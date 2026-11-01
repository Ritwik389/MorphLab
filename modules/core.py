import os
import sys
# single thread doubles cuda performance - needs to be set before torch import
if any(arg.startswith('--execution-provider') for arg in sys.argv):
    os.environ['OMP_NUM_THREADS'] = '6'
# reduce tensorflow log level
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import warnings
from typing import List
import platform
import signal
import shutil
import argparse
import json
import tempfile
from pathlib import Path
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
import onnxruntime

import modules.globals
import modules.metadata
from modules.processors.frame.core import get_frame_processors_modules, process_video_in_memory
from modules.utilities import is_image, is_video, detect_fps, create_video, extract_frames, get_temp_frame_paths, restore_audio, create_temp, move_temp, clean_temp, normalize_output_path

if HAS_TORCH and 'ROCMExecutionProvider' in modules.globals.execution_providers:
    del torch

warnings.filterwarnings('ignore', category=FutureWarning, module='insightface')
if HAS_TORCH:
    warnings.filterwarnings('ignore', category=UserWarning, module='torchvision')


def parse_args() -> None:
    signal.signal(signal.SIGINT, lambda signal_number, frame: destroy())
    program = argparse.ArgumentParser()
    program.add_argument('-s', '--source', help='select an source image', dest='source_path')
    program.add_argument('-t', '--target', help='select an target image or video', dest='target_path')
    program.add_argument('-o', '--output', help='select output file or directory', dest='output_path')
    program.add_argument('--frame-processor', help='pipeline of frame processors', dest='frame_processor', default=['face_swapper'], choices=['face_swapper', 'face_enhancer', 'face_enhancer_gpen256', 'face_enhancer_gpen512'], nargs='+')
    program.add_argument('--keep-fps', help='keep original fps (default)', action=argparse.BooleanOptionalAction, default=True)
    program.add_argument('--keep-audio', help='keep original audio (default)', action=argparse.BooleanOptionalAction, default=True)
    program.add_argument('--keep-frames', help='keep temporary frames', dest='keep_frames', action='store_true', default=False)
    program.add_argument('--many-faces', help='process every face', dest='many_faces', action='store_true', default=False)
    program.add_argument('--nsfw-filter', help='filter the NSFW image or video', dest='nsfw_filter', action='store_true', default=False)
    program.add_argument('--map-faces', help='map source target faces', dest='map_faces', action='store_true', default=False)
    program.add_argument('--mouth-mask', help='mask the mouth region', dest='mouth_mask', action='store_true', default=False)
    program.add_argument('--video-encoder', help='adjust output video encoder', dest='video_encoder', default='libx264', choices=['libx264', 'libx265', 'libvpx-vp9'])
    program.add_argument('--video-quality', help='adjust output video quality', dest='video_quality', type=int, default=18, choices=range(52), metavar='[0-51]')
    program.add_argument('-l', '--lang', help='Ui language', default="en")
    program.add_argument('--live-mirror', help='The live camera display as you see it in the front-facing camera frame', dest='live_mirror', action='store_true', default=False)
    program.add_argument('--live-resizable', help='The live camera frame is resizable', dest='live_resizable', action='store_true', default=False)
    program.add_argument('--max-memory', help='maximum amount of RAM in GB', dest='max_memory', type=int, default=suggest_max_memory())
    program.add_argument('--execution-provider', help='execution provider', dest='execution_provider', default=[suggest_default_execution_provider()], choices=suggest_execution_providers(), nargs='+')
    program.add_argument('--execution-threads', help='number of execution threads', dest='execution_threads', type=int, default=None)
    program.add_argument('--temporal-strategy', choices=['off', 'baseline', 'tracked', 'adaptive'], default='tracked',
                         help='video research strategy (default: tracked)')
    program.add_argument('--detection-interval', type=int, choices=range(1, 11), default=3,
                         help='maximum adaptive detection interval in frames')
    program.add_argument('--research-report', help='write video measurements as JSON')
    program.add_argument('-v', '--version', action='version', version=f'{modules.metadata.name} {modules.metadata.version}')

    # register deprecated args
    program.add_argument('-f', '--face', help=argparse.SUPPRESS, dest='source_path_deprecated')
    program.add_argument('--cpu-cores', help=argparse.SUPPRESS, dest='cpu_cores_deprecated', type=int)
    program.add_argument('--gpu-vendor', help=argparse.SUPPRESS, dest='gpu_vendor_deprecated')
    program.add_argument('--gpu-threads', help=argparse.SUPPRESS, dest='gpu_threads_deprecated', type=int)

    args = program.parse_args()
    headless = bool(args.source_path or args.source_path_deprecated or args.target_path or args.output_path)
    if headless:
        if not args.target_path or not args.output_path:
            program.error('headless processing requires --target and --output')
        if 'face_swapper' in args.frame_processor and not (args.source_path or args.source_path_deprecated):
            program.error('face swapping requires --source')
        if args.map_faces:
            program.error('--map-faces requires the desktop face-mapping dialog')
    if args.max_memory < 0 or (args.execution_threads is not None and args.execution_threads < 1):
        program.error('memory must be >= 0 and execution threads must be >= 1')

    modules.globals.source_path = args.source_path
    modules.globals.target_path = args.target_path
    modules.globals.output_path = normalize_output_path(modules.globals.source_path, modules.globals.target_path, args.output_path)
    modules.globals.frame_processors = args.frame_processor
    modules.globals.headless = headless
    modules.globals.keep_fps = args.keep_fps
    modules.globals.keep_audio = args.keep_audio
    modules.globals.keep_frames = args.keep_frames
    modules.globals.many_faces = args.many_faces
    modules.globals.mouth_mask = args.mouth_mask
    modules.globals.nsfw_filter = args.nsfw_filter
    modules.globals.map_faces = args.map_faces
    modules.globals.video_encoder = args.video_encoder
    modules.globals.video_quality = args.video_quality
    modules.globals.live_mirror = args.live_mirror
    modules.globals.live_resizable = args.live_resizable
    modules.globals.max_memory = args.max_memory
    modules.globals.execution_providers = decode_execution_providers(args.execution_provider)
    modules.globals.execution_threads = args.execution_threads
    modules.globals.lang = args.lang
    modules.globals.temporal_strategy = args.temporal_strategy
    modules.globals.detection_interval = args.detection_interval
    modules.globals.video_report_path = args.research_report

    # The argparse default (None) avoids evaluating suggest_execution_threads()
    # before providers are decoded, and deprecated-arg overrides above may
    # have already set execution_threads.
    if modules.globals.execution_threads is None:
        modules.globals.execution_threads = suggest_execution_threads()

    #for ENHANCER tumblers:
    for enhancer_key in ('face_enhancer', 'face_enhancer_gpen256', 'face_enhancer_gpen512'):
        modules.globals.fp_ui[enhancer_key] = enhancer_key in args.frame_processor

    # translate deprecated args
    if args.source_path_deprecated:
        print('\033[33mArgument -f and --face are deprecated. Use -s and --source instead.\033[0m')
        modules.globals.source_path = args.source_path_deprecated
        modules.globals.output_path = normalize_output_path(args.source_path_deprecated, modules.globals.target_path, args.output_path)
    if args.cpu_cores_deprecated:
        print('\033[33mArgument --cpu-cores is deprecated. Use --execution-threads instead.\033[0m')
        modules.globals.execution_threads = args.cpu_cores_deprecated
    if args.gpu_vendor_deprecated == 'apple':
        print('\033[33mArgument --gpu-vendor apple is deprecated. Use --execution-provider coreml instead.\033[0m')
        modules.globals.execution_providers = decode_execution_providers(['coreml'])
    if args.gpu_vendor_deprecated == 'nvidia':
        print('\033[33mArgument --gpu-vendor nvidia is deprecated. Use --execution-provider cuda instead.\033[0m')
        modules.globals.execution_providers = decode_execution_providers(['cuda'])
    if args.gpu_vendor_deprecated == 'amd':
        print('\033[33mArgument --gpu-vendor amd is deprecated. Use --execution-provider cuda instead.\033[0m')
        modules.globals.execution_providers = decode_execution_providers(['rocm'])
    if args.gpu_threads_deprecated:
        print('\033[33mArgument --gpu-threads is deprecated. Use --execution-threads instead.\033[0m')
        modules.globals.execution_threads = args.gpu_threads_deprecated


