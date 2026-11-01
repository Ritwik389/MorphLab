#!/usr/bin/env python3
"""MorphLab research workbench. `python app.py`, or `python app.py --share`."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).parent / '.cache' / 'matplotlib'))

import gradio as gr
from modules import research, live_camera
from modules.paths import ROOT_DIR, MODELS_DIR

CSS = """
.gradio-container { max-width: 1180px !important; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
h1 { font-size: 28px !important; letter-spacing: -0.8px; margin-bottom: 8px !important; }
button.primary { background: #171717 !important; border-color: #171717 !important; color: white !important; }
button { min-height: 44px; }
footer { display: none !important; }
"""


def image_experiment(*args):
    try:
        comparison, output, report_path, report = research.process_image(*args)
        summary = f"**{report['faces_edited']} face(s) edited** · {report['processing_seconds']:.2f} seconds · {report['width']} × {report['height']} px"
        return comparison, output, report_path, report, summary
    except (ValueError, RuntimeError, OSError) as exc:
        raise gr.Error(str(exc)) from exc


def video_experiment(*args):
    try:
        return research.process_video(*args)
    except (ValueError, RuntimeError, OSError) as exc:
        raise gr.Error(str(exc)) from exc


def live_frame(*args):
    try:
        output, status = live_camera.process_frame(*args)
        return output, status, args[0]
    except (ValueError, RuntimeError, OSError) as exc:
        raise gr.Error(str(exc)) from exc


def capture_webcam_face(frame):
    try:
        return live_camera.capture_identity(frame)
    except (ValueError, RuntimeError, OSError) as exc:
        raise gr.Error(str(exc)) from exc


def build_app():
    with gr.Blocks(title='MorphLab · Research workbench', delete_cache=(600, 3600)) as demo:
        gr.Markdown('# MorphLab / Research workbench\nFace editing experiments with a result you can inspect and measure.')
        with gr.Tab('Live webcam'):
            gr.Markdown('### Detect faces from your camera\nStart the webcam and allow camera access. Faces are detected automatically; no photo upload is needed.')
            live_identity = gr.State(None, time_to_live=3600)
            latest_camera_frame = gr.State(None, time_to_live=3600)
            live_mode = gr.Radio(live_camera.MODES, value='Detect faces', label='Live mode')
            with gr.Row():
                camera = gr.Image(sources=['webcam'], type='numpy', streaming=True, format='jpeg',
                                  label='Webcam', height=360, interactive=True, alt_text='Live webcam input')
                camera_result = gr.Image(type='numpy', format='jpeg', label='Live detection',
                                         height=360, interactive=False, buttons=['fullscreen'],
                                         alt_text='Live camera frame with detected faces highlighted')
            live_status = gr.Markdown('Start the webcam to detect faces automatically.')
            with gr.Group(visible=False) as webcam_identity_controls:
                gr.Markdown('Capture a face directly from the webcam to choose the swap identity. Only capture people who have agreed to the edit.')
                with gr.Row():
                    capture = gr.Button('Capture face from webcam', variant='primary')
                    clear_identity = gr.Button('Clear captured face')
                captured_face = gr.Image(label='Captured webcam identity', interactive=False,
                                         height=160, type='numpy', buttons=[])
                captured_status = gr.Markdown('No webcam identity captured yet.')
            live_mode.change(lambda mode: gr.update(visible=mode == 'Swap face'), live_mode,
                             webcam_identity_controls, queue=False, api_visibility='private')
            live_stream = camera.stream(live_frame, [camera, live_mode, live_identity],
                          [camera_result, live_status, latest_camera_frame],
                          stream_every=.15, trigger_mode='always_last', concurrency_limit=1,
                          concurrency_id='live_camera', show_progress='hidden', api_name='live_frame')
            capture.click(capture_webcam_face, latest_camera_frame, [live_identity, captured_face, captured_status],
                          concurrency_limit=1, concurrency_id='experiments', api_name='capture_webcam_face')
            clear_identity.click(lambda: (None, None, 'Captured identity cleared.'),
                                 outputs=[live_identity, captured_face, captured_status], queue=False,
                                 api_visibility='private')
            camera.clear(lambda: (None, 'Camera cleared. Start the webcam to detect faces.',
                                   None, None, 'Captured identity cleared.', None),
                         outputs=[camera_result, live_status, live_identity, captured_face, captured_status, latest_camera_frame],
                         queue=False, cancels=[live_stream], api_visibility='private')
            gr.Markdown('Detection is lightweight. Face swapping is slower on CPU. Stop the camera with its stop control; '
                        'clear the camera to remove the captured identity. The live preview is not exported as a recording.')
        with gr.Tab('Image experiment'):
            with gr.Row():
                with gr.Column(scale=1, min_width=300):
                    mode = gr.Radio(research.MODES, value='Swap identity', label='Experiment')
                    with gr.Row():
                        source = gr.Image(type='pil', label='Source identity', height=220, sources=['upload'])
                        target = gr.Image(type='pil', label='Target image', height=220, sources=['upload'])
                    gr.Markdown('Use clear, front-facing portraits. Source is only needed for identity swapping.')
                    with gr.Accordion('Swap settings', open=False):
                        strength = gr.Slider(0.1, 1, value=1, step=0.05, label='Blend strength')
                        many = gr.Checkbox(label='Swap all detected faces', value=False)
                    permission = gr.Checkbox(label='I have permission to edit this media.', value=False)
                    run = gr.Button('Run experiment', variant='primary')
                with gr.Column(scale=1, min_width=300):
                    comparison = gr.ImageSlider(label='Target / Edited result', type='numpy', height=400)
                    summary = gr.Markdown('Upload an image and run an experiment to compare the result.')
                    with gr.Row():
                        output = gr.File(label='Edited image', interactive=False)
                        report_file = gr.File(label='Experiment report', interactive=False)
            with gr.Accordion('Measured results', open=False):
                report = gr.JSON(label='Measurements')
            run.click(image_experiment, [source, target, mode, strength, many, permission],
                      [comparison, output, report_file, report, summary],
                      concurrency_limit=1, concurrency_id='experiments', api_name='image_experiment')
            examples = Path(ROOT_DIR) / 'assets' / 'examples'
            if (examples / 'source.png').exists():
                gr.Examples([[str(examples / 'source.png'), str(examples / 'target.jpg')]],
                            inputs=[source, target], label='Public-domain sample portraits')
        with gr.Tab('Short video'):
            gr.Markdown('### Export a short face swap\nCPU demo limits: **30 seconds, 720p, 100 MB**. Audio and timing are preserved; exports carry an edited label.')
            with gr.Row():
                with gr.Column():
                    video_source = gr.Image(type='pil', label='Source identity', sources=['upload'], height=220)
                    video_target = gr.File(label='Target video', file_types=['.mp4', '.mkv', '.mov', '.webm'])
                    video_permission = gr.Checkbox(label='I have permission to edit this media.')
                    strategy = gr.Radio(['baseline', 'tracked', 'adaptive'], value='tracked', label='Video strategy',
                                        info='Baseline detects every frame; tracked stabilizes identity; adaptive also reuses verified motion.')
                    interval = gr.Slider(1, 10, value=3, step=1, label='Adaptive detection interval (frames)')
                    export = gr.Button('Export video', variant='primary')
                with gr.Column():
                    video_result = gr.Video(label='Edited video', interactive=False)
                    video_report_file = gr.File(label='Experiment report', interactive=False)
                    video_report = gr.JSON(label='Measurements')
            export.click(video_experiment, [video_source, video_target, video_permission, strategy, interval],
                         [video_result, video_report_file, video_report],
                         concurrency_limit=1, concurrency_id='experiments', api_name='video_experiment')
        gr.Markdown('Research demo · Identity swapping requires pretrained research models. Blur and pixelation work without them. '
                    'Quality measurements are heuristics, not authenticity scores. Inspect anonymized images for missed faces. '
                    'Uploads and generated files expire after about one hour while the app is running.')
    return demo


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--share', action='store_true', help='Create a temporary public Gradio link')
    parser.add_argument('--host', default=os.environ.get('GRADIO_SERVER_NAME', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '7860')))
    args = parser.parse_args()
    demo = build_app()
    demo.queue(max_size=8, default_concurrency_limit=1).launch(
        server_name=args.host, server_port=args.port, share=args.share,
        theme=gr.themes.Base(primary_hue='neutral', neutral_hue='gray',
                             font=['Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif']),
        css=CSS, max_file_size='100mb', show_error=False,
        blocked_paths=[str(Path(ROOT_DIR) / '.git'), MODELS_DIR, str(Path(ROOT_DIR) / '.venv')])
