import io
import json
import struct
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from modules.runtime import InferenceScheduler
from modules.studio_live import LiveSession, pack_frame, unpack_frame
from modules import studio_api, research


def jpeg():
    image = Image.new('RGB', (160, 120), 'white')
    output = io.BytesIO()
    image.save(output, 'JPEG')
    return output.getvalue()


def test_binary_frame_roundtrip_and_validation():
    header = {'frame_id': 4, 'revision': 2, 'captured_at': 123.5}
    metadata, frame = unpack_frame(pack_frame(header, jpeg()))
    assert metadata == header and frame.shape == (120, 160, 3)
    for invalid in [b'', struct.pack('!I', 9999999) + b'[]', pack_frame({**header, 'frame_id': -1}, jpeg())]:
        with pytest.raises((ValueError, json.JSONDecodeError)):
            unpack_frame(invalid)


def test_decoded_image_size_is_checked_before_expansion():
    output = io.BytesIO()
    Image.new('RGB', (1400, 10)).save(output, 'PNG')
    with pytest.raises(ValueError, match='Live frames'):
        unpack_frame(pack_frame({'frame_id': 1, 'revision': 0, 'captured_at': 0}, output.getvalue()))


def test_source_revisions_reject_stale_frames_without_inference(monkeypatch):
    session = LiveSession()
    session.set_source(np.ones((1, 512)))
    monkeypatch.setattr('modules.studio_live.registry.detect', lambda *a: pytest.fail('stale frame detected'))
    assert session.process({'revision': 0}, np.zeros((100, 100, 3), np.uint8)) is None
    session.set_source(None)
    assert session.revision == 2 and session.latent is None


def test_live_priority_and_cancelled_offline_waiter():
    scheduler = InferenceScheduler()
    entered = threading.Event()
    order = []
    def work(name, live):
        entered.set()
        with scheduler.use(live=live):
            order.append(name)
    with scheduler.use():
        offline = threading.Thread(target=work, args=('offline', False))
        online = threading.Thread(target=work, args=('live', True))
        offline.start(); online.start()
        deadline = time.monotonic() + 2
        while not scheduler.live_waiters and time.monotonic() < deadline:
            time.sleep(.001)
        assert scheduler.live_waiters == 1
    online.join(2); offline.join(2)
    assert order == ['live', 'offline']
    with pytest.raises(InterruptedError):
        with scheduler.use(cancelled=lambda: True):
            pytest.fail('cancelled job acquired the device')
    assert not scheduler.busy


