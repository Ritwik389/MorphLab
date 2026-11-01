"""Ordered live inference, stable person selection and bounded binary streaming."""

from __future__ import annotations

import json
import struct
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from modules.runtime import registry
from modules.temporal import FaceTracker, scene_changed, stabilize, iou
from modules.research import watermark

MODES = {"detect", "swap", "blur", "pixelate"}


def observe(frame):
    return registry.live_detect(frame), cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def pack_frame(metadata, jpeg):
    header = json.dumps(metadata, separators=(",", ":"), allow_nan=False).encode()
    return struct.pack("!I", len(header)) + header + jpeg


def unpack_frame(packet):
    if len(packet) < 5 or len(packet) > 2_100_000:
        raise ValueError("Invalid frame size.")
    length = struct.unpack("!I", packet[:4])[0]
    if not 0 < length <= 8192 or length + 4 >= len(packet):
        raise ValueError("Invalid frame header.")
    try:
        metadata = json.loads(packet[4 : 4 + length])
    except RecursionError as exc:
        raise ValueError("Frame metadata is nested too deeply.") from exc
    if not isinstance(metadata, dict):
        raise ValueError("Invalid frame metadata.")
    for name in ("frame_id", "revision"):
        if type(metadata.get(name)) is not int or metadata[name] < 0:
            raise ValueError(f"Invalid {name}.")
    if type(metadata.get("captured_at")) not in (float, int) or not np.isfinite(
        metadata["captured_at"]
    ):
        raise ValueError("Invalid capture timestamp.")
    from PIL import Image
    import io

    with Image.open(io.BytesIO(packet[4 + length :])) as image:
        if (
            image.width > 1280
            or image.height > 960
            or image.width * image.height > 1_000_000
        ):
            raise ValueError("Live frames must be at most 1280 × 960 and 1 megapixel.")
        frame = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    return metadata, frame


def erase(value):
    """Best effort on owned buffers. Allocator/driver copies cannot be guaranteed erased."""
    if isinstance(value, np.ndarray):
        value.fill(0)
    elif isinstance(value, dict):
        for item in value.values():
            erase(item)