def encode_execution_providers(execution_providers: List[str]) -> List[str]:
    return [execution_provider.replace('ExecutionProvider', '').lower() for execution_provider in execution_providers]


def decode_execution_providers(execution_providers: List[str]) -> List[str]:
    return [provider for provider, encoded_execution_provider in zip(onnxruntime.get_available_providers(), encode_execution_providers(onnxruntime.get_available_providers()))
            if any(execution_provider in encoded_execution_provider for execution_provider in execution_providers)]


def suggest_max_memory() -> int:
    # A hard address-space limit can abort native ONNX/Qt allocations on macOS.
    return 0


def suggest_default_execution_provider() -> str:
    """Pick the best available provider: cuda > rocm > coreml > openvino > dml > cpu."""
    available = encode_execution_providers(onnxruntime.get_available_providers())
    for pref in ('cuda', 'rocm', 'coreml', 'openvino', 'dml'):
        if pref in available:
            return pref
    return 'cpu'


def suggest_execution_providers() -> List[str]:
    return encode_execution_providers(onnxruntime.get_available_providers())


def suggest_execution_threads() -> int:
    """Suggest optimal thread count based on hardware and execution provider."""
    import os
    
    # Get CPU count
    cpu_count = os.cpu_count() or 4
    
    if 'DmlExecutionProvider' in modules.globals.execution_providers:
        return 1
    if 'ROCMExecutionProvider' in modules.globals.execution_providers:
        return 1
    if 'CUDAExecutionProvider' in modules.globals.execution_providers:
        return 2
    if 'OpenVINOExecutionProvider' in modules.globals.execution_providers:
        return 1
    
    # For CPU execution, use most cores but leave some for system
    return max(1, min(cpu_count - 2, 16))


