"""Portable lock semantics, without pretending to execute another OS's wheels."""

from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement


def test_web_lock_selects_platform_dependencies_for_python_311():
    lock = Path(__file__).resolve().parents[1] / 'requirements-web.lock'
    requirements = [
        Requirement(line.rstrip(' \\'))
        for line in lock.read_text().splitlines()
        if line and not line[0].isspace() and not line.startswith('#')
    ]

    def selected(platform):
        environment = {**default_environment(), 'python_version': '3.11',
                       'python_full_version': '3.11.9', 'sys_platform': platform,
                       'platform_python_implementation': 'CPython'}
        return {r.name for r in requirements if r.marker is None or r.marker.evaluate(environment)}

    windows = selected('win32')
    assert 'uvloop' not in windows
    assert {'colorama', 'pyreadline3', 'uvicorn', 'onnxruntime'} <= windows
    for platform in ['linux', 'darwin']:
        packages = selected(platform)
        assert 'uvloop' in packages
        assert 'pyreadline3' not in packages
