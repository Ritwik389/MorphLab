"""Same-origin API for MorphLab Studio. Model and camera state never live in the frontend bundle."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import shutil
import time
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from PIL import Image, UnidentifiedImageError

from modules.paths import ROOT_DIR
from modules import research
from modules.runtime import registry
from modules.studio_live import LiveSession, unpack_frame
from modules.studio_jobs import Job, POOL, run_job
from modules.evaluation import fingerprint

ROOT = Path(ROOT_DIR)
EXAMPLES = ROOT / 'assets/examples'
sessions = {}
jobs = {}
connected = set()
admission_lock = threading.RLock()
logger = logging.getLogger('aims')
STARTUP_SOURCE_SHA256 = fingerprint()['source_tree_sha256']


def expire():
    now = time.monotonic()
    for key, session in list(sessions.items()):
        if key not in connected and now-session.touched > 3600:
            sessions.pop(key, None)
            session.set_source(None)
            session.reset_camera()
    for key, job in list(jobs.items()):
        if job.state in {'complete', 'error', 'cancelled'} and time.time()-job.created > 3600:
            shutil.rmtree(job.directory, ignore_errors=True)
            jobs.pop(key, None)
    if research.OUTPUT_ROOT.exists():
        for directory in research.OUTPUT_ROOT.iterdir():
            if (directory.is_dir() and len(directory.name) == 32
                    and all(c in '0123456789abcdef' for c in directory.name)
                    and directory.name not in jobs and time.time()-directory.stat().st_mtime > 3600):
                shutil.rmtree(directory, ignore_errors=True)


@asynccontextmanager
async def lifespan(app):
    async def cleanup():
        while True:
            await asyncio.sleep(60)
            expire()
    task = asyncio.create_task(cleanup())
    yield
    task.cancel()
    for job in jobs.values():
        job.cancelled.set()
    sessions.clear()


app = FastAPI(title='MorphLab Studio', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[
    value.strip() for value in os.getenv('AIMS_ALLOWED_HOSTS', 'localhost,127.0.0.1,::1,testserver').split(',')
    if value.strip()
])


@app.middleware('http')
async def boundaries(request: Request, call_next):
    from urllib.parse import urlparse
    origin = request.headers.get('origin')
    if request.method not in {'GET','HEAD','OPTIONS'} and origin and urlparse(origin).netloc != request.headers.get('host'):
        return JSONResponse({'detail':'Cross-origin writes are not allowed.'},403)
    try:
        if int(request.headers.get('content-length', '0')) > 105 * 1024 * 1024:
            return JSONResponse({'detail': 'Upload must be under 100 MB.'}, 413)
    except ValueError:
        return JSONResponse({'detail': 'Invalid request size.'}, 400)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({'detail': str(exc)}, 422)


def session_for(key):
    session = sessions.get(key)
    if session is None:
        raise HTTPException(404, 'Session expired. Start a new camera session.')
    return session


def load_image(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > research.MAX_PIXELS:
                raise ValueError('Image must be under 16 megapixels.')
            return research.read_image(image)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Could not read this image. Use PNG, JPEG, or WebP.') from exc


async def read_upload(file, limit):
    output = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            output.extend(chunk)
            if len(output) > limit:
                raise ValueError('File is too large.')
    finally:
        await file.close()
    return bytes(output)


@app.get('/api/system')
def system():
    return {**registry.status(), 'source_tree_sha256': STARTUP_SOURCE_SHA256}


@app.get('/api/diagnostics/resources')
def resources():
    return {**registry.memory_status(),
            'sessions':len(sessions),'connected':len(connected),
            'scope':'Process RSS includes shared model weights and allocator caches.'}


def latest_evaluation():
    reports = list((ROOT/'outputs/evaluations').glob('*/report.json'))
    return max(reports,key=lambda p:p.stat().st_mtime) if reports else None


@app.get('/api/evaluation')
def evaluation_status():
    file = latest_evaluation()
    if file is None:
        return {'status':'Not Run','checks':[],'note':'Run scripts/verify.py to generate a reproducible verification report.'}
    data = json.loads(file.read_text())
    from modules.evaluation import fingerprint
    stale = data['manifest'].get('source_tree_sha256') != fingerprint()['source_tree_sha256']
    return {'status':'Not Run' if stale else data['overall'],'recorded_status':data['overall'],'stale':stale,'run':file.parent.name,
            'suite':data['manifest'].get('suite','experiment'),
            'release_status':data['overall'] if not stale and data['manifest'].get('suite') == 'release' else 'Not Run',
            'created_at':data['manifest'].get('created_at'),
            'checks':[{'name':c['name'],'status':c['status']} for c in data['checks']],
            'report':'/api/evaluation/report',
            'note':'Each report applies to its recorded source fingerprint and test conditions. Functional checks alone do not establish full release acceptance.'}


@app.get('/api/evaluation/report')
def evaluation_report():
    file = latest_evaluation()
    if file is None or not file.with_suffix('.html').exists():
        raise HTTPException(404,'No verification report is available yet.')
    return FileResponse(file.with_suffix('.html'),filename='morphlab-verification.html',media_type='text/html')


@app.post('/api/system/prepare')
def prepare():
    try:
        with registry.scheduler.use():
            return registry.prepare()
    except Exception as exc:
        raise HTTPException(503, f'Model warmup failed: {exc}') from exc


@app.get('/api/examples')
def examples():
    file = EXAMPLES / 'manifest.json'
    return json.loads(file.read_text()) if file.exists() else {'pairs': [], 'fixtures': []}


@app.post('/api/sessions')
def create_session():
    with admission_lock:
        expire()
        if len(sessions) >= 32:
            raise HTTPException(429, 'Too many camera sessions. Close an unused session.')
        key = uuid.uuid4().hex
        sessions[key] = LiveSession()
    return {'id': key, 'revision': 0}


@app.delete('/api/sessions/{key}')
def delete_session(key):
    session = sessions.pop(key, None)
    if session:
        session.set_source(None)
        session.reset_camera()
    return {'deleted': True}


@app.put('/api/sessions/{key}/source')
async def enroll(key: str, file: UploadFile | None = File(None), example: str | None = Form(None), camera: bool = Form(False)):
    session = session_for(key)
    expected_revision = session.revision
    if camera:
        with session.lock:
            frame = None if session.latest is None else session.latest.copy()
        if frame is None:
            raise ValueError('Start the camera and wait for a frame before capturing.')
    elif file:
        frame = await asyncio.to_thread(load_image, await read_upload(file, 20 * 1024 * 1024))
    elif example:
        valid = {p['source'] for p in examples()['pairs']}
        if example not in valid:
            raise ValueError('Choose an available sample identity.')
        frame = load_image((EXAMPLES / Path(example).name).read_bytes())
    else:
        raise ValueError('Choose a source image or capture your camera face.')
    def extract():
        from modules.source_checks import analyse_source
        with registry.scheduler.use(live=True):
            faces = registry.detect(frame)
            if len(faces) != 1:
                raise ValueError('Use a source with exactly one clear face.' if faces else 'No face detected in source. Try a clear portrait.')
            points = registry.landmarks(frame, faces[0])
            checks = analyse_source(frame, faces[0], points)
            return registry.live_source(frame), checks
    latent, checks = await asyncio.to_thread(extract)
    with session.lock:
        if sessions.get(key) is not session or session.revision != expected_revision:
            from modules.studio_live import erase
            erase(latent)
            raise HTTPException(409, 'Source preparation was superseded or the session was cleared.')
        session.source_checks = checks
        revision = session.set_source(latent)
    return {'revision': revision, 'mode': 'swap', 'checks':checks, 'message': 'Source identity ready'}


@app.get('/api/sessions/{key}/people/{person}/thumbnail')
def thumbnail(key: str, person: int):
    session = session_for(key)
    with session.lock:
        data = session.thumbnails.get(person)
    if data is None:
        raise HTTPException(404, 'Person thumbnail is no longer available.')
    return Response(data, media_type='image/jpeg', headers={'Cache-Control':'no-store'})


@app.post('/api/sessions/{key}/purge')
def purge(key: str):
    session = session_for(key)
    with session.lock:
        revision = session.set_source(None)
        session.reset_camera()
    return {'revision':revision,'cleared':True,'note':'Session references cleared; physical allocator copies cannot be guaranteed erased.'}


@app.delete('/api/sessions/{key}/source')
def clear_source(key):
    return {'revision': session_for(key).set_source(None)}


@app.websocket('/api/live/{key}')
async def live(socket: WebSocket, key: str):
    from urllib.parse import urlparse
    origin = socket.headers.get('origin')
    if origin and urlparse(origin).netloc != socket.headers.get('host'):
        await socket.close(code=1008)
        return
    if key not in sessions or key in connected:
        await socket.close(code=1008)
        return
    session = session_for(key)
    connected.add(key)
    try:
        await socket.accept()
    except BaseException:
        connected.discard(key)
        raise
    registry.scheduler.camera(1)
    queue = asyncio.Queue(maxsize=1)
    dropped = 0
    async def process():
        nonlocal dropped
        roster_at = 0
        while True:
            data, received_at = await queue.get()
            try:
                decode_started = time.perf_counter()
                metadata, frame = await asyncio.to_thread(unpack_frame, data)
                metadata['input_decode_ms'] = (time.perf_counter()-decode_started)*1000
                metadata['queue_wait_ms'] = (decode_started-received_at)*1000
                result = await asyncio.to_thread(session.process, {**metadata, 'dropped_frames': dropped}, frame)
                if result is not None and key in sessions:
                    await socket.send_bytes(result)
                    if time.monotonic()-roster_at >= 1:
                        with session.lock:
                            people = session.roster()
                        for person in people:
                            person['thumbnail'] = person['thumbnail'].replace('{session}',key)
                        if people:
                            await socket.send_json({'type':'people','revision':session.revision,'people':people})
                        roster_at = time.monotonic()
            except (ValueError, RuntimeError, OSError) as exc:
                await socket.send_json({'error': str(exc)})
            finally:
                queue.task_done()
    worker = asyncio.create_task(process())
    try:
        while True:
            # Notice disconnected send workers even when the browser sends no more frames.
            receive = asyncio.create_task(socket.receive())
            done, _ = await asyncio.wait({receive, worker}, return_when=asyncio.FIRST_COMPLETED)
            if worker in done:
                receive.cancel()
                await worker
                break
            message = receive.result()
            if message['type'] == 'websocket.disconnect':
                break
            if message.get('bytes') is not None:
                if len(message['bytes']) > 2_100_000:
                    raise ValueError('Camera frame is too large.')
                if queue.full():
                    queue.get_nowait()
                    queue.task_done()
                    dropped += 1
                queue.put_nowait((message['bytes'],time.perf_counter()))
            elif message.get('text'):
                control = json.loads(message['text'])
                await asyncio.to_thread(session.control, control)
                await socket.send_json({'type':'control','target_revision':session.target_revision})
    except (WebSocketDisconnect, RuntimeError, ValueError, json.JSONDecodeError, RecursionError):
        pass
    finally:
        worker.cancel()
        try:
            await worker
        except (asyncio.CancelledError, RuntimeError, WebSocketDisconnect):
            pass
        finally:
            connected.discard(key)
            registry.scheduler.camera(-1)
            # A send failure must not retain a device reservation or private frames.
            await asyncio.to_thread(session.reset_camera)
            await asyncio.to_thread(session.set_source, None)
            try:
                await socket.close()
            except (RuntimeError, WebSocketDisconnect):
                pass


@app.post('/api/jobs')
async def create_job(target: UploadFile = File(...), source: UploadFile | None = File(None),
                     kind: str = Form('photo'), mode: str = Form('swap'), many: bool = Form(False),
                     strength: float = Form(1), consent: bool = Form(False)):
    if not consent:
        raise ValueError('Confirm you have permission to edit this media.')
    if kind not in {'photo', 'video'} or mode not in {'swap', 'blur', 'pixelate'}:
        raise ValueError('Choose a supported media type and effect.')
    if not 0 < strength <= 1:
        raise ValueError('Blend strength must be greater than zero and at most one.')
    if mode == 'swap' and source is None:
        raise ValueError('Choose a source portrait first.')
    with admission_lock:
        if sum(j.state in {'queued', 'running'} for j in jobs.values()) >= 4:
            raise HTTPException(429, 'The export queue is full. Wait for a job to finish.')
        job = Job()
        job.directory.mkdir(parents=True, exist_ok=True)
        jobs[job.id] = job
    try:
        target_bytes = await read_upload(target, 100 * 1024 * 1024)
        if kind == 'photo':
            bgr = await asyncio.to_thread(load_image, target_bytes)
            import cv2
            target_value = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        else:
            target_value = job.directory / 'target.upload'
            target_value.write_bytes(target_bytes)
            await asyncio.to_thread(research.probe_video, str(target_value))
        source_value = None
        if source:
            bgr = await asyncio.to_thread(load_image, await read_upload(source, 20 * 1024 * 1024))
            import cv2
            source_value = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        jobs[job.id] = job
        POOL.submit(run_job, job, source_value, target_value, kind, mode, many, strength)
        return job.public()
    except BaseException:
        jobs.pop(job.id,None)
        shutil.rmtree(job.directory, ignore_errors=True)
        raise


def job_for(key):
    job = jobs.get(key)
    if job is None:
        raise HTTPException(404, 'Job expired or does not exist.')
    return job


@app.get('/api/jobs/{key}')
def job_status(key):
    return job_for(key).public()


@app.delete('/api/jobs/{key}')
def cancel_job(key):
    job = job_for(key)
    job.cancelled.set()
    return job.public()


@app.get('/api/jobs/{key}/{asset}')
def download(key, asset):
    job = job_for(key)
    if job.state != 'complete' or asset not in {'result', 'report', 'original'}:
        raise HTTPException(404, 'Result is not ready.')
    if asset == 'original':
        file = job.directory/'original.png'
        if not file.is_file():
            raise HTTPException(404, 'Original preview is unavailable.')
    else:
        file = job.directory / 'report.json' if asset == 'report' else next(job.directory.glob('result.*'))
    return FileResponse(file, filename=file.name)


app.mount('/examples', StaticFiles(directory=EXAMPLES), name='examples')


@app.get('/{path:path}')
def frontend(path: str):
    if path.startswith('api/'):
        raise HTTPException(404, 'API endpoint does not exist.')
    root = ROOT / 'frontend/dist'
    candidate = (root / path).resolve()
    if root.resolve() in candidate.parents and candidate.is_file():
        return FileResponse(candidate)
    if (root / 'index.html').is_file():
        return FileResponse(root / 'index.html')
    raise HTTPException(503, 'Frontend is not built. Run: cd frontend && npm ci && npm run build')
