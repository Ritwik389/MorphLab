"""Isolated web inference: immutable configuration, validated native CoreML, no CLI globals."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from modules.paths import MODELS_DIR, ROOT_DIR


@dataclass(frozen=True)
class RuntimeConfig:
    device: str = "auto"
    threads: int = 2
    shape: tuple = (1, 3, 128, 128)
    precision: str | None = None
    tracking_model: str = "auto"


class InferenceScheduler:
    """One inference at a time; queued live work takes priority over the next export frame."""

    def __init__(self):
        self.condition = threading.Condition()
        self.busy = False
        self.live_waiters = 0
        self.live_sessions = 0

    def camera(self, delta):
        with self.condition:
            self.live_sessions = max(0, self.live_sessions + delta)
            self.condition.notify_all()

    @contextmanager
    def use(self, live=False, cancelled=lambda: False):
        with self.condition:
            if live:
                self.live_waiters += 1
            try:
                while self.busy or (
                    not live and (self.live_waiters or self.live_sessions)
                ):
                    if cancelled():
                        raise InterruptedError("Job cancelled.")
                    self.condition.wait(0.05)
                if cancelled():
                    raise InterruptedError("Job cancelled.")
                self.busy = True
            finally:
                if live:
                    self.live_waiters -= 1
        try:
            yield
        finally:
            with self.condition:
                self.busy = False
                self.condition.notify_all()


class ModelRegistry:
    def __init__(self, config=None):
        self.config = config or RuntimeConfig(
            device=os.getenv("AIMS_EXECUTION_PROVIDER", "auto").lower(),
            tracking_model=os.getenv("AIMS_LIVE_TRACKING", "auto"),
        )
        self.lock = threading.RLock()
        self.scheduler = InferenceScheduler()
        self.detector = self.recognizer = self.swapper = self.landmarker = None
        self.emap = None
        self.state = "idle"
        self.active = None
        self.reason = None
        self.manifest = None
        self.mobile = None
        self.live_runtime = None
        self.live_note = None
        self.live_detector = self.live_recognizer = None
        self.live_tracking_kind = None
        self.tracking_hashes = None
        self.live_model_manifest = None

    def status(self):
        import onnxruntime as ort

        apple = platform.system() == "Darwin" and platform.machine() == "arm64"
        return {
            "os": platform.system(),
            "architecture": platform.machine(),
            "apple_silicon": apple,
            "available_providers": ort.get_available_providers(),
            "requested_device": self.config.device,
            "active_runtime": self.active,
            "state": self.state,
            "fallback_reason": self.reason,
            "model": "inswapper_128" if self.active else None,
            "benchmark": self.manifest,
            "performance_target_fps": 15,
            "live_runtime": self.live_runtime,
            "live_note": self.live_note,
            "live_tracking": self.live_tracking_kind,
            "live_tracking_hashes": self.tracking_hashes,
            "live_model_manifest": self.live_model_manifest,
            "hardware_location": "server",
            "active_live_sessions": self.scheduler.live_sessions,
        }

    def _options(self):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = self.config.threads
        options.log_severity_level = 3
        return options

    def memory_status(self):
        import psutil

        result = {
            "process_rss_mb": psutil.Process(os.getpid()).memory_info().rss / 1024**2
        }
        if self.mobile is not None:
            import torch

            if torch.backends.mps.is_available():
                result["mps_tensors_mb"] = (
                    torch.mps.current_allocated_memory() / 1024**2
                )
                result["mps_driver_mb"] = torch.mps.driver_allocated_memory() / 1024**2
        return result

    def detect(self, frame, recognition=False):
        import onnxruntime as ort
        from insightface.model_zoo.retinaface import RetinaFace
        from insightface.app.common import Face

        with self.lock:
            if self.detector is None:
                path = Path(MODELS_DIR) / "insightface/models/buffalo_l/det_10g.onnx"
                if not path.is_file():
                    raise ValueError(
                        "Face models are missing. Run scripts/download_models.py first."
                    )
                session = ort.InferenceSession(
                    str(path),
                    sess_options=self._options(),
                    providers=["CPUExecutionProvider"],
                )
                self.detector = RetinaFace(model_file=str(path), session=session)
                self.detector.prepare(ctx_id=-1, input_size=(320, 320), det_thresh=0.5)
            boxes, points = self.detector.detect(
                frame, input_size=(320, 320), max_num=0
            )
            faces = [
                Face(bbox=box[:4], kps=points[i], det_score=float(box[4]))
                for i, box in enumerate(boxes)
            ]
            if recognition:
                for face in faces:
                    face.embedding = self.embedding(frame, face)
            return faces

    def embedding(self, frame, face):
        import onnxruntime as ort
        from insightface.model_zoo.arcface_onnx import ArcFaceONNX

        with self.lock:
            if self.recognizer is None:
                path = Path(MODELS_DIR) / "insightface/models/buffalo_l/w600k_r50.onnx"
                session = ort.InferenceSession(
                    str(path),
                    sess_options=self._options(),
                    providers=["CPUExecutionProvider"],
                )
                self.recognizer = ArcFaceONNX(model_file=str(path), session=session)
                self.recognizer.prepare(ctx_id=-1)
            return self.recognizer.get(frame, face).copy()

    def _prepare_live_tracking(self):
        """Select one appearance space per runtime; never mix MBF and R50 tracks."""
        if self.live_tracking_kind is not None:
            return
        if self.config.tracking_model == "standard":
            self.live_tracking_kind = (
                "SCRFD-10GF + ArcFace R50 · CPU · explicitly selected"
            )
            return
        if self.config.tracking_model not in {"auto", "light"}:
            raise ValueError("Tracking model must be auto, light, or standard.")
        import onnxruntime as ort
        from insightface.model_zoo.retinaface import RetinaFace
        from insightface.model_zoo.arcface_onnx import ArcFaceONNX

        with self.lock:
            if self.live_tracking_kind is not None:
                return
            directory = Path(MODELS_DIR) / "insightface/models/buffalo_sc"
            try:
                pins = json.loads(
                    (Path(ROOT_DIR) / "models-manifest.json").read_text()
                )["models"]
                for name in ["det_500m.onnx", "w600k_mbf.onnx"]:
                    expected = next(
                        m["sha256"]
                        for m in pins
                        if m["path"].endswith("buffalo_sc/" + name)
                    )
                    with (directory / name).open("rb") as stream:
                        if (
                            hashlib.file_digest(stream, "sha256").hexdigest()
                            != expected
                        ):
                            raise ValueError("Live tracking model checksum mismatch.")
                path = directory / "det_500m.onnx"
                self.live_detector = RetinaFace(
                    model_file=str(path),
                    session=ort.InferenceSession(
                        str(path),
                        sess_options=self._options(),
                        providers=["CPUExecutionProvider"],
                    ),
                )
                self.live_detector.prepare(
                    ctx_id=-1, input_size=(320, 320), det_thresh=0.5
                )
                path = directory / "w600k_mbf.onnx"
                self.live_recognizer = ArcFaceONNX(
                    model_file=str(path),
                    session=ort.InferenceSession(
                        str(path),
                        sess_options=self._options(),
                        providers=["CPUExecutionProvider"],
                    ),
                )
                self.live_recognizer.prepare(ctx_id=-1)
                self.live_tracking_kind = (
                    "SCRFD-500MF + MobileFaceNet · CPU · 320px detection"
                )
                self.tracking_hashes = {
                    m["path"]: m["sha256"] for m in pins if "buffalo_sc/" in m["path"]
                }
            except FileNotFoundError:
                self.live_tracking_kind = (
                    "SCRFD-10GF + ArcFace R50 · CPU fallback (light weights absent)"
                )
                self.live_note = "Install verified lightweight tracking weights with scripts/download_models.py for faster live recovery."

    def live_detect(self, frame):
        from insightface.app.common import Face

        self._prepare_live_tracking()
        if self.live_detector is None:
            return self.detect(frame)
        with self.lock:
            boxes, points = self.live_detector.detect(
                frame, input_size=(320, 320), max_num=0
            )
        return [
            Face(bbox=b[:4], kps=points[i], det_score=float(b[4]))
            for i, b in enumerate(boxes)
        ]

    def live_embedding(self, frame, face):
        self._prepare_live_tracking()
        if self.live_recognizer is None:
            return self.embedding(frame, face)
        with self.lock:
            value = self.live_recognizer.get(frame, face).copy()
        if not np.isfinite(value).all() or np.linalg.norm(value) < 1e-8:
            raise ValueError("Live appearance model returned invalid features.")
        return value

    def landmarks(self, frame, face):
        """Refresh dense geometry on this frame; never reuse stale landmark outputs."""
        import onnxruntime as ort
        from insightface.model_zoo.landmark import Landmark

        with self.lock:
            if self.landmarker is None:
                path = Path(MODELS_DIR) / "insightface/models/buffalo_l/2d106det.onnx"
                self.landmarker = Landmark(
                    model_file=str(path),
                    session=ort.InferenceSession(
                        str(path),
                        sess_options=self._options(),
                        providers=["CPUExecutionProvider"],
                    ),
                )
                self.landmarker.prepare(ctx_id=-1)
            points = np.asarray(self.landmarker.get(frame, face), np.float32)
        if points.shape != (106, 2) or not np.isfinite(points).all():
            raise ValueError("Face geometry is not reliable on this frame.")
        face.landmark_2d_106 = points
        # The model's documented 106-point topology: eye centres, nose tip, mouth corners.
        anchors = points[[38, 88, 86, 52, 61]].copy()
        anchors[:2] = anchors[:2][np.argsort(anchors[:2, 0])]
        anchors[3:] = anchors[3:][np.argsort(anchors[3:, 0])]
        if np.linalg.norm(anchors[0] - anchors[1]) < 4:
            raise ValueError("Move closer so both eyes are visible.")
        face.kps = anchors
        return points

    def prepare(self):
        with self.lock:
            if self.swapper is not None:
                return self.status()
            self.state = "warming"
            try:
                blob = np.full(self.config.shape, 0.5, np.float32)
                latent = np.ones((1, 512), np.float32) / np.sqrt(512)
                try:
                    self._load_swapper()
                    result = self._infer(blob, latent)
                    if (
                        result.shape != self.config.shape
                        or not np.isfinite(result).all()
                    ):
                        raise RuntimeError("Accelerated model failed its output check.")
                except Exception as accelerated_error:
                    if self.config.device == "cpu":
                        raise
                    self.reason = (
                        f"Accelerated warmup failed; using CPU: {accelerated_error}"
                    )
                    self.swapper = None
                    self.manifest = None
                    self._load_swapper(force_cpu=True)
                result = self._infer(blob, latent)
                if result.shape != self.config.shape or not np.isfinite(result).all():
                    raise RuntimeError("Model failed its warmup output check.")
                self.state = "ready"
            except Exception as exc:
                self.swapper = None
                self.active = None
                self.state = "error"
                self.reason = str(exc)
                raise
            return self.status()

    def _load_swapper(self, force_cpu=False):
        import onnx
        import onnxruntime as ort

        path = Path(MODELS_DIR) / "inswapper_128.onnx"
        if not path.exists():
            raise ValueError(
                "Swap weights are missing. Run scripts/download_models.py."
            )
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        apple = platform.system() == "Darwin" and platform.machine() == "arm64"
        candidates = []
        if not force_cpu and apple and self.config.device in {"auto", "coreml"}:
            try:
                import coremltools as ct

                for file in (Path(ROOT_DIR) / ".cache/coreml").glob("*/manifest.json"):
                    item = json.loads(file.read_text())
                    if (
                        item.get("validated")
                        and item.get("model_sha256") == digest
                        and (
                            self.config.precision is None
                            or item.get("precision") == self.config.precision
                        )
                        and item.get("shape") == list(self.config.shape)
                        and item.get("converter") == 2
                        and item.get("coremltools") == ct.__version__
                        and item.get("arch") == platform.machine()
                        and item.get("macos") == platform.mac_ver()[0]
                    ):
                        candidates.append((item["mean_ms"], file, item))
                for _, file, item in sorted(candidates):
                    try:
                        self.swapper = ct.models.MLModel(
                            str(file.parent / "swapper.mlpackage"),
                            compute_units=ct.ComputeUnit.ALL,
                        )
                        self.emap = np.load(
                            file.parent / "emap.npy", allow_pickle=False
                        )
                        self.active = f"Native CoreML · {item['precision'].upper()} · GPU / Neural Engine eligible"
                        self.manifest = item
                        return
                    except Exception as exc:
                        self.reason = f"Native CoreML could not load: {exc}"
                self.reason = (
                    self.reason
                    or "No validated native CoreML model. Run scripts/convert_coreml.py."
                )
            except ImportError:
                self.reason = "Native CoreML tools are not installed."
        available = ort.get_available_providers()
        device = "cpu" if force_cpu else self.config.device
        if device not in {"auto", "cpu", "coreml", "cuda"}:
            raise ValueError("Device must be auto, cpu, coreml, or cuda.")
        providers = ["CPUExecutionProvider"]
        if device in {"auto", "cuda"} and "CUDAExecutionProvider" in available:
            providers.insert(0, "CUDAExecutionProvider")
        elif (
            apple
            and device in {"auto", "coreml"}
            and "CoreMLExecutionProvider" in available
        ):
            from modules.onnx_optimize import optimize_for_coreml

            optimized = optimize_for_coreml(str(path), self.config.shape)
            cache = Path(ROOT_DIR) / ".cache/ort-coreml" / digest[:16]
            cache.mkdir(parents=True, exist_ok=True)
            providers.insert(
                0,
                (
                    "CoreMLExecutionProvider",
                    {
                        "ModelFormat": "MLProgram",
                        "MLComputeUnits": "ALL",
                        "ModelCacheDirectory": str(cache),
                    },
                ),
            )
            path = Path(optimized)
        self.swapper = ort.InferenceSession(
            str(path), sess_options=self._options(), providers=providers
        )
        self.active = "ONNX Runtime · " + " + ".join(self.swapper.get_providers())
        self.emap = onnx.numpy_helper.to_array(
            onnx.load(str(path)).graph.initializer[-1]
        )
        if (
            device == "cuda"
            and "CUDAExecutionProvider" not in self.swapper.get_providers()
        ):
            self.reason = "CUDA is unavailable; using CPU."

    def _infer(self, blob, latent):
        if self.active.startswith("Native CoreML"):
            return np.asarray(
                next(
                    iter(
                        self.swapper.predict(
                            {"target": blob, "source": latent}
                        ).values()
                    )
                ),
                np.float32,
            )
        names = [x.name for x in self.swapper.get_inputs()]
        return self.swapper.run(None, {names[0]: blob, names[1]: latent})[0]

    def source(self, frame):
        faces = self.detect(frame)
        if len(faces) != 1:
            raise ValueError(
                "Use a source with exactly one clear face."
                if faces
                else "No face detected in source. Try a clear portrait."
            )
        face = faces[0]
        embedding = self.embedding(frame, face)
        self.prepare()
        latent = (embedding / max(1e-8, np.linalg.norm(embedding))).reshape(
            1, -1
        ) @ self.emap
        latent /= max(1e-8, np.linalg.norm(latent))
        return np.asarray(latent, np.float32)

    def live_source(self, frame):
        """The lighter live model is selected only after a local parity/performance check."""
        if (
            self.config.device == "auto"
            and os.getenv("AIMS_LIVE_MODEL", "auto") != "inswapper"
        ):
            try:
                import torch

                directory = Path(MODELS_DIR) / "mobilefaceswap"
                file = directory / "manifest.json"
                if torch.backends.mps.is_available() and file.is_file():
                    item = json.loads(file.read_text())
                    if (
                        item.get("validated")
                        and item.get("port_version") == 1
                        and item.get("torch") == torch.__version__
                        and item.get("macos") == platform.mac_ver()[0]
                        and item.get("p95_ms", 1000) < 55
                    ):
                        from modules.mobile_model import MobileRuntime

                        with self.lock:
                            if self.mobile is None:
                                for filename, expected in item["weights"].items():
                                    if filename not in {
                                        "arcface.pdparams",
                                        "MobileFaceSwap_224.pdparams",
                                    }:
                                        raise ValueError(
                                            "Invalid mobile checkpoint manifest."
                                        )
                                    with (directory / filename).open("rb") as stream:
                                        if (
                                            hashlib.file_digest(
                                                stream, "sha256"
                                            ).hexdigest()
                                            != expected
                                        ):
                                            raise ValueError(
                                                "Mobile checkpoint checksum mismatch."
                                            )
                                self.mobile = MobileRuntime(directory, "mps")
                            faces = self.detect(frame)
                            if len(faces) != 1:
                                raise ValueError(
                                    "Use a source with exactly one clear face."
                                    if faces
                                    else "No face detected in source. Try a clear portrait."
                                )
                            model = self.mobile.source(frame, faces[0])
                            self.mobile.predict(frame, faces[0], model)
                            self.live_runtime = "MobileFaceSwap 224 · Apple GPU / MPS"
                            self.live_model_manifest = {
                                "weights": item["weights"],
                                "port_version": item["port_version"],
                                "torch": item["torch"],
                            }
                            return {"model": model, "kind": "mobile"}
            except ImportError:
                self.live_note = "Optional mobile runtime is not installed; using the standard swapper."
            except RuntimeError as exc:
                self.live_note = (
                    f"Mobile GPU warmup failed; using the standard swapper: {exc}"
                )
        latent = self.source(frame)
        self.live_runtime = "INSwapper 128 · " + self.active
        return latent

    def live_swap(self, frame, face, identity, timings=None):
        if isinstance(identity, dict) and identity.get("kind") == "mobile":
            fake, transform, mask = self.mobile.predict(
                frame, face, identity["model"], timings
            )
            started = time.perf_counter()
            result = paste_face(
                frame,
                fake,
                transform,
                mask,
                colour_match=self.mobile.mask_mode != "binary",
            )
            if timings is not None:
                timings["composite_ms"] = (time.perf_counter() - started) * 1000
            return result
        return self.swap(frame, face, identity, timings)

    def swap(self, frame, face, latent, timings=None):
        from insightface.utils.face_align import norm_crop2

        started = time.perf_counter()
        crop, transform = norm_crop2(frame, face.kps, 128)
        blob = cv2.dnn.blobFromImage(crop, 1 / 255.0, (128, 128), swapRB=True)
        aligned = time.perf_counter()
        output = self._infer(blob, latent)
        generated = time.perf_counter()
        if not np.isfinite(output).all():
            raise RuntimeError("Model produced an invalid frame.")
        fake = np.clip(output[0].transpose(1, 2, 0)[:, :, ::-1] * 255, 0, 255).astype(
            np.uint8
        )
        result = paste_face(frame, fake, transform)
        if timings is not None:
            timings.update(
                alignment_ms=(aligned - started) * 1000,
                generator_ms=(generated - aligned) * 1000,
                composite_ms=(time.perf_counter() - generated) * 1000,
            )
        return result


_MASK = np.zeros((128, 128), np.float32)
cv2.ellipse(_MASK, (64, 64), (56, 56), 0, 0, 360, 1, -1)
_MASK = cv2.GaussianBlur(_MASK, (21, 21), 5)


def paste_face(frame, fake, transform, mask=None, colour_match=False):
    inv = cv2.invertAffineTransform(transform)
    size = fake.shape[0]
    corners = (
        np.array([[0, 0, 1], [size, 0, 1], [size, size, 1], [0, size, 1]], np.float32)
        @ inv.T
    )
    h, w = frame.shape[:2]
    x1, y1 = np.maximum(0, np.floor(corners.min(axis=0))).astype(int)
    x2, y2 = np.minimum([w, h], np.ceil(corners.max(axis=0))).astype(int)
    if x2 <= x1 or y2 <= y1:
        return frame
    inv[:, 2] -= [x1, y1]
    fake_roi = cv2.warpAffine(fake, inv, (x2 - x1, y2 - y1))
    alpha = np.clip(
        cv2.warpAffine(_MASK if mask is None else mask, inv, (x2 - x1, y2 - y1)), 0, 1
    )[:, :, None]
    if colour_match and float(alpha.sum()) > 32:
        weights = alpha * (alpha > 0.5)
        count = max(1.0, float(weights.sum()))
        shift = (
            (frame[y1:y2, x1:x2] * weights).sum(axis=(0, 1))
            - (fake_roi * weights).sum(axis=(0, 1))
        ) / count
        fake_roi = np.clip(
            fake_roi.astype(np.float32) + np.clip(shift, -12, 12) * 0.35, 0, 255
        )
    result = frame.copy()
    result[y1:y2, x1:x2] = (
        alpha * fake_roi + (1 - alpha) * frame[y1:y2, x1:x2]
    ).astype(np.uint8)
    return result


registry = ModelRegistry()
