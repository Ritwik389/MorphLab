"""Real codec/process boundaries; model inference is deliberately replaced here."""

import shutil
import subprocess
import cv2
import numpy as np
import pytest
from modules import studio_jobs, research


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_video_export_uses_display_dimensions(tmp_path, monkeypatch, rotation):
    base, target = tmp_path / "base.mp4", tmp_path / "rotated.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=5",
            "-t",
            "0.4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(base),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-display_rotation",
            str(rotation),
            "-i",
            str(base),
            "-c",
            "copy",
            str(target),
        ],
        check=True,
    )
    capture = cv2.VideoCapture(str(target))
    capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    ok, frame = capture.read()
    capture.release()
    assert ok
    monkeypatch.setattr(research, "OUTPUT_ROOT", tmp_path / "jobs")
    monkeypatch.setattr(studio_jobs.registry, "detect", lambda *a, **kw: [])
    job = studio_jobs.Job()
    job.directory.mkdir(parents=True)
    studio_jobs.run_job(job, None, target, "video", "blur", False, 1)
    assert job.state == "complete", job.message
    result = cv2.VideoCapture(str(job.directory / "result.mp4"))
    ok, output = result.read()
    result.release()
    assert ok and output.shape[:2] == frame.shape[:2]
    assert np.abs(output.astype(float) - frame.astype(float)).mean() < 20
    assert [job.report["width"], job.report["height"]] == list(frame.shape[1::-1])


def test_exif_orientation_is_applied_before_processing():
    from PIL import Image

    image = Image.new("RGB", (80, 120), "white")
    image.getexif()[274] = 6
    assert research.read_image(image).shape[:2] == (80, 120)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_video_longer_than_audio_is_not_truncated(tmp_path, monkeypatch):
    target = tmp_path / "short-audio.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(target),
        ],
        check=True,
    )
    monkeypatch.setattr(research, "OUTPUT_ROOT", tmp_path / "jobs")
    monkeypatch.setattr(studio_jobs.registry, "detect", lambda *a, **kw: [])
    job = studio_jobs.Job()
    job.directory.mkdir(parents=True)
    studio_jobs.run_job(job, None, target, "video", "blur", False, 1)
    assert job.state == "complete", job.message
    duration = research.probe_video(str(job.directory / "result.mp4"))[
        "duration_seconds"
    ]
    assert 1.9 <= duration <= 2.1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_ci_camera_fixture_works_with_manifest_but_without_downloaded_corpus(
    tmp_path, monkeypatch
):
    import importlib.util
    import json
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "camera_fixture", root / "scripts/build_camera_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "experiments").mkdir()
    (tmp_path / "assets/examples").mkdir(parents=True)
    shutil.copy(
        root / "assets/examples/target.jpg", tmp_path / "assets/examples/target.jpg"
    )
    (tmp_path / "experiments/corpus.json").write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "split": "development",
                        "identity": "ravdess-01",
                        "path": "missing.mp4",
                    }
                ]
            }
        )
    )
    output = tmp_path / "camera.y4m"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["build_camera_fixture.py", "--output", str(output)]
    )
    module.main()
    manifest = json.loads(output.with_suffix(".json").read_text())
    assert manifest["frames"] == 120 and manifest["scope"].startswith("Synthetic")
    capture = cv2.VideoCapture(str(output))
    ok, frame = capture.read()
    capture.release()
    assert ok and frame.shape[:2] == (480, 640)