def test_live_does_not_use_legacy_export_lock(monkeypatch):
    from modules import studio_live
    monkeypatch.setattr(studio_live, 'observe', lambda frame: ([], cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
    session = LiveSession()
    research.JOB_LOCK.acquire()
    try:
        packet = session.process({'frame_id': 1, 'revision': 0, 'captured_at': 0}, np.zeros((120, 160, 3), np.uint8))
        size = struct.unpack('!I', packet[:4])[0]
        assert json.loads(packet[4:4+size])['swapped'] is False
    finally:
        research.JOB_LOCK.release()
        session.reset_camera()


def test_sessions_are_isolated_and_deleted():
    with TestClient(studio_api.app) as client:
        a = client.post('/api/sessions').json()['id']
        b = client.post('/api/sessions').json()['id']
        studio_api.sessions[a].set_source(np.ones((1, 512)))
        assert studio_api.sessions[b].latent is None
        assert client.delete(f'/api/sessions/{a}').status_code == 200
        assert a not in studio_api.sessions
        assert client.delete(f'/api/sessions/{b}').status_code == 200


def test_examples_and_routes_are_ready_without_model_loading(monkeypatch):
    monkeypatch.setattr(studio_api.registry, 'prepare', lambda: pytest.fail('landing loaded model'))
    with TestClient(studio_api.app) as client:
        examples = client.get('/api/examples').json()
        assert len(examples['pairs']) == 3 and len(examples['fixtures']) >= 5
        for route in ['/', '/studio', '/how-it-works']:
            assert client.get(route).status_code == 200
        assert client.get('/api/does-not-exist').status_code == 404


def test_websocket_rejects_cross_origin_and_invalid_session():
    with TestClient(studio_api.app) as client:
        key = client.post('/api/sessions').json()['id']
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f'/api/live/{key}', headers={'origin':'https://unrelated.invalid'}):
                pass
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/api/live/missing'):
                pass
        client.delete(f'/api/sessions/{key}')


def test_invalid_media_returns_friendly_error(tmp_path):
    path = tmp_path / 'bad.mp4'
    path.write_bytes(b'not a movie')
    with pytest.raises(ValueError, match='Could not read this video'):
        research.probe_video(str(path))
    with TestClient(studio_api.app) as client:
        response = client.post('/api/jobs', data={'kind':'photo','mode':'blur','consent':'true'},
                               files={'target':('bad.jpg',b'not an image','image/jpeg')})
        assert response.status_code == 422 and 'Could not read this image' in response.json()['detail']


def test_unknown_source_example_cannot_read_arbitrary_files():
    with TestClient(studio_api.app) as client:
        key = client.post('/api/sessions').json()['id']
        response = client.put(f'/api/sessions/{key}/source', data={'example':'../../.env'})
        assert response.status_code == 422
        client.delete(f'/api/sessions/{key}')


def test_failed_accelerator_warmup_falls_back_to_validated_cpu(monkeypatch):
    from modules.runtime import ModelRegistry, RuntimeConfig
    model = ModelRegistry(RuntimeConfig(device='auto'))
    loads = []
    def load(force_cpu=False):
        loads.append(force_cpu)
        model.swapper = object()
        model.active = 'CPU' if force_cpu else 'Native CoreML'
    monkeypatch.setattr(model, '_load_swapper', load)
    monkeypatch.setattr(model, '_infer', lambda *args: np.ones((1, 3, 128, 128), np.float32) if model.active == 'CPU' else np.full((1, 3, 128, 128), np.nan))
    status = model.prepare()
    assert loads == [False, True]
    assert status['state'] == 'ready' and status['active_runtime'] == 'CPU'
    assert 'warmup failed' in status['fallback_reason']


def test_active_camera_pauses_offline_work_and_cancellation_still_works():
    scheduler = InferenceScheduler()
    scheduler.camera(1)
    cancel = threading.Event()
    finished = threading.Event()
    def offline():
        try:
            with scheduler.use(cancelled=cancel.is_set):
                pytest.fail('offline job ran while camera was active')
        except InterruptedError:
            finished.set()
    worker = threading.Thread(target=offline)
    worker.start()
    with scheduler.use(live=True):
        assert scheduler.busy
    cancel.set()
    assert finished.wait(2)
    scheduler.camera(-1)
    worker.join(2)


def test_websocket_replaces_pending_frames_instead_of_accumulating(monkeypatch):
    started, release = threading.Event(), threading.Event()
    def slow(self, metadata, frame):
        if metadata['frame_id'] == 0:
            started.set()
            assert release.wait(2)
        return pack_frame(metadata, jpeg())
    monkeypatch.setattr(LiveSession, 'process', slow)
    with TestClient(studio_api.app) as client:
        key = client.post('/api/sessions').json()['id']
        with client.websocket_connect(f'/api/live/{key}') as socket:
            socket.send_bytes(pack_frame({'frame_id':0,'revision':0,'captured_at':0},jpeg()))
            assert started.wait(2)
            for frame_id in [1, 2, 3]:
                socket.send_bytes(pack_frame({'frame_id':frame_id,'revision':0,'captured_at':0},jpeg()))
            time.sleep(.05)
            release.set()
            first, _ = unpack_frame(socket.receive_bytes())
            latest, _ = unpack_frame(socket.receive_bytes())
            assert first['frame_id'] == 0 and latest['frame_id'] == 3
            assert latest['dropped_frames'] == 2
        client.delete(f'/api/sessions/{key}')


def test_frame_send_disconnect_always_releases_live_reservation(monkeypatch):
    from starlette.websockets import WebSocketDisconnect
    before = studio_api.registry.scheduler.live_sessions
    def failed_send(self, metadata, frame):
        raise WebSocketDisconnect(code=1006)
    monkeypatch.setattr(LiveSession, 'process', failed_send)
    with TestClient(studio_api.app) as client:
        key = client.post('/api/sessions').json()['id']
        with client.websocket_connect(f'/api/live/{key}') as socket:
            socket.send_bytes(pack_frame({'frame_id':0,'revision':0,'captured_at':0},jpeg()))
            assert socket.receive()['type'] == 'websocket.close'
        assert key not in studio_api.connected
        assert studio_api.registry.scheduler.live_sessions == before
        assert studio_api.sessions[key].latent is None
        client.delete(f'/api/sessions/{key}')


def test_coreml_cache_is_separated_by_input_shape(tmp_path, monkeypatch):
    import onnx
    from onnx import helper, TensorProto, numpy_helper
    from modules import onnx_optimize
    monkeypatch.setattr(onnx_optimize, 'IS_APPLE_SILICON', True)
    model = helper.make_model(helper.make_graph([
        helper.make_node('Pad', ['x', 'pads'], ['y'], mode='reflect')], 'cache-shape',
        [helper.make_tensor_value_info('x', TensorProto.FLOAT, [1, 1, None, None])],
        [helper.make_tensor_value_info('y', TensorProto.FLOAT, [1, 1, None, None])],
        [numpy_helper.from_array(np.array([0,0,1,1,0,0,1,1],np.int64),'pads')]),
        opset_imports=[helper.make_opsetid('',13)])
    path = tmp_path / 'model.onnx'
    onnx.save(model, path)
    a = onnx_optimize.optimize_for_coreml(str(path), (1,1,3,3))
    b = onnx_optimize.optimize_for_coreml(str(path), (1,1,5,5))
    assert a != b and a != str(path)
    assert onnx.load(a).graph.input[0].type.tensor_type.shape.dim[2].dim_value == 3
    assert onnx.load(b).graph.input[0].type.tensor_type.shape.dim[2].dim_value == 5


@pytest.mark.parametrize('cancelled', [False, True])
def test_failed_or_cancelled_photo_removes_original_preview(tmp_path, monkeypatch, cancelled):
    from modules.studio_jobs import Job, run_job
    from modules import studio_jobs
    monkeypatch.setattr(research, 'OUTPUT_ROOT', tmp_path)
    monkeypatch.setattr(studio_jobs.registry, 'detect', lambda *args, **kwargs: [])
    job = Job()
    job.directory.mkdir()
    if cancelled:
        job.cancelled.set()
    run_job(job, None, Image.new('RGB',(100,100),'white'), 'photo','blur',False,1)
    assert job.state == ('cancelled' if cancelled else 'error')
    assert not (job.directory/'original.png').exists()
    assert not list(job.directory.glob('result.*'))
