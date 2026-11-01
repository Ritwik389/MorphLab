"""Independent offline AdaFace evaluation. Never imported by the live server."""

import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class AdaFaceEvaluator:
    def __init__(self):
        import torch

        self.torch = torch
        directory = ROOT / "models/evaluation/adaface"
        manifest = json.loads((directory / "manifest.json").read_text())
        path = directory / "adaface_ir50_webface4m.ckpt"
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
                raise ValueError("AdaFace checkpoint hash mismatch.")
        source = ROOT / "third_party/adaface/net.py"
        if (
            hashlib.sha256(source.read_bytes()).hexdigest()
            != manifest["source_sha256"]["net.py"]
        ):
            raise ValueError("AdaFace source hash mismatch.")
        spec = importlib.util.spec_from_file_location("aims_adaface", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.net = module.build_model("ir_50")
        # Do not allow arbitrary checkpoint pickle execution.
        state = torch.load(path, map_location="cpu", weights_only=True)["state_dict"]
        self.net.load_state_dict(
            {
                k.removeprefix("model."): v
                for k, v in state.items()
                if k.startswith("model.")
            }
        )
        self.net.eval()
        torch.set_num_threads(2)
        self.manifest = manifest

    def embedding(self, frame, face):
        from insightface.utils.face_align import norm_crop

        crop = norm_crop(frame, face.kps, 112)  # OpenCV BGR stays BGR, per authors.
        data = (
            np.ascontiguousarray(crop.transpose(2, 0, 1)).astype(np.float32) / 127.5 - 1
        )
        with self.torch.inference_mode():
            features, _ = self.net(self.torch.from_numpy(data).unsqueeze(0))
        vector = features[0].numpy()
        return vector / max(1e-8, float(np.linalg.norm(vector)))
