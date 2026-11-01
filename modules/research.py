"""Bounded image experiments and short video exports for the research UI."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from modules.paths import MODELS_DIR, ROOT_DIR
from modules.utilities import file_sha256

OUTPUT_ROOT = Path(ROOT_DIR) / 'outputs' / 'web'
JOB_LOCK = threading.Lock()
MAX_PIXELS = 16_000_000
MAX_SIDE = 1600
MODES = ['Swap identity', 'Blur faces', 'Pixelate faces']


def new_job() -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    # Only our UUID-named results expire; never inspect arbitrary user folders.
    for path in OUTPUT_ROOT.iterdir():
        if path.is_dir() and len(path.name) == 32 and time.time() - path.stat().st_mtime > 3600:
            shutil.rmtree(path, ignore_errors=True)
    directory = OUTPUT_ROOT / uuid.uuid4().hex
    directory.mkdir()
    return directory


def read_image(value) -> np.ndarray:
    if value is None:
        raise ValueError('Upload a target image first.')
    image = value if isinstance(value, Image.Image) else Image.fromarray(np.asarray(value))
    if image.width * image.height > MAX_PIXELS:
        raise ValueError('Image is too large. Use an image under 16 megapixels.')
    image = ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def configure_runtime():
    import modules.globals as state
    import onnxruntime as ort
    selected = os.environ.get('AIMS_EXECUTION_PROVIDER', 'cpu').lower()
    names = {'cpu': 'CPUExecutionProvider', 'coreml': 'CoreMLExecutionProvider',
             'cuda': 'CUDAExecutionProvider'}
    provider = names.get(selected)
    if provider not in ort.get_available_providers():
        raise ValueError(f'Execution provider {selected!r} is unavailable.')
    state.execution_providers = list(dict.fromkeys([provider, 'CPUExecutionProvider']))
    state.execution_threads = 2
    state.headless = True
    state.map_faces = False
    state.many_faces = False
    state.frame_processors = ['face_swapper']
    state.enable_interpolation = False
    state.mouth_mask = False
    state.poisson_blend = False
    state.sharpness = 0.0
    state.opacity = 1.0


def require_models():
    manifest = json.loads((Path(ROOT_DIR) / 'models-manifest.json').read_text())
    missing = [m['path'] for m in manifest['models'] if not (Path(MODELS_DIR) / m['path']).is_file()]
    if missing:
        raise ValueError('Face-swap models are missing. Run: .venv/bin/python scripts/download_models.py')


def quality(frame: np.ndarray, bbox=None) -> dict:
    crop = frame
    if bbox is not None:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = np.asarray(bbox).astype(int)
        crop = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    if crop.size == 0:
        return {'warning': 'Face lies outside the image.'}
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    warnings = []
    if min(crop.shape[:2]) < 80:
        warnings.append('Small face crop; use a higher resolution image.')
    if sharpness < 70:
        warnings.append('Low edge detail; focus or compression may limit the result.')
    if brightness < 50 or brightness > 215:
        warnings.append('Extreme lighting may reduce quality.')
    return {'mean_luminance_0_255': round(brightness, 2),
            'laplacian_variance': round(sharpness, 2), 'warnings': warnings}


def watermark(frame: np.ndarray) -> np.ndarray:
    result = frame.copy()
    h, w = result.shape[:2]
    scale = max(0.35, min(0.7, w / 900))
    text = 'MorphLab / EDITED'
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = max(0, w - tw - 14), max(th + 4, h - 12)
    cv2.rectangle(result, (max(0, x - 6), max(0, y - th - 6)),
                  (min(w - 1, x + tw + 6), min(h - 1, y + 5)), (20, 20, 20), -1)
    cv2.putText(result, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255, 255, 255), 1, cv2.LINE_AA)
    return result


def process_image(source, target, mode='Swap identity', strength=1.0,
                  many_faces=False, consent=False):
    if not consent:
        raise ValueError('Confirm you have permission to edit the supplied media.')
    if mode not in MODES:
        raise ValueError('Select a supported editing mode.')
    if not 0 < float(strength) <= 1:
        raise ValueError('Blend strength must be greater than 0 and at most 1.')
    with JOB_LOCK:
        started = time.perf_counter()
        frame = read_image(target)
        original = frame.copy()
        report = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                  'mode': mode, 'width': frame.shape[1], 'height': frame.shape[0],
                  'quality_metrics_are_heuristics': True,
                  'notice': 'These measurements do not establish authenticity or anonymity.'}
        if mode == 'Swap identity':
            require_models()
            configure_runtime()
            from modules.face_analyser import get_many_faces, get_one_face
            from modules.processors.frame.face_swapper import swap_face
            import modules.globals as state
            source_frame = read_image(source)
            source_face = get_one_face(source_frame)
            faces = sorted(get_many_faces(frame) or [], key=lambda f: f.bbox[0])
            if source_face is None:
                raise ValueError('No face detected in source. Use a clear, front-facing portrait.')
            if not faces:
                raise ValueError('No face detected in target. Use a clear portrait.')
            selected = faces if many_faces else faces[:1]
            state.opacity = float(strength)
            report['source_quality'] = quality(source_frame, source_face.bbox)
            report['target_quality'] = [quality(frame, face.bbox) for face in selected]
            for face in selected:
                frame = swap_face(source_face, face, frame)
            output_face = get_one_face(frame)
            if output_face is not None:
                # A raw cosine comparison, deliberately not labelled as a probability.
                report['source_output_embedding_cosine'] = round(float(np.dot(
                    source_face.normed_embedding, output_face.normed_embedding)), 4)
            report['providers'] = state.execution_providers
            report['faces_detected'] = len(faces)
            report['faces_edited'] = len(selected)
        else:
            detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            boxes = detector.detectMultiScale(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                                               scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            if len(boxes) == 0:
                raise ValueError('No frontal faces detected. Try a clearer, front-facing image.')
            for x, y, w, h in boxes:
                roi = frame[y:y+h, x:x+w]
                if mode == 'Pixelate faces':
                    roi[:] = cv2.resize(cv2.resize(roi, (8, 8), interpolation=cv2.INTER_AREA),
                                        (w, h), interpolation=cv2.INTER_NEAREST)
                else:
                    roi[:] = cv2.GaussianBlur(roi, (0, 0), max(12, w / 5))
            report.update(faces_detected=len(boxes), faces_edited=len(boxes),
                          detector='OpenCV frontal-face Haar cascade',
                          warning='Frontal detection can miss faces; inspect every result before sharing.')
        # Measure before adding a label so it cannot inflate the changed-pixel metric.
        report['mean_absolute_pixel_change_0_255'] = round(float(np.abs(
            frame.astype(np.float32) - original.astype(np.float32)).mean()), 3)
        frame = watermark(frame)
        directory = new_job()
        output = directory / 'edited.png'
        Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(output)
        report['output_sha256'] = file_sha256(str(output))
        report['processing_seconds'] = round(time.perf_counter() - started, 3)
        report_path = directory / 'report.json'
        report_path.write_text(json.dumps(report, indent=2))
        before = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
        after = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return (before, after), str(output), str(report_path), report


def probe_video(path: str) -> dict:
    if not path or not Path(path).is_file():
        raise ValueError('Upload a target video first.')
    if Path(path).stat().st_size > 100 * 1024 * 1024:
        raise ValueError('Video must be under 100 MB.')
    try:
        data = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
            timeout=20, stderr=subprocess.PIPE))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError('Could not read this video. Use a valid MP4, MOV, or WebM file.') from exc
    videos = [s for s in data['streams'] if s['codec_type'] == 'video']
    if not videos:
        raise ValueError('The upload does not contain a video stream.')
    stream = videos[0]
    duration = float(data.get('format', {}).get('duration', stream.get('duration', 0)))
    if not 0 < duration <= 30:
        raise ValueError('The browser demo accepts videos up to 30 seconds.')
    if max(stream['width'], stream['height']) > 1280 or min(stream['width'], stream['height']) > 720:
        raise ValueError('Use a video at 720p or below for this CPU demo.')
    return {'duration_seconds': duration, 'width': stream['width'], 'height': stream['height']}


def process_video(source, target: str, consent=False, strategy='tracked', interval=3):
    if not consent:
        raise ValueError('Confirm you have permission to edit the supplied media.')
    require_models()
    if strategy not in {'baseline', 'tracked', 'adaptive'}:
        raise ValueError('Select a supported video strategy.')
    if int(interval) != interval or not 1 <= int(interval) <= 10:
        raise ValueError('Detection interval must be an integer from 1 to 10.')
    metadata = probe_video(target)
    source_frame = read_image(source)
    with JOB_LOCK:
        directory = new_job()
        source_path = directory / 'source.png'
        Image.fromarray(cv2.cvtColor(source_frame, cv2.COLOR_BGR2RGB)).save(source_path)
        raw_output = directory / 'raw.mp4'
        output = directory / 'edited.mp4'
        metrics_path = directory / 'pipeline-report.json'
        label_path = directory / 'label.png'
        label = Image.new('RGBA', (170, 32), (20, 20, 20, 220))
        ImageDraw.Draw(label).text((8, 6), 'MorphLab / EDITED', fill='white', font=ImageFont.load_default(size=18))
        label.save(label_path)
        started = time.perf_counter()
        try:
            with (directory / 'processing.log').open('w+') as log:
                subprocess.run([sys.executable, str(Path(ROOT_DIR) / 'run.py'),
                    '-s', str(source_path), '-t', str(Path(target).resolve()), '-o', str(raw_output),
                    '--execution-provider', os.environ.get('AIMS_EXECUTION_PROVIDER', 'cpu'),
                    '--execution-threads', '2', '--max-memory', '0',
                    '--temporal-strategy', strategy, '--detection-interval', str(int(interval)),
                    '--research-report', str(metrics_path)], cwd=ROOT_DIR,
                    stdout=log, stderr=subprocess.STDOUT, timeout=900, check=True)
            # A PNG overlay works even when FFmpeg has no libfreetype/drawtext.
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(raw_output), '-i', str(label_path),
                '-filter_complex', '[0:v][1:v]overlay=x=max(0\\,main_w-overlay_w-12):y=max(0\\,main_h-overlay_h-12)[v]',
                '-map', '[v]', '-map', '0:a?',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-c:a', 'copy',
                '-movflags', '+faststart', '-y', str(output)], check=True, timeout=120,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            report = {**json.loads(metrics_path.read_text()), **metadata, 'mode': 'Swap identity', 'processing_seconds': round(time.perf_counter() - started, 3),
                      'output_sha256': file_sha256(str(output)), 'watermark': 'MorphLab / EDITED'}
            report_path = directory / 'report.json'
            report_path.write_text(json.dumps(report, indent=2))
            return str(output), str(report_path), report
        except (subprocess.SubprocessError, OSError) as exc:
            with (directory / 'processing.log').open('a') as log:
                log.write(f'\nExport failure: {exc}\n')
                detail = getattr(exc, 'stderr', None)
                if detail:
                    log.write(detail.decode(errors='replace') if isinstance(detail, bytes) else detail)
            raise RuntimeError('Video export failed. Check outputs/web/<job>/processing.log for details.') from exc
        finally:
            source_path.unlink(missing_ok=True)
            raw_output.unlink(missing_ok=True)
            label_path.unlink(missing_ok=True)
