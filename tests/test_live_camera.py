from types import SimpleNamespace
from unittest.mock import Mock
import threading

import cv2
import numpy as np
import pytest

from modules import live_camera, research


def observation():
    return {'bbox':np.array([20,20,100,110]),'score':.95,
            'kps':np.array([[40,45],[80,45],[60,65],[45,90],[75,90]],np.float32)}


@pytest.fixture
def detected(monkeypatch):
    monkeypatch.setattr(live_camera,'detect_faces',lambda frame:([observation()],'test detector'))
    return np.random.default_rng(5).integers(0,256,(160,200,3),dtype=np.uint8)


def test_camera_waits_for_frames_without_requesting_a_photo(monkeypatch):
    monkeypatch.setattr(live_camera,'detect_faces',lambda frame:pytest.fail('no frame to detect'))
    output,status=live_camera.process_frame(None)
    assert output is None and 'webcam' in status.lower() and 'upload' not in status.lower()


def test_live_detection_needs_no_identity_or_swap_models(detected,monkeypatch):
    monkeypatch.setattr(research,'require_models',lambda:pytest.fail('detection must not require swap weights'))
    output,status=live_camera.process_frame(detected)
    assert output.shape==detected.shape
    assert not np.array_equal(output,detected)
    assert '1 face detected' in status


def test_no_face_is_a_normal_live_state(monkeypatch):
    monkeypatch.setattr(live_camera,'detect_faces',lambda frame:([],'test detector'))
    output,status=live_camera.process_frame(np.zeros((80,120,3),np.uint8))
    assert output.shape==(80,120,3) and '0 faces detected' in status


@pytest.mark.parametrize('mode',['Blur faces','Pixelate faces'])
def test_live_privacy_modes_need_no_source_photo(mode,detected):
    output,status=live_camera.process_frame(detected,mode)
    assert not np.array_equal(output[40:90,40:80],detected[40:90,40:80])
    assert '1 face detected' in status


def test_swap_without_captured_identity_keeps_detection_running(detected,monkeypatch):
    monkeypatch.setattr(research,'require_models',lambda:pytest.fail('not swapping yet'))
    output,status=live_camera.process_frame(detected,'Swap face')
    assert output is not None and 'Capture a webcam face' in status
    assert 'upload' not in status.lower()


def test_camera_frames_are_bounded_and_keep_rgb_bgr_contract():
    rgb=np.zeros((1080,1920,3),np.uint8)
    rgb[:]=[250,0,10]
    frame=live_camera.camera_frame(rgb)
    assert frame.shape==(360,640,3)
    np.testing.assert_array_equal(frame[0,0],[10,0,250])
    with pytest.raises(ValueError,match='RGB'):
        live_camera.camera_frame(np.zeros((80,120),np.uint8))


def test_capture_uses_current_webcam_frame_and_stores_only_session_arrays(detected,monkeypatch):
    from modules import face_analyser
    original=np.ones(512,dtype=np.float32)
    monkeypatch.setattr(research,'JOB_LOCK',threading.Lock())
    monkeypatch.setattr(research,'require_models',lambda:None)
    monkeypatch.setattr(research,'configure_runtime',lambda:None)
    extract=Mock(return_value=SimpleNamespace(bbox=observation()['bbox'],embedding=original))
    monkeypatch.setattr(face_analyser,'get_one_face',extract)
    identity,preview,status=live_camera.capture_identity(detected)
    assert preview.shape==(90,80,3)
    assert set(identity)=={'embedding'}
    original[:]=0
    assert identity['embedding'].sum()==512
    expected=cv2.cvtColor(detected,cv2.COLOR_RGB2BGR)
    np.testing.assert_array_equal(extract.call_args.args[0],expected)
    assert 'captured' in status.lower()


def test_capture_without_a_face_is_actionable(detected,monkeypatch):
    from modules import face_analyser
    monkeypatch.setattr(research,'JOB_LOCK',threading.Lock())
    monkeypatch.setattr(research,'require_models',lambda:None)
    monkeypatch.setattr(research,'configure_runtime',lambda:None)
    monkeypatch.setattr(face_analyser,'get_one_face',lambda frame:None)
    with pytest.raises(ValueError,match='No face detected'):
        live_camera.capture_identity(detected)
    assert not research.JOB_LOCK.locked()
    with pytest.raises(ValueError,match='Start the webcam'):
        live_camera.capture_identity(None)


def test_busy_export_does_not_block_live_detection(detected,monkeypatch):
    lock=threading.Lock()
    lock.acquire()
    monkeypatch.setattr(research,'JOB_LOCK',lock)
    try:
        output,status=live_camera.process_frame(detected,'Swap face',{'embedding':np.ones(512)})
        assert output is not None and 'Another experiment' in status
    finally:
        lock.release()


def test_live_swap_uses_captured_identity_and_current_face(detected,monkeypatch):
    from modules.processors.frame import face_swapper
    monkeypatch.setattr(research,'JOB_LOCK',threading.Lock())
    monkeypatch.setattr(research,'require_models',lambda:None)
    monkeypatch.setattr(research,'configure_runtime',lambda:None)
    swap=Mock(side_effect=lambda source,target,frame:frame)
    monkeypatch.setattr(face_swapper,'swap_face',swap)
    identity={'embedding':np.ones(512,dtype=np.float32)}
    output,status=live_camera.process_frame(detected,'Swap face',identity)
    assert output is not None and 'identity applied' in status
    source,target,frame=swap.call_args.args
    np.testing.assert_array_equal(source.embedding,identity['embedding'])
    np.testing.assert_array_equal(target.kps,observation()['kps'])


def test_browser_opens_live_with_webcam_only_input():
    import pytest
    pytest.importorskip("gradio", reason="Optional legacy Gradio UI is excluded from the maintained Studio production dependencies")
    from app import build_app
    config=build_app().get_config_file()
    tabs=[c['props'].get('label') for c in config['components'] if c['type']=='tabitem']
    assert tabs[0]=='Live webcam'
    cameras=[c for c in config['components'] if c['type']=='image' and c['props'].get('sources')==['webcam']]
    assert len(cameras)==1 and cameras[0]['props']['streaming']
    stream=next(d for d in config['dependencies'] if d.get('api_name')=='live_frame')
    assert stream['trigger_mode']=='always_last'
    capture=next(d for d in config['dependencies'] if d.get('api_name')=='capture_webcam_face')
    latest_frame_id=stream['outputs'][-1]
    assert capture['inputs']==[latest_frame_id]
    assert next(c for c in config['components'] if c['id']==latest_frame_id)['type']=='state'


def test_desktop_live_opens_without_a_source_photo(monkeypatch):
    import modules.globals as state
    from modules import ui
    monkeypatch.setattr(state,'source_path',None)
    monkeypatch.setattr(state,'map_faces',False)
    monkeypatch.setattr(ui,'_LIVE_MAPPER',None)
    open_preview=Mock()
    monkeypatch.setattr(ui,'_open_webcam_preview',open_preview)
    window=SimpleNamespace(cb_camera=SimpleNamespace(currentIndex=lambda:0),_camera_indices=[0])
    ui.MainWindow._on_live(window)
    open_preview.assert_called_once_with(0)
