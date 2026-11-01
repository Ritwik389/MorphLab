import os
import subprocess
import sys
import importlib
import inspect
import tempfile
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType
from typing import Any, List, Callable

import numpy as np
from tqdm import tqdm

import modules
import modules.globals
from modules.face_analyser import get_one_face

FRAME_PROCESSORS_MODULES: List[ModuleType] = []
FRAME_PROCESSORS_INTERFACE = [
    'pre_check',
    'pre_start',
    'process_frame',
    'process_image',
    'process_video'
]

ALLOWED_PROCESSORS = {
    'face_swapper',
    'face_enhancer',
    'face_enhancer_gpen256',
    'face_enhancer_gpen512'
}

def load_frame_processor_module(frame_processor: str) -> Any:
    if frame_processor not in ALLOWED_PROCESSORS:
        print(f"Frame processor {frame_processor} is not allowed")
        sys.exit()
    try:
        frame_processor_module = importlib.import_module(f'modules.processors.frame.{frame_processor}')
        for method_name in FRAME_PROCESSORS_INTERFACE:
            if not hasattr(frame_processor_module, method_name):
                print(f"Frame processor {frame_processor} is missing required method {method_name}")
                sys.exit()
    except ImportError:
        print(f"Frame processor {frame_processor} not found")
        sys.exit()
    return frame_processor_module


def get_frame_processors_modules(frame_processors: List[str]) -> List[ModuleType]:
    global FRAME_PROCESSORS_MODULES

    # Reconcile on each request: the previous cache silently ignored changes.
    names = list(dict.fromkeys(frame_processors))
    for name, enabled in modules.globals.fp_ui.items():
        if enabled and name not in names:
            names.append(name)
        elif not enabled and name in names:
            names.remove(name)
    cached = {module.__name__.split('.')[-1]: module for module in FRAME_PROCESSORS_MODULES}
    FRAME_PROCESSORS_MODULES = [cached[name] if name in cached else
                               load_frame_processor_module(name) for name in names]
    modules.globals.frame_processors = names
    return FRAME_PROCESSORS_MODULES

def set_frame_processors_modules_from_ui(frame_processors: List[str]) -> None:
    global FRAME_PROCESSORS_MODULES
    current_processor_names = [proc.__name__.split('.')[-1] for proc in FRAME_PROCESSORS_MODULES]

    for frame_processor, state in modules.globals.fp_ui.items():
        if state and frame_processor not in current_processor_names:
            try:
                frame_processor_module = load_frame_processor_module(frame_processor)
                FRAME_PROCESSORS_MODULES.append(frame_processor_module)
                if frame_processor not in modules.globals.frame_processors:
                     modules.globals.frame_processors.append(frame_processor)
            except SystemExit:
                 print(f"Warning: Failed to load frame processor {frame_processor} requested by UI state.")
            except Exception as e:
                 print(f"Warning: Error loading frame processor {frame_processor} requested by UI state: {e}")

        elif not state and frame_processor in current_processor_names:
            try:
                module_to_remove = next((mod for mod in FRAME_PROCESSORS_MODULES if mod.__name__.endswith(f'.{frame_processor}')), None)
                if module_to_remove:
                    FRAME_PROCESSORS_MODULES.remove(module_to_remove)
                if frame_processor in modules.globals.frame_processors:
                    modules.globals.frame_processors.remove(frame_processor)
            except Exception as e:
                 print(f"Warning: Error removing frame processor {frame_processor}: {e}")

