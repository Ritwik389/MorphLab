import hashlib
import io
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from PIL import Image

import modules.globals as state
from modules import capturer, utilities
from modules.processors.frame import core as pipeline
from modules.research import process_image, probe_video


@pytest.fixture(autouse=True)
def preserve_state(monkeypatch):
    values = {k: v.copy() if isinstance(v, (list, dict)) else v
              for k, v in vars(state).items() if not k.startswith('__')}
    yield
    for k, v in values.items():
        setattr(state, k, v)


@pytest.mark.parametrize('path, expected', [(None, False), ('x.bmp', True),
    ('x.GIF', True), ('x.webp', True), ('x.notpng', False), ('x.mp4', False)])
def test_image_extensions(path, expected):
    assert utilities.has_image_extension(path) is expected


def test_optional_output_directory_does_not_crash():
    assert utilities.normalize_output_path('source.png', 'target.png', None) is None


def test_model_provenance_does_not_become_a_gradio_file_download():
    from gradio_client.utils import traverse, is_file_obj
    metadata = utilities.model_provenance()
    traverse(metadata, lambda value: pytest.fail('model metadata was treated as a downloadable file'), is_file_obj)
    assert metadata['weights']['inswapper_128.onnx']['sha256']


def test_frame_paths_are_numeric_and_distinguish_containers(tmp_path, monkeypatch):
    target = str(tmp_path / 'clip.mp4')
    directory = Path(utilities.get_temp_directory_path(target))
    directory.mkdir(parents=True)
    for name in ['10000.png', '0002.png', '9999.png']:
        (directory / name).touch()
    assert [Path(p).name for p in utilities.get_temp_frame_paths(target)] == ['0002.png', '9999.png', '10000.png']
    assert utilities.get_temp_directory_path(target) != utilities.get_temp_directory_path(str(tmp_path/'clip.mkv'))


def test_incomplete_model_is_not_cached(tmp_path, monkeypatch):
    response = io.BytesIO(b'partial')
    response.headers = {'Content-Length': '100'}
    monkeypatch.setattr(utilities.urllib.request, 'urlopen', lambda *a, **kw: response)
    with pytest.raises(OSError, match='Incomplete'):
        utilities.conditional_download(str(tmp_path), ['https://models.example/model.onnx'])
    assert list(tmp_path.iterdir()) == []


def test_model_hash_and_tls_are_verified(tmp_path, monkeypatch):
    payload = b'complete model'
    response = io.BytesIO(payload)
    response.headers = {'Content-Length': str(len(payload))}
    def open_url(url, **kwargs):
        assert kwargs['context'].check_hostname
        assert kwargs['context'].verify_mode != 0
        return response
    monkeypatch.setattr(utilities.urllib.request, 'urlopen', open_url)
    utilities.conditional_download(str(tmp_path), ['https://models.example/model.onnx'],
                                  {'model.onnx': hashlib.sha256(payload).hexdigest()})
    assert (tmp_path/'model.onnx').read_bytes() == payload
    if os.name != 'nt':
        # A read-only bind mount must be readable by the container's different UID.
        mode = stat.S_IMODE((tmp_path/'model.onnx').stat().st_mode)
        assert mode & stat.S_IROTH
        assert not mode & (stat.S_IWGRP | stat.S_IWOTH)


def test_bad_model_hash_is_not_published(tmp_path, monkeypatch):
    response = io.BytesIO(b'wrong')
    response.headers = {}
    monkeypatch.setattr(utilities.urllib.request, 'urlopen', lambda *a, **kw: response)
    with pytest.raises(OSError, match='SHA-256'):
        utilities.conditional_download(str(tmp_path), ['https://models.example/model.onnx'], {'model.onnx': '0'*64})
    assert not (tmp_path/'model.onnx').exists()


def test_preview_uses_zero_based_frame_index(monkeypatch):
    capture = Mock()
    capture.get.return_value = 10
    capture.read.return_value = (True, np.zeros((2, 2, 3), np.uint8))
    monkeypatch.setattr(capturer.cv2, 'VideoCapture', lambda _: capture)
    capturer.get_video_frame('clip.mp4', 9)
    capture.set.assert_any_call(cv2.CAP_PROP_POS_FRAMES, 9)
    capturer.get_video_frame('clip.mp4', 0)
    capture.set.assert_any_call(cv2.CAP_PROP_POS_FRAMES, 0)


def make_video(path, fps=12, audio=False):
    command = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=red:s=96x96:r={fps}:d=1']
    if audio:
        command += ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:a', 'aac']
    subprocess.run(command + ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path)], check=True)


def test_pipe_preserves_duration_when_converting_fps(tmp_path):
    source, output = tmp_path/'source.mp4', tmp_path/'output.mp4'
    make_video(source, fps=12)
    state.execution_threads = 1
    assert pipeline._run_pipe_pipeline(str(source), str(output), 30, None, [], 96, 96, 96*96*3, 30,
                                       'libx264', ['-crf', '23'])
    assert utilities.detect_fps(str(output)) == 30
    assert abs(probe_video(str(output))['duration_seconds'] - 1) < .08
    capture = cv2.VideoCapture(str(output))
    assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == 30
    capture.release()