def limit_resources() -> None:
    # prevent tensorflow memory leak
    if modules.globals.nsfw_filter:
        import tensorflow
        gpus = tensorflow.config.experimental.list_physical_devices('GPU')
        for gpu in gpus:
            tensorflow.config.experimental.set_memory_growth(gpu, True)
    # limit memory usage
    if modules.globals.max_memory:
        memory = modules.globals.max_memory * 1024 ** 3
        if platform.system().lower() == 'windows':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetProcessWorkingSetSize(-1, ctypes.c_size_t(memory), ctypes.c_size_t(memory))
        elif platform.system().lower() != 'darwin':
            import resource
            resource.setrlimit(resource.RLIMIT_DATA, (memory, memory))


def release_resources() -> None:
    if 'CUDAExecutionProvider' in modules.globals.execution_providers and HAS_TORCH:
        torch.cuda.empty_cache()


def pre_check() -> bool:
    if sys.version_info < (3, 10):
        update_status('Python version is not supported - please upgrade to 3.10 or higher.')
        return False
    if not shutil.which('ffmpeg'):
        update_status('ffmpeg is not installed.')
        return False
    if not shutil.which('ffprobe'):
        update_status('ffprobe is not installed.')
        return False
    return True


def update_status(message: str, scope: str = 'DLC.CORE') -> None:
    print(f'[{scope}] {message}')
    if not modules.globals.headless:
        from modules import ui
        ui.update_status(message)