def multi_process_frame(source_path: str, temp_frame_paths: List[str], process_frames: Callable[[str, List[str], Any], None], progress: Any = None) -> None:
    """Process frames in parallel with optimized batching and memory management."""
    max_workers = max(1, modules.globals.execution_threads or 1)
    # Temporal interpolation is ordered state; parallel frames corrupt it.
    if modules.globals.enable_interpolation and 0 < modules.globals.interpolation_weight < 1:
        process_frames(source_path, temp_frame_paths, progress)
        return
    
    # Determine optimal batch size based on available memory and thread count
    # Process frames in batches to avoid memory overflow
    batch_size = max(1, min(32, len(temp_frame_paths) // max(1, max_workers)))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Process in batches to manage memory better
        for i in range(0, len(temp_frame_paths), batch_size):
            batch = temp_frame_paths[i:i + batch_size]
            futures = []
            
            for path in batch:
                future = executor.submit(process_frames, source_path, [path], progress)
                futures.append(future)
            
            # Wait for batch to complete before starting next batch
            for future in futures:
                future.result()


def process_video(source_path: str, frame_paths: list[str], process_frames: Callable[[str, List[str], Any], None]) -> None:
    progress_bar_format = '{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
    total = len(frame_paths)
    with tqdm(total=total, desc='Processing', unit='frame', dynamic_ncols=True, bar_format=progress_bar_format) as progress:
        progress.set_postfix({'execution_providers': modules.globals.execution_providers, 'execution_threads': modules.globals.execution_threads, 'max_memory': modules.globals.max_memory})
        multi_process_frame(source_path, frame_paths, process_frames, progress)


def process_video_in_memory(source_path: str, target_path: str, fps: float) -> bool:
    """Process video frames in-memory using FFmpeg pipes, eliminating disk I/O.

    Reads raw frames from the source video via an FFmpeg decoder pipe, runs each
    frame through all active frame processors sequentially, and writes the
    result directly to an FFmpeg encoder pipe.  This avoids extracting frames to
    PNG on disk, which is the biggest I/O bottleneck in the disk-based pipeline.

    Returns True on success, False on failure (caller should fall back to the
    disk-based pipeline).
    """
    from modules import imread_unicode
    from modules.face_analyser import get_one_face
    from modules.utilities import (
        get_video_dimensions,
        estimate_frame_count,
        get_temp_output_path,
    )

    temp_output_path = get_temp_output_path(target_path)

    # --- Pre-load source face (needed by face_swapper in simple mode) ---
    source_face = None
    if source_path and os.path.exists(source_path):
        source_img = imread_unicode(source_path)
        if source_img is not None:
            source_face = get_one_face(source_img)
            del source_img
        if source_face is None:
            print("[DLC.CORE] Warning: No face detected in source image. "
                  "Face swapping will be skipped.")

    # --- Collect frame processors & reset per-video state ---
    frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
    for fp in frame_processors:
        if hasattr(fp, 'PREVIOUS_FRAME_RESULT'):
            fp.PREVIOUS_FRAME_RESULT = None

    # --- Video metadata ---
    try:
        width, height = get_video_dimensions(target_path)
    except Exception as e:
        print(f"[DLC.CORE] Failed to get video dimensions: {e}")
        return False

    total_frames = estimate_frame_count(target_path, fps)
    frame_size = width * height * 3

    # --- Build encoder arguments ---
    encoder = modules.globals.video_encoder
    encoder_options: List[str] = []
    is_hw_encoder = False

    if 'CUDAExecutionProvider' in modules.globals.execution_providers:
        if encoder == 'libx264':
            encoder = 'h264_nvenc'
            is_hw_encoder = True
            encoder_options = [
                '-preset', 'p4', '-tune', 'hq', '-rc', 'vbr',
                '-cq', str(modules.globals.video_quality), '-b:v', '0',
            ]
        elif encoder == 'libx265':
            encoder = 'hevc_nvenc'
            is_hw_encoder = True
            encoder_options = [
                '-preset', 'p4', '-tune', 'hq', '-rc', 'vbr',
                '-cq', str(modules.globals.video_quality), '-b:v', '0',
            ]
    elif 'DmlExecutionProvider' in modules.globals.execution_providers:
        if encoder == 'libx264':
            encoder = 'h264_amf'
            is_hw_encoder = True
            encoder_options = [
                '-quality', 'quality', '-rc', 'vbr_latency',
                '-qp_i', str(modules.globals.video_quality),
                '-qp_p', str(modules.globals.video_quality),
            ]
        elif encoder == 'libx265':
            encoder = 'hevc_amf'
            is_hw_encoder = True
            encoder_options = [
                '-quality', 'quality', '-rc', 'vbr_latency',
                '-qp_i', str(modules.globals.video_quality),
                '-qp_p', str(modules.globals.video_quality),
            ]

    if not is_hw_encoder:
        if encoder == 'libx264':
            encoder_options = [
                '-preset', 'medium',
                '-crf', str(modules.globals.video_quality),
                '-tune', 'film',
            ]
        elif encoder == 'libx265':
            encoder_options = [
                '-preset', 'medium',
                '-crf', str(modules.globals.video_quality),
                '-x265-params', 'log-level=error',
            ]
        elif encoder == 'libvpx-vp9':
            encoder_options = [
                '-crf', str(modules.globals.video_quality),
                '-b:v', '0', '-cpu-used', '2',
            ]

    # --- Attempt pipeline (hw encoder first, then sw fallback) ---
    encoders_to_try = [(encoder, encoder_options)]
    if is_hw_encoder:
        # Software fallback
        sw_encoder = 'libx264'
        sw_options = [
            '-preset', 'medium',
            '-crf', str(modules.globals.video_quality),
            '-tune', 'film',
        ]
        encoders_to_try.append((sw_encoder, sw_options))

    for attempt, (enc, enc_opts) in enumerate(encoders_to_try):
        # Reset interpolation state on retry
        if attempt > 0:
            for fp in frame_processors:
                if hasattr(fp, 'PREVIOUS_FRAME_RESULT'):
                    fp.PREVIOUS_FRAME_RESULT = None

        temporal = None
        swapper = next((p for p in frame_processors if p.__name__.endswith('.face_swapper')), None)
        strategy = modules.globals.temporal_strategy
        if swapper is not None and source_face is not None and strategy != 'off':
            from modules.face_analyser import get_many_faces, get_face_analyser, ensure_landmarks
            from modules.temporal import TemporalProcessor, clone_face

            def identity_metric(frame, face):
                measured = clone_face(face)
                model = get_face_analyser().models.get('recognition')
                if model is None:
                    return None
                model.get(frame, measured)
                return float(np.dot(source_face.normed_embedding, measured.normed_embedding))

            def swap_current(source, target, frame):
                if modules.globals.mouth_mask:
                    target.landmark_2d_106 = None
                    ensure_landmarks(frame, [target])
                return swapper.swap_face(source, target, frame)

            temporal = TemporalProcessor(get_many_faces, swap_current, source_face,
                                         mode=strategy, interval=modules.globals.detection_interval,
                                         many_faces=modules.globals.many_faces, identity_metric=identity_metric,
                                         postprocess=swapper.apply_post_processing)

        success = _run_pipe_pipeline(
            target_path, temp_output_path, fps,
            source_face, frame_processors,
            width, height, frame_size, total_frames,
            enc, enc_opts, temporal=temporal,
        )
        if success:
            modules.globals.last_video_report = temporal.report() if temporal else {}
            return True

        if attempt == 0 and is_hw_encoder:
            print(f"[DLC.CORE] Hardware encoder '{enc}' failed, "
                  f"retrying with software encoder...")

    return False


def _run_pipe_pipeline(
    target_path: str,
    temp_output_path: str,
    fps: float,
    source_face: Any,
    frame_processors: List[Any],
    width: int,
    height: int,
    frame_size: int,
    total_frames: int,
    encoder: str,
    encoder_options: List[str],
    temporal=None,
) -> bool:
    """Run the FFmpeg-pipe read → process → encode pipeline once."""

    # --- Reader: decode source video to raw BGR24 on stdout ---
    reader_cmd = [
        'ffmpeg', '-hide_banner',
        '-i', target_path,
        '-map', '0:v:0', '-an',
        '-vf', f'fps={fps}',
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-v', 'error',
        '-',
    ]

    # --- Writer: encode raw BGR24 from stdin ---
    writer_cmd = [
        'ffmpeg', '-hide_banner',
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{width}x{height}',
        '-r', str(fps),
        '-i', '-',
        '-c:v', encoder,
    ]
    writer_cmd.extend(encoder_options)
    writer_cmd.extend([
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
        '-v', 'error',
        '-y', temp_output_path,
    ])

    reader = None
    writer = None
    # Pipe stderr can fill while the parent is blocked on raw frame I/O.
    reader_log = tempfile.TemporaryFile()
    writer_log = tempfile.TemporaryFile()
    try:
        reader = subprocess.Popen(
            reader_cmd, stdout=subprocess.PIPE, stderr=reader_log,
        )
        writer = subprocess.Popen(
            writer_cmd, stdin=subprocess.PIPE, stderr=writer_log,
        )
    except Exception as e:
        print(f"[DLC.CORE] Failed to start FFmpeg pipes: {e}")
        for proc in (reader, writer):
            if proc:
                try:
                    proc.kill()
                    proc.wait()
                except Exception:
                    pass
        reader_log.close()
        writer_log.close()
        return False

    processed_count = 0
    bar_fmt = ('{l_bar}{bar}| {n_fmt}/{total_fmt} '
               '[{elapsed}<{remaining}, {rate_fmt}{postfix}]')

    try:
        with tqdm(total=total_frames, desc='Processing', unit='frame',
                  dynamic_ncols=True, bar_format=bar_fmt) as progress:
            progress.set_postfix({
                'execution_providers': modules.globals.execution_providers,
                'threads': modules.globals.execution_threads,
                'mode': 'in-memory',
            })

            parameters = [inspect.signature(fp.process_frame).parameters for fp in frame_processors]

            while True:
                raw = reader.stdout.read(frame_size)
                if not raw:
                    break
                if len(raw) != frame_size:
                    raise RuntimeError('FFmpeg returned a truncated raw frame')

                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (height, width, 3)
                ).copy()

                # Run frame through every active processor
                for fp, params in zip(frame_processors, parameters):
                    if temporal is not None and fp.__name__.endswith('.face_swapper'):
                        frame = temporal.process(frame)
                        continue
                    kwargs = {}
                    if 'target_face' in params and not modules.globals.many_faces:
                        kwargs['target_face'] = get_one_face(frame)
                    frame = fp.process_frame(source_face, frame, **kwargs)

                writer.stdin.write(frame.tobytes())
                processed_count += 1
                progress.update(1)

        # Graceful shutdown
        writer.stdin.close()
        writer.wait()
        reader.wait()

        if writer.returncode != 0 or reader.returncode != 0:
            writer_log.seek(0)
            reader_log.seek(0)
            stderr_out = (writer_log.read() + reader_log.read()).decode(errors='ignore').strip()
            if stderr_out:
                print(f"[DLC.CORE] FFmpeg encoder error: {stderr_out}")
            return False

        return processed_count > 0 and os.path.isfile(temp_output_path)

    except BrokenPipeError:
        print("[DLC.CORE] FFmpeg pipe broken (encoder may not be available).")
        return False
    except Exception as e:
        print(f"[DLC.CORE] In-memory processing error: {e}")
        return False
    finally:
        for proc in (reader, writer):
            if proc:
                try:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait()
                    for stream in (proc.stdin, proc.stdout):
                        if stream is not None:
                            stream.close()
                except Exception:
                    pass
        reader_log.close()
        writer_log.close()
