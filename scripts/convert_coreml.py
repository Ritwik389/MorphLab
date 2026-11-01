"""Convert our verified ONNX weights to native CoreML; benchmark before selection."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def convert():
    parser = argparse.ArgumentParser()
    parser.add_argument('--precision', choices=['fp16', 'int8'], default='fp16')
    parser.add_argument('--runs', type=int, default=12)
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('Native CoreML requires macOS.')
    import coremltools as ct
    import onnx
    import torch
    from onnx2torch import convert as to_torch

    torch.set_num_threads(2)
    source = ROOT / 'models/inswapper_128.onnx'
    digest = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
    compatibility = {'model_sha256': digest, 'converter': 2, 'precision': args.precision,
                     'shape': [1, 3, 128, 128], 'coremltools': ct.__version__,
                     'macos': platform.mac_ver()[0], 'arch': platform.machine()}
    key = hashlib.sha256(json.dumps(compatibility, sort_keys=True).encode()).hexdigest()[:20]
    directory = ROOT / '.cache/coreml' / key
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / 'swapper.mlpackage'
    graph = onnx.load(source)
    emap = onnx.numpy_helper.to_array(graph.graph.initializer[-1])
    np.save(directory / 'emap.npy', emap)
    if not output.exists():
        print('Reconstructing and tracing verified weights…', flush=True)
        module = to_torch(graph).eval()
        trace = torch.jit.trace(module, (torch.zeros(1, 3, 128, 128), torch.zeros(1, 512)))
        model = ct.convert(trace, inputs=[ct.TensorType(name='target', shape=(1, 3, 128, 128)),
                                         ct.TensorType(name='source', shape=(1, 512))],
                           convert_to='mlprogram', compute_precision=ct.precision.FLOAT16,
                           minimum_deployment_target=ct.target.macOS13)
        if args.precision == 'int8':
            import coremltools.optimize.coreml as cto
            config = cto.OptimizationConfig(global_config=cto.OpLinearQuantizerConfig(
                mode='linear_symmetric', dtype='int8'))
            model = cto.linear_quantize_weights(model, config=config)
        model.save(str(output))
        del model, module, trace
    print('Loading native model…', flush=True)
    model = ct.models.MLModel(str(output), compute_units=ct.ComputeUnit.ALL)
    # Real aligned portraits exercise numerical parity rather than an all-zero input.
    import cv2
    from modules.live_camera import detect_faces
    from insightface.utils.face_align import norm_crop2
    face = cv2.imread(str(ROOT / 'assets/examples/target.jpg'))
    observations, _ = detect_faces(face)
    crop, _ = norm_crop2(face, observations[0]['kps'], 128)
    blob = cv2.dnn.blobFromImage(crop, 1 / 255., (128, 128), swapRB=True)
    rng = np.random.default_rng(7)
    latent = rng.normal(size=(1, 512)).astype(np.float32)
    latent /= np.linalg.norm(latent)
    inputs = {'target': blob, 'source': latent}
    timings = []
    for i in range(args.runs + 2):
        start = time.perf_counter()
        result = next(iter(model.predict(inputs).values()))
        elapsed = (time.perf_counter() - start) * 1000
        if i >= 2:
            timings.append(elapsed)
        if not np.isfinite(result).all():
            raise RuntimeError('Non-finite CoreML output; refusing this model.')
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    reference = ort.InferenceSession(str(source), sess_options=options, providers=['CPUExecutionProvider'])
    names = [v.name for v in reference.get_inputs()]
    expected = reference.run(None, {names[0]: blob, names[1]: latent})[0]
    mae = float(np.abs(result.astype(np.float32) - expected).mean())
    manifest = {**compatibility, 'path': str(output.relative_to(ROOT)),
                'mean_ms': float(np.mean(timings)), 'p95_ms': float(np.percentile(timings, 95)),
                'samples_ms': timings, 'parity_mae_0_1': mae,
                'validated': mae <= 2 / 255., 'scope': 'model-only; not webcam FPS'}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    convert()
