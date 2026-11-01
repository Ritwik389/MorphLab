"""Advisory source checks; these measurements are not a success probability."""

import cv2
import numpy as np


def analyse_source(frame, face, points=None):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = np.asarray(face.bbox, int)
    crop = frame[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]
    if not crop.size:
        raise ValueError("No clear face region. Try another portrait.")
    gray = cv2.cvtColor(cv2.resize(crop, (160, 160)), cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    clipping = float(np.mean((gray < 5) | (gray > 250)))
    warnings = []
    if min(crop.shape[:2]) < 128:
        warnings.append(
            "Use a larger portrait: the face is under 128 pixels wide or high."
        )
    if blur < 35:
        warnings.append("The face looks blurred. Try a sharper portrait.")
    if clipping > 0.2:
        warnings.append(
            "Strong shadows or highlights hide detail. Try more even lighting."
        )
    pose = None
    if points is not None:
        # Approximate camera intrinsics and a generic 3D face: advisory only.
        image = np.asarray(
            [
                face.kps[2],
                points[0],
                face.kps[0],
                face.kps[1],
                face.kps[3],
                face.kps[4],
            ],
            np.float64,
        )
        template = np.array(
            [
                [0, 0, 0],
                [0, -63, -12],
                [-43, 32, -26],
                [43, 32, -26],
                [-28, -28, -24],
                [28, -28, -24],
            ],
            np.float64,
        )
        camera = np.array([[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]], np.float64)
        ok, rotation, _ = cv2.solvePnP(
            template, image, camera, np.zeros((4, 1)), flags=cv2.SOLVEPNP_SQPNP
        )
        if ok:
            angles = cv2.RQDecomp3x3(cv2.Rodrigues(rotation)[0])[0]
            pitch, yaw, roll = [float((x + 90) % 180 - 90) for x in angles]
            pose = {"pitch": pitch, "yaw": yaw, "roll": roll, "approximate": True}
            if abs(yaw) > 35 or abs(pitch) > 35:
                warnings.append(
                    "A more front-facing portrait usually transfers identity better."
                )
    return {
        "status": "advisory" if warnings else "ready",
        "warnings": warnings,
        "face_pixels": list(crop.shape[:2][::-1]),
        "blur_variance": round(blur, 2),
        "clipped_fraction": round(clipping, 4),
        "pose": pose,
        "note": "Heuristic guidance, not a quality percentage or an occlusion detector.",
    }
