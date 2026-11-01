"""Live browser camera processing; detection never needs a source photograph."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np

from modules.paths import INSIGHTFACE_ROOT

MODES = ['Detect faces', 'Blur faces', 'Pixelate faces', 'Swap face']
_DETECTOR = None
_DETECTOR_LOCK = threading.Lock()


def camera_frame(value):
    """Bound transport/inference cost while preserving the camera's aspect ratio."""
    if value is None:
        return None
    rgb = np.asarray(value)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.size:
        raise ValueError('Camera must supply an RGB frame.')
    if rgb.shape[0] * rgb.shape[1] > 16_000_000:
        raise ValueError('Camera frame is too large.')
    if rgb.dtype != np.uint8:
        raise ValueError('Camera must supply an 8-bit RGB frame.')
    scale = min(1., 640 / rgb.shape[1], 480 / rgb.shape[0])
    if scale < 1:
        rgb = cv2.resize(rgb, (max(1, round(rgb.shape[1] * scale)),
                               max(1, round(rgb.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def detect_faces(frame):
    """Use the installed detector alone; no recognition or swap model is loaded."""
    global _DETECTOR
    model_path = Path(INSIGHTFACE_ROOT) / 'models' / 'buffalo_l' / 'det_10g.onnx'
    with _DETECTOR_LOCK:
        if model_path.is_file():
            if _DETECTOR is None:
                import insightface
                import onnxruntime
                options = onnxruntime.SessionOptions()
                options.intra_op_num_threads = 2
                # The model supports dynamic input sizes, but its output metadata
                # lists 640px anchor counts. Avoid repeating benign 320px warnings.
                options.log_severity_level = 3
                _DETECTOR = insightface.model_zoo.get_model(str(model_path),
                    providers=['CPUExecutionProvider'], sess_options=options)
                _DETECTOR.prepare(ctx_id=-1, input_size=(320, 320), det_thresh=.5)
            boxes, points = _DETECTOR.detect(frame, input_size=(320, 320), max_num=0)
            observations = [{'bbox': box[:4], 'score': float(box[4]),
                             'kps': points[i] if points is not None else None}
                            for i, box in enumerate(boxes)]
            return observations, 'InsightFace detector'
        # Detection still works on a fresh install without any downloaded models.
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        boxes = cascade.detectMultiScale(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                                         scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        return [{'bbox': np.array([x, y, x+w, y+h]), 'score': None, 'kps': None}
                for x, y, w, h in boxes], 'OpenCV frontal-face detector'


def draw_detections(frame, observations):
    result = frame.copy()
    h, w = result.shape[:2]
    for i, observation in enumerate(observations):
        x1, y1, x2, y2 = np.asarray(observation['bbox']).astype(int)
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w-1, x2), min(h-1, y2)
        if x1 >= x2 or y1 >= y2:
            continue
        cv2.rectangle(result, (x1, y1), (x2, y2), (40, 210, 75), 2)
        text = f'Face {i+1}'
        cv2.putText(result, text, (x1, max(16, y1-7)), cv2.FONT_HERSHEY_SIMPLEX,
                    .5, (40, 210, 75), 1, cv2.LINE_AA)
    return result


def capture_identity(value):
    """Capture one face as session-local arrays; never write its image to disk."""
    from modules import research
    frame = camera_frame(value)
    if frame is None:
        raise ValueError('Start the webcam first, then click Capture face from webcam.')
    if not research.JOB_LOCK.acquire(blocking=False):
        raise ValueError('Another experiment is running. Try capturing again when it finishes.')
    try:
        research.require_models()
        research.configure_runtime()
        from modules.face_analyser import get_one_face
        face = get_one_face(frame)
        if face is None:
            raise ValueError('No face detected. Face the camera and try capturing again.')
        x1, y1, x2, y2 = np.asarray(face.bbox).astype(int)
        h, w = frame.shape[:2]
        crop = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if not crop.size:
            raise ValueError('The detected face is outside the camera frame. Try again.')
        # Plain arrays avoid InsightFace's custom attribute/deepcopy behavior in gr.State.
        identity = {'embedding': np.asarray(face.embedding).copy()}
        preview = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        return identity, preview, 'Webcam face captured. You can now use Swap face.'
    finally:
        research.JOB_LOCK.release()


def process_frame(value, mode='Detect faces', identity=None):
    started = time.perf_counter()
    if mode not in MODES:
        raise ValueError('Select a supported live mode.')
    frame = camera_frame(value)
    if frame is None:
        return None, 'Start the webcam to detect faces automatically.'
    observations, detector = detect_faces(frame)
    count = len(observations)
    message = f'{count} face{"s" if count != 1 else ""} detected'
    if mode in {'Blur faces', 'Pixelate faces'}:
        h, w = frame.shape[:2]
        for observation in observations:
            x1, y1, x2, y2 = np.asarray(observation['bbox']).astype(int)
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            if mode == 'Pixelate faces':
                roi[:] = cv2.resize(cv2.resize(roi, (8, 8), interpolation=cv2.INTER_AREA),
                                    (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)
            else:
                roi[:] = cv2.GaussianBlur(roi, (0, 0), max(12, (x2-x1)/5))
    elif mode == 'Swap face' and count:
        from modules import research
        if identity is None:
            message += ' · Capture a webcam face below to enable swapping.'
        elif not research.JOB_LOCK.acquire(blocking=False):
            message += ' · Another experiment is running; showing detection.'
        else:
            try:
                research.require_models()
                research.configure_runtime()
                from insightface.app.common import Face
                from modules.processors.frame.face_swapper import swap_face
                target = min(observations, key=lambda observation: observation['bbox'][0])
                if target['kps'] is None:
                    message += ' · Install neural model weights to enable swapping.'
                else:
                    source = Face(embedding=identity['embedding'])
                    target_face = Face(bbox=np.asarray(target['bbox']), kps=np.asarray(target['kps']),
                                       det_score=target['score'])
                    frame = research.watermark(swap_face(source, target_face, frame))
                    message += ' · Webcam identity applied.'
            finally:
                research.JOB_LOCK.release()
    frame = draw_detections(frame, observations)
    milliseconds = (time.perf_counter() - started) * 1000
    # This measures backend processing, not camera/network FPS.
    message += f' · {milliseconds:.0f} ms processing · {detector}'
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), message
