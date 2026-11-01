import importlib
import unittest
from unittest.mock import patch


def _load_face_analyser():
    # Use the real module; patch only the analysis call under test.
    return importlib.import_module("modules.face_analyser")


class Face:
    def __init__(self, left):
        self.bbox = [left, 0, 10, 10]


class GetOneFaceTests(unittest.TestCase):
    def test_uses_supplied_detected_faces_without_reanalysing_frame(self):
        face_analyser = _load_face_analyser()
        right = Face(20)
        left = Face(5)

        with patch.object(
            face_analyser,
            "_analyse_faces",
            side_effect=AssertionError("should not analyse"),
        ):
            self.assertIs(face_analyser.get_one_face("frame", [right, left]), left)

    def test_supplied_empty_detected_faces_returns_none(self):
        face_analyser = _load_face_analyser()

        with patch.object(
            face_analyser,
            "_analyse_faces",
            side_effect=AssertionError("should not analyse"),
        ):
            self.assertIsNone(face_analyser.get_one_face("frame", []))

    def test_without_supplied_faces_preserves_existing_detection_path(self):
        face_analyser = _load_face_analyser()
        right = Face(30)
        left = Face(3)

        with patch.object(face_analyser, "_is_dml", return_value=False), patch.object(
            face_analyser,
            "_analyse_faces",
            return_value=[right, left],
        ) as analyse:
            self.assertIs(face_analyser.get_one_face("frame"), left)

        analyse.assert_called_once_with("frame")


if __name__ == "__main__":
    unittest.main()