def test_pipe_does_not_reuse_previous_frame_detection(tmp_path, monkeypatch):
    source, output = tmp_path/'source.mp4', tmp_path/'output.mp4'
    make_video(source, fps=3)
    faces = iter([object(), object(), object()])
    detected, received = [], []
    def detect(frame):
        face = next(faces)
        detected.append(face)
        return face
    def process(source, frame, target_face=None):
        received.append(target_face)
        return frame
    monkeypatch.setattr(pipeline, 'get_one_face', detect)
    assert pipeline._run_pipe_pipeline(str(source), str(output), 3, None,
        [SimpleNamespace(process_frame=process)], 96, 96, 96*96*3, 3, 'libx264', [])
    assert received == detected and len(received) == 3


def test_pipe_rejects_failed_decoder(tmp_path):
    assert not pipeline._run_pipe_pipeline(str(tmp_path/'absent.mp4'), str(tmp_path/'out.mp4'), 30,
        None, [], 96, 96, 96*96*3, 0, 'libx264', [])


def test_worker_errors_propagate():
    state.execution_threads = 2
    def broken(*args):
        raise RuntimeError('failed frame')
    with pytest.raises(RuntimeError, match='failed frame'):
        pipeline.multi_process_frame('source', ['a.png'], broken)


def test_temporal_frames_run_in_order():
    state.execution_threads = 4
    state.enable_interpolation = True
    state.interpolation_weight = .5
    received = []
    pipeline.multi_process_frame('source', ['a', 'b', 'c'], lambda _, paths, p: received.append(paths))
    assert received == [['a', 'b', 'c']]


def test_processor_selection_updates(monkeypatch):
    monkeypatch.setattr(pipeline, 'FRAME_PROCESSORS_MODULES', [])
    monkeypatch.setattr(pipeline, 'load_frame_processor_module',
                        lambda name: SimpleNamespace(__name__='modules.processors.frame.'+name))
    state.fp_ui = {}
    assert pipeline.get_frame_processors_modules(['face_swapper'])[0].__name__.endswith('face_swapper')
    assert pipeline.get_frame_processors_modules(['face_enhancer'])[0].__name__.endswith('face_enhancer')


def test_missing_permission_and_missing_face_are_errors():
    image = Image.new('RGB', (128, 128))
    with pytest.raises(ValueError, match='permission'):
        process_image(None, image, 'Blur faces')
    with pytest.raises(ValueError, match='No frontal faces'):
        process_image(None, image, 'Blur faces', consent=True)


def test_model_free_anonymization_has_provenance(tmp_path, monkeypatch):
    from modules import research
    monkeypatch.setattr(research, 'OUTPUT_ROOT', tmp_path)
    target = Image.open(Path(__file__).parents[1]/'assets/examples/target.jpg')
    comparison, output, report, metrics = process_image(None, target, 'Pixelate faces', consent=True)
    assert metrics['faces_edited'] >= 1
    assert metrics['mean_absolute_pixel_change_0_255'] > 0
    assert Path(report).exists() and Path(output).exists()
    assert metrics['output_sha256'] == utilities.file_sha256(output)
    assert not np.array_equal(*comparison)


def test_output_cannot_overwrite_target(tmp_path):
    from modules import core
    target = tmp_path/'target.bmp'
    Image.new('RGB', (128,128)).save(target)
    state.target_path = state.output_path = str(target)
    with pytest.raises(ValueError, match='differ'):
        core.start()


def test_failed_image_export_preserves_existing_output(tmp_path, monkeypatch):
    from modules import core
    target, output = tmp_path/'target.bmp', tmp_path/'output.png'
    Image.new('RGB', (128,128)).save(target)
    output.write_bytes(b'existing output')
    state.target_path, state.output_path = str(target), str(output)
    state.source_path = None
    state.frame_processors = ['face_enhancer']
    state.nsfw_filter = False
    processor = SimpleNamespace(NAME='broken', pre_check=lambda: True, pre_start=lambda: True,
                                process_image=lambda *a: None)
    monkeypatch.setattr(core, 'get_frame_processors_modules', lambda _: [processor])
    with pytest.raises(RuntimeError, match='did not produce'):
        core.start()
    assert output.read_bytes() == b'existing output'


def test_audio_is_preserved_and_silent_video_succeeds(tmp_path):
    for audio in [False, True]:
        source = tmp_path/f'source-{audio}.mp4'
        make_video(source, audio=audio)
        utilities.create_temp(str(source))
        shutil_copy = __import__('shutil').copyfile
        shutil_copy(source, utilities.get_temp_output_path(str(source)))
        output = tmp_path/f'output-{audio}.mp4'
        utilities.restore_audio(str(source), str(output))
        assert output.stat().st_size > 0
        import json
        data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)]))
        assert any(s['codec_type']=='audio' for s in data['streams']) is audio
