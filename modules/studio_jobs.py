"""Cancellable exports which yield the inference device between frames."""
from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import cv2
import numpy as np

from modules import research
from modules.runtime import registry

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='aims-export')


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = 'queued'
    progress: float = 0
    message: str = 'Waiting to process'
    report: dict = field(default_factory=dict)
    cancelled: object = field(default_factory=threading.Event)
    created: float = field(default_factory=time.time)

    @property
    def directory(self):
        return research.OUTPUT_ROOT / self.id

    def public(self):
        complete = self.state == 'complete'
        message = 'Paused while the live camera is active. Stop the camera to resume.' if self.state in {'queued', 'running'} and registry.scheduler.live_sessions else self.message
        return {'id': self.id, 'state': self.state, 'progress': self.progress, 'message': message,
                'result': f'/api/jobs/{self.id}/result' if complete else None,
                'original': f'/api/jobs/{self.id}/original' if complete and (self.directory/'original.png').exists() else None,
                'report_url': f'/api/jobs/{self.id}/report' if complete else None, 'report': self.report}


def edit_frame(frame, latent, mode, many, strength, job):
    if job.cancelled.is_set():
        raise InterruptedError('Job cancelled.')
    with registry.scheduler.use(cancelled=job.cancelled.is_set):
        faces = sorted(registry.detect(frame), key=lambda f: f.bbox[0])
        if not faces:
            return frame, 0
        selected = faces if many else faces[:1]
        output = frame.copy()
        for face in selected:
            if mode == 'swap':
                output = registry.swap(output, face, latent)
            else:
                h, w = output.shape[:2]
                x1, y1, x2, y2 = face.bbox.astype(int)
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                roi = output[y1:y2, x1:x2]
                if roi.size:
                    roi[:] = cv2.GaussianBlur(roi, (0, 0), max(12, (x2-x1)/5)) if mode == 'blur' else cv2.resize(cv2.resize(roi, (8, 8)), (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)
        return cv2.addWeighted(output, strength, frame, 1-strength, 0), len(selected)


def run_job(job, source, target, kind, mode, many, strength):
    started = time.perf_counter()
    capture = writer = None
    job.state = 'running'
    job.message = 'Preparing models'
    try:
        latent = None
        if mode == 'swap':
            with registry.scheduler.use(cancelled=job.cancelled.is_set):
                source_frame = research.read_image(source)
                latent = registry.source(source_frame)
                source_face = registry.detect(source_frame)[0]
                source_embedding = registry.embedding(source_frame, source_face)
                source_embedding /= max(1e-8, np.linalg.norm(source_embedding))
                job.report['source_quality'] = research.quality(source_frame, source_face.bbox)
        if kind == 'photo':
            frame = research.read_image(target)
            cv2.imwrite(str(job.directory/'original.png'), frame)
            output, count = edit_frame(frame, latent, mode, many, strength, job)
            if not count:
                raise ValueError('No face detected in target. Try a clear portrait.')
            changed = float(np.abs(output.astype(float)-frame.astype(float)).mean())
            cv2.imwrite(str(job.directory / 'result.png'), research.watermark(output))
            job.report.update({'faces_edited': count, 'width': frame.shape[1], 'height': frame.shape[0],
                          'mean_absolute_pixel_change_0_255': changed})
            with registry.scheduler.use(cancelled=job.cancelled.is_set):
                observed = registry.detect(output, recognition=mode == 'swap')
            job.report['target_quality'] = [research.quality(frame, face.bbox) for face in observed]
            if mode == 'swap' and observed:
                actual = observed[0].normed_embedding
                job.report['source_output_embedding_cosine'] = float(np.dot(source_embedding, actual))
        else:
            metadata = research.probe_video(str(target))
            capture = cv2.VideoCapture(str(target))
            if not capture.isOpened():
                raise ValueError('Could not decode this video. Try an MP4 with H.264 video.')
            rotation = capture.get(cv2.CAP_PROP_ORIENTATION_META)
            oriented = capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
            if rotation % 360 and not oriented:
                raise ValueError('This decoder cannot rotate the video. Convert it to an upright MP4 first.')
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if width <= 0 or height <= 0:
                raise ValueError('Video has invalid decoded dimensions.')
            fps = capture.get(cv2.CAP_PROP_FPS)
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if not np.isfinite(fps) or not 0 < fps <= 240:
                raise ValueError('Video has an invalid frame rate.')
            writer = cv2.VideoWriter(str(job.directory / 'silent.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps,
                                     (width, height))
            if not writer.isOpened():
                raise ValueError('Could not initialize the video encoder.')
            frames = edited = 0
            from modules.temporal import FaceTracker, scene_changed
            tracker = FaceTracker()
            previous = None
            while True:
                if job.cancelled.is_set() or time.perf_counter()-started > 900:
                    raise InterruptedError('Job cancelled.')
                ok, frame = capture.read()
                if not ok:
                    break
                # Refresh recognition on detection frames to prevent cross-person association.
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if frames % 3 == 0 or scene_changed(previous, gray) or not tracker.predict(previous, gray):
                    with registry.scheduler.use(cancelled=job.cancelled.is_set):
                        tracks = tracker.update(registry.detect(frame, recognition=True))
                else:
                    tracks = [t for t in tracker.tracks if t.visible]
                previous = gray
                chosen = tracks if many else [t for t in tracks if t.id == 1]
                result = frame.copy()
                with registry.scheduler.use(cancelled=job.cancelled.is_set):
                    for track in chosen:
                        if mode == 'swap':
                            result = registry.swap(result, track.face, latent)
                if mode != 'swap':
                    result, _ = edit_frame(frame, None, mode, many, strength, job)
                else:
                    result = cv2.addWeighted(result, strength, frame, 1-strength, 0)
                writer.write(research.watermark(result))
                frames += 1
                edited += len(chosen)
                job.progress = min(.95, frames / max(1, total) * .95)
                job.message = f'Processing frame {frames} of {total}'
            writer.release()
            writer = None
            capture.release()
            capture = None
            if not frames or (total > 0 and frames < total-2):
                raise ValueError('Video ended unexpectedly. Try another video file.')
            job.message = 'Restoring audio'
            command = ['ffmpeg', '-v', 'error', '-i', str(job.directory / 'silent.mp4'), '-i', str(target),
                '-map', '0:v:0', '-map', '1:a:0?', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-c:a', 'aac', '-movflags', '+faststart', '-y', str(job.directory / 'result.mp4')]
            with (job.directory/'ffmpeg.log').open('w') as log:
                with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log) as process:
                    deadline = time.monotonic()+120
                    while process.poll() is None:
                        if job.cancelled.wait(.1) or time.monotonic() > deadline:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                            raise InterruptedError('Job cancelled or time limit reached.')
                    if process.returncode:
                        raise ValueError('Could not finalize this video. Check its format and audio.')
            job.report.update({**metadata, 'coded_width': metadata['width'], 'coded_height': metadata['height'],
                          'width': width, 'height': height, 'input_orientation_degrees': rotation,
                          'frames_processed': frames, 'faces_edited': edited, 'fps': fps,
                          'strategy': 'identity-gated tracking + sparse flow; detection every 3 frames'})
        if job.cancelled.is_set():
            raise InterruptedError('Job cancelled.')
        from modules.utilities import file_sha256
        result_path = next(job.directory.glob('result.*'))
        job.report.update({'schema_version': 2, 'processing_seconds': time.perf_counter()-started,
            'mode': mode, 'runtime': registry.status(), 'quality_metrics_are_heuristics': True,
            'output_sha256': file_sha256(str(result_path)), 'watermark': 'MorphLab / EDITED'})
        (job.directory / 'report.json').write_text(json.dumps(job.report, indent=2))
        job.state, job.progress, job.message = 'complete', 1, 'Your result is ready'
    except InterruptedError:
        job.state, job.message = 'cancelled', 'Job cancelled'
    except Exception as exc:
        import traceback
        (job.directory/'processing.log').write_text(traceback.format_exc())
        job.state, job.message = 'error', str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Processing failed. Try another file.'
    finally:
        if capture is not None:
            capture.release()
        if writer is not None:
            writer.release()
        for name in ('source.upload', 'target.upload', 'silent.mp4'):
            (job.directory / name).unlink(missing_ok=True)
        if job.state != 'complete':
            (job.directory/'original.png').unlink(missing_ok=True)
            for path in job.directory.glob('result.*'):
                path.unlink(missing_ok=True)