@dataclass
class LiveSession:
    revision: int = 0
    latent: object = None
    mode: str = "detect"
    selected: int | None = None
    selection_mode: str = "auto"
    target_status: str = "searching"
    target_revision: int = 0
    frame_number: int = 0
    last_frame_id: int = -1
    previous_gray: object = None
    latest: object = None
    touched: float = field(default_factory=time.monotonic)
    lock: object = field(default_factory=threading.RLock)
    tracker: object = field(default_factory=lambda: FaceTracker(max_missed=100000))
    seen: dict = field(default_factory=dict)
    thumbnails: dict = field(default_factory=dict)
    thumbnail_at: dict = field(default_factory=dict)
    last_detection: float = -1e9
    last_recognition: float = -1e9
    detection_interval: float = 0.15
    dense_geometry: bool = True
    motion_prediction: bool = True
    geometry_error: str | None = None
    profile: bool = False
    source_checks: object = None
    clock: object = time.monotonic
    recoveries: int = 0
    geometry: dict = field(default_factory=dict)

    def set_source(self, latent):
        with self.lock:
            erase(self.latent)
            self.latent = latent
            self.revision += 1
            self.touched = self.clock()
            if latent is not None:
                self.mode = "swap"
            return self.revision

    def reset_camera(self):
        with self.lock:
            erase(self.latest)
            erase(self.previous_gray)
            for track in self.tracker.tracks:
                erase(track.appearance)
                erase(getattr(track.face, "embedding", None))
            self.latest = self.previous_gray = None
            self.tracker.reset()
            self.selected = None
            self.selection_mode = "auto"
            self.target_status = "searching"
            self.target_revision += 1
            self.frame_number = 0
            self.last_frame_id = -1
            self.last_detection = -1e9
            self.seen.clear()
            self.thumbnails.clear()
            self.thumbnail_at.clear()
            self.geometry.clear()
            self.source_checks = None

    def control(self, message):
        if not isinstance(message, dict):
            raise ValueError("Invalid camera control.")
        with self.lock:
            if "mode" in message:
                if not isinstance(message["mode"], str) or message["mode"] not in MODES:
                    raise ValueError("Choose a supported live mode.")
                self.mode = message["mode"]
            if "profile" in message:
                if type(message["profile"]) is not bool:
                    raise ValueError("Invalid profiler setting.")
                self.profile = message["profile"]
            if message.get("auto") is True:
                self.selection_mode = "auto"
                self.target_revision += 1
            if "select" in message:
                value = message["select"]
                if type(value) is not int:
                    raise ValueError("Invalid person selection.")
                # A roster thumbnail can outlive its observation. Acknowledge the
                # client's revision without dropping the stream or its current target.
                self.target_revision += 1
                if not any(t.id == value and t.visible for t in self.tracker.tracks):
                    return
                self.selected = value
                self.selection_mode = "manual"
                self.target_status = "tracking"

    def choose(self, tracks, now, width, height):
        for track in tracks:
            self.seen[track.id] = now
        target = next((t for t in tracks if t.id == self.selected), None)
        if target is not None:
            if self.target_status == "reacquiring":
                self.recoveries += 1
            self.target_status = "tracking"
            return target
        if self.selected is not None and now - self.seen.get(self.selected, now) < 2:
            self.target_status = "reacquiring"
            return None
        if not tracks:
            self.target_status = "searching" if self.selected is None else "reacquiring"
            return None

        def priority(track):
            box = track.face.bbox
            area = max(0, box[2] - box[0]) * max(0, box[3] - box[1])
            distance = np.linalg.norm((box[:2] + box[2:]) / 2 - [width / 2, height / 2])
            return (area, -distance, -track.id)

        self.selected = max(tracks, key=priority).id
        self.target_revision += 1
        self.selection_mode = "auto"
        self.target_status = "tracking"
        return next(t for t in tracks if t.id == self.selected)

    def roster(self):
        return [
            {
                "id": t.id,
                "label": f"Person {t.id}",
                "visible": t.visible,
                "thumbnail": f"/api/sessions/{{session}}/people/{t.id}/thumbnail?v={int(self.thumbnail_at.get(t.id, 0))}",
            }
            for t in self.tracker.tracks
            if t.id in self.thumbnails
        ]

    def process(self, metadata, frame):
        start = time.perf_counter()
        stages = {}

        def elapsed(name, since):
            stages[name] = (time.perf_counter() - since) * 1000

        with self.lock:
            if metadata["revision"] != self.revision:
                return None
            frame_id = metadata["frame_id"]
            if frame_id <= self.last_frame_id:
                return None
            self.last_frame_id = frame_id
            now = self.clock()
            self.touched = now
            self.latest = frame.copy()
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            changed = scene_changed(self.previous_gray, gray)
            t0 = time.perf_counter()
            if changed:
                for track in self.tracker.tracks:
                    track.visible = False
                self.geometry.clear()
            reliable = (
                self.motion_prediction
                and not changed
                and self.tracker.predict(self.previous_gray, gray)
            )
            elapsed("optical_flow_ms", t0)
            # Detection, association and geometry all describe THIS frame, in order.
            if not reliable or now - self.last_detection >= self.detection_interval:
                t0 = time.perf_counter()
                faces, _ = observe(frame)
                elapsed("detection_ms", t0)
                t0 = time.perf_counter()
                if len(faces) > 1 or not reliable or now - self.last_recognition >= 1:
                    for face in faces:
                        if getattr(face, "embedding", None) is None:
                            face.embedding = registry.live_embedding(frame, face)
                    self.last_recognition = now
                elapsed("recognition_ms", t0)
                t0 = time.perf_counter()
                tracks = self.tracker.update(faces)
                self.last_detection = now
                elapsed("association_ms", t0)
            else:
                tracks = [t for t in self.tracker.tracks if t.visible]
            # Retain appearance references long enough to reacquire; bound gallery size/lifetime.
            self.tracker.tracks = [
                t
                for t in self.tracker.tracks
                if now - self.seen.get(t.id, now) < 30 or t.id == self.selected
            ][-32:]
            retained = {t.id for t in self.tracker.tracks}
            for mapping in (
                self.seen,
                self.thumbnails,
                self.thumbnail_at,
                self.geometry,
            ):
                for key in list(mapping):
                    if key not in retained:
                        erase(mapping.pop(key))
            target = self.choose(tracks, now, w, h)
            geometry_valid = True
            self.geometry_error = None
            if target is not None and self.dense_geometry:
                t0 = time.perf_counter()
                try:
                    registry.landmarks(frame, target.face)
                    previous = self.geometry.get(target.id)
                    if self.tracker.smooth:
                        target.face.kps = stabilize(previous, target.face.kps)
                    self.geometry[target.id] = target.face.kps.copy()
                except (ValueError, RuntimeError, OSError) as exc:
                    geometry_valid = False
                    self.geometry_error = str(exc)
                    self.target_status = "uncertain"
                    self.last_detection = -1e9
                elapsed("dense_geometry_ms", t0)
            if target is not None and any(
                other.id != target.id and iou(target.face.bbox, other.face.bbox) > 0.25
                for other in tracks
            ):
                # Temporary passthrough prevents painting onto an occluding person.
                # Selection is retained and resumes automatically after separation.
                geometry_valid = False
                self.target_status = "uncertain"
                self.geometry_error = "People overlap; following the selected identity."
            for track in tracks:
                if now - self.thumbnail_at.get(track.id, -1e9) >= 1:
                    x1, y1, x2, y2 = track.face.bbox.astype(int)
                    crop = frame[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]
                    if crop.size:
                        ok, data = cv2.imencode(
                            ".jpg",
                            cv2.resize(crop, (80, 80)),
                            [cv2.IMWRITE_JPEG_QUALITY, 75],
                        )
                        if ok:
                            self.thumbnails[track.id] = data.tobytes()
                            self.thumbnail_at[track.id] = now
            self.previous_gray = gray
            self.frame_number += 1
            result = frame
            swapped = False
            message = (
                f"{len(tracks)} face" + ("" if len(tracks) == 1 else "s") + " detected"
            )
            if self.mode == "swap":
                if self.latent is None:
                    message = "Choose a source identity or capture your camera face."
                elif target is None:
                    message = (
                        "Following your selected person…"
                        if tracks
                        else "Looking for a face…"
                    )
                elif not geometry_valid:
                    message = "Reacquiring clear face geometry…"
                else:
                    t0 = time.perf_counter()
                    with registry.scheduler.use(live=True):
                        elapsed("inference_wait_ms", t0)
                        t0 = time.perf_counter()
                        result = watermark(
                            registry.live_swap(
                                frame,
                                target.face,
                                self.latent,
                                stages if self.profile else None,
                            )
                        )
                        elapsed("alignment_generator_composite_ms", t0)
                    swapped = True
                    message = "Identity applied"
            elif self.mode in {"blur", "pixelate"}:
                result = frame.copy()
                for track in tracks:
                    x1, y1, x2, y2 = track.face.bbox.astype(int)
                    roi = result[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]
                    if roi.size:
                        roi[:] = (
                            cv2.GaussianBlur(roi, (0, 0), max(12, (x2 - x1) / 5))
                            if self.mode == "blur"
                            else cv2.resize(
                                cv2.resize(roi, (8, 8)),
                                (roi.shape[1], roi.shape[0]),
                                interpolation=cv2.INTER_NEAREST,
                            )
                        )
            if not swapped:
                result = result.copy()
                for track in tracks:
                    x1, y1, x2, y2 = track.face.bbox.astype(int)
                    cv2.rectangle(result, (x1, y1), (x2, y2), (230, 100, 50), 2)
                    cv2.putText(
                        result,
                        f"Person {track.id}",
                        (x1, max(18, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (230, 100, 50),
                        1,
                    )
            t0 = time.perf_counter()
            encoded, jpeg = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 85])
            elapsed("output_encode_ms", t0)
            if not encoded:
                raise ValueError("Could not encode camera frame.")
            header = {
                **metadata,
                "protocol_version": 2,
                "swapped": swapped,
                "mode": self.mode,
                "message": message,
                "processing_ms": (time.perf_counter() - start) * 1000,
                "width": w,
                "height": h,
                "faces": [
                    {"id": t.id, "bbox": (t.face.bbox / [w, h, w, h]).tolist()}
                    for t in tracks
                ],
                "selected_face": self.selected,
                "selection_mode": self.selection_mode,
                "target_status": self.target_status,
                "target_revision": self.target_revision,
                "recoveries": self.recoveries,
            }
            if self.profile:
                header["stages"] = stages
                header.update(registry.memory_status())
            return pack_frame(header, jpeg.tobytes())
