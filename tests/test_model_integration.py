"""Real weights, separate from mocks. CI may deselect model tests; release must run them."""

from pathlib import Path
import cv2
import numpy as np
import pytest
from modules.paths import MODELS_DIR


@pytest.mark.model
def test_real_cpu_model_detect_enroll_swap():
    if not (Path(MODELS_DIR) / "inswapper_128.onnx").exists():
        pytest.skip("Real weights unavailable")
    from modules.runtime import ModelRegistry, RuntimeConfig

    model = ModelRegistry(RuntimeConfig("cpu"))
    source = cv2.imread("assets/examples/source.png")
    target = cv2.imread("assets/examples/target.jpg")
    face = model.detect(target)[0]
    model.landmarks(target, face)
    identity = model.source(source)
    result = model.swap(target, face, identity)
    assert result.shape == target.shape and np.isfinite(result).all()
    assert np.abs(result.astype(float) - target).mean() > 0.1
    assert model.status()["active_runtime"] == "ONNX Runtime · CPUExecutionProvider"


@pytest.mark.model
def test_real_light_tracking_returns_consistent_embedding_space():
    from modules.runtime import ModelRegistry, RuntimeConfig

    model = ModelRegistry(RuntimeConfig("cpu"))
    frame = cv2.imread("assets/examples/target.jpg")
    if not (Path(MODELS_DIR) / "insightface/models/buffalo_sc/det_500m.onnx").exists():
        pytest.skip("Light tracking weights unavailable")
    faces = model.live_detect(frame)
    assert len(faces) == 1
    feature = model.live_embedding(frame, faces[0])
    assert feature.shape == (512,) and np.isfinite(feature).all()
    assert "500MF" in model.live_tracking_kind
