#!/usr/bin/env python3
"""MorphLab Studio launcher. Use --legacy for the previous Gradio workbench."""
import argparse
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).parent / '.cache/matplotlib'))
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')


def build_app():
    try:
        from legacy_app import build_app as legacy
    except ImportError as exc:
        raise SystemExit('Legacy Gradio is optional and is not part of the maintained Studio installation. Run without --legacy to open MorphLab Studio.') from exc
    return legacy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MorphLab · Face editing studio')
    parser.add_argument('--host', default=os.getenv('MorphLab_HOST', os.getenv('GRADIO_SERVER_NAME', '127.0.0.1')))
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '7860')))
    parser.add_argument('--legacy', action='store_true')
    parser.add_argument('--share', action='store_true', help='Temporary sharing for --legacy only')
    args = parser.parse_args()
    if args.legacy:
        build_app().queue(max_size=8).launch(server_name=args.host, server_port=args.port, share=args.share)
    else:
        if args.share:
            parser.error('--share requires --legacy. Studio runs locally or behind an HTTPS deployment endpoint.')
        import uvicorn
        uvicorn.run('modules.studio_api:app', host=args.host, port=args.port, ws_max_size=2_100_000, access_log=False)
