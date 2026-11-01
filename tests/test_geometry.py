import cv2
import numpy as np
import pytest


@pytest.mark.model
def test_dense_five_point_topology_matches_detector():
    from modules.runtime import ModelRegistry, RuntimeConfig

    model = ModelRegistry(RuntimeConfig("cpu"))
    image = cv2.imread("assets/examples/target.jpg")
    face = model.detect(image)[0]
    expected = face.kps.copy()
    points = model.landmarks(image, face)
    assert points.shape == (106, 2)
    assert np.linalg.norm(face.kps - expected, axis=1).max() < 15
    assert face.kps[0, 0] < face.kps[1, 0] and face.kps[3, 0] < face.kps[4, 0]