def start() -> bool:
    """Process one job, preserving inputs and only publishing completed output."""
    import time
    from modules import imread_unicode
    from modules.face_analyser import get_one_face

    started = time.perf_counter()
    target = modules.globals.target_path
    output = modules.globals.output_path
    if not (is_image(target) or is_video(target)):
        raise ValueError('Select a readable target image or video.')
    if not output:
        raise ValueError('Select an output path.')
    for input_path in (target, modules.globals.source_path):
        if input_path and Path(input_path).resolve() == Path(output).resolve():
            raise ValueError('Output must differ from both input files.')
    if not Path(output).parent.is_dir():
        raise ValueError('Output directory does not exist.')
    processors = get_frame_processors_modules(modules.globals.frame_processors)
    if not processors:
        raise ValueError('Select at least one frame processor.')
    if 'face_swapper' in modules.globals.frame_processors and not modules.globals.map_faces:
        source = imread_unicode(modules.globals.source_path)
        if source is None or get_one_face(source) is None:
            raise ValueError('Source image must contain a detectable face.')
    for processor in processors:
        if not processor.pre_check() or not processor.pre_start():
            raise RuntimeError(f'{processor.NAME}: model or input validation failed.')
    if modules.globals.nsfw_filter:
        from modules.predicter import predict_image, predict_video
        blocked = predict_image(target) if is_image(target) else predict_video(target)
        if blocked:
            raise ValueError('The optional content classifier blocked this input.')
    update_status('Processing...')
    image_job = is_image(target)
    modules.globals.last_video_report = {}
    report_path = modules.globals.video_report_path
    if report_path:
        if image_job or modules.globals.map_faces or modules.globals.temporal_strategy == 'off':
            raise ValueError('Research reports require a video with a temporal research strategy and no face map.')
        protected = [output, target, modules.globals.source_path]
        if any(p and Path(p).resolve() == Path(report_path).resolve() for p in protected):
            raise ValueError('Research report must differ from the input and output media paths.')
        if not Path(report_path).parent.is_dir():
            raise ValueError('Research report directory does not exist.')
    extension = Path(output).suffix.lower()
    if image_job and extension not in {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff'}:
        raise ValueError('Choose a supported output image extension.')
    if not image_job and extension not in {'.mp4', '.mkv'}:
        raise ValueError('Choose .mp4 or .mkv for video output.')

    # Output staging prevents a failed job from overwriting a previous result.
    with tempfile.TemporaryDirectory(prefix='.aims-', dir=Path(output).parent) as directory:
        staged = str(Path(directory) / ('result' + extension))
        if image_job:
            current = target
            for processor in processors:
                processor.process_image(modules.globals.source_path, current, staged)
                if imread_unicode(staged) is None:
                    raise RuntimeError(f'{processor.NAME} did not produce an image.')
                current = staged
                release_resources()
        else:
            fps = detect_fps(target) if modules.globals.keep_fps else 30.0
            create_temp(target)
            try:
                created = False
                if not modules.globals.map_faces:
                    created = process_video_in_memory(modules.globals.source_path, target, fps)
                if not created and report_path:
                    raise RuntimeError('Research video pipeline failed; falling back would invalidate the experiment.')
                if not created:
                    if not modules.globals.map_faces:
                        if not extract_frames(target, fps):
                            raise RuntimeError('FFmpeg frame extraction failed.')
                    frames = get_temp_frame_paths(target)
                    if not frames:
                        raise RuntimeError('No frames were decoded from the video.')
                    for processor in processors:
                        processor.process_video(modules.globals.source_path, frames)
                        release_resources()
                    created = create_video(target, fps)
                if not created:
                    raise RuntimeError('FFmpeg video encoding failed.')
                if modules.globals.keep_audio:
                    restore_audio(target, staged)
                else:
                    move_temp(target, staged)
            finally:
                clean_temp(target)
        if not os.path.isfile(staged) or os.path.getsize(staged) == 0:
            raise RuntimeError('Processing did not produce an output file.')
        os.replace(staged, output)
    if report_path:
        if not modules.globals.last_video_report:
            raise RuntimeError('Research measurements are unavailable; the pipeline used a fallback.')
        import cv2
        import numpy
        from modules.utilities import file_sha256, model_provenance
        report = {**modules.globals.last_video_report,
                  'end_to_end_seconds': time.perf_counter() - started,
                  'execution_providers': modules.globals.execution_providers,
                  'execution_threads': modules.globals.execution_threads,
                  'source_sha256': file_sha256(modules.globals.source_path),
                  'target_sha256': file_sha256(target),
                  'output_sha256': file_sha256(output),
                  'model_manifest': model_provenance(),
                  'software': {'python': platform.python_version(), 'platform': platform.platform(),
                               'opencv': cv2.__version__, 'numpy': numpy.__version__,
                               'onnxruntime': onnxruntime.__version__}}
        Path(report_path).write_text(json.dumps(report, indent=2))
    update_status(f'Processing succeeded in {time.perf_counter() - started:.2f}s: {output}')
    return True


def destroy(to_quit=True) -> None:
    if modules.globals.target_path:
        clean_temp(modules.globals.target_path)
    if to_quit:
        quit()


def run() -> None:
    parse_args()
    if not pre_check():
        raise SystemExit(1)
    for frame_processor in get_frame_processors_modules(modules.globals.frame_processors):
        if not frame_processor.pre_check():
            raise SystemExit(1)
    # Pre-load face analyser in main thread before GUI starts
    #from modules.face_analyser import get_face_analyser
    #get_face_analyser()
    limit_resources()
    if modules.globals.headless:
        try:
            start()
        except Exception as exc:
            update_status(f'Processing failed: {exc}')
            raise SystemExit(1) from exc
    else:
        from modules import ui
        window = ui.init(start, destroy, modules.globals.lang)
        window.mainloop()
