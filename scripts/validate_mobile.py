"""Compare PyTorch with the unmodified Paddle reference in isolated processes.

Paddle and PyTorch export colliding native symbols on macOS; never import both in one process.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CACHE = ROOT / '.cache/mobile-validation'
CACHE.mkdir(parents=True, exist_ok=True)


def reference(name):
    spec = importlib.util.spec_from_file_location('mobile_reference_'+name, ROOT/'third_party/mobilefaceswap'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_reference():
    import numpy as np
    import paddle
    paddle.set_device('cpu')
    arc, ref = reference('arcface'), reference('model')
    directory = ROOT/'models/mobilefaceswap'
    encoder = arc.ResNet(arc.IRBlock, [3, 4, 23, 3])
    encoder.set_state_dict(paddle.load(str(directory/'arcface.pdparams')))
    encoder.eval()
    weights = paddle.load(str(directory/'MobileFaceSwap_224.pdparams'))
    for file in sorted(CACHE.glob('input-*.npz')):
        data = np.load(file)
        with paddle.no_grad():
            identity, feature = encoder(paddle.to_tensor(data['source']))
            original = ref.FaceSwap(use_gpu=False)
            original.set_model_param(ref.l2_norm(identity), feature, weights)
            original.eval()
            image, mask = original(paddle.to_tensor(data['target']))
        np.savez(CACHE/('reference-'+file.name[6:]), image=image.numpy(), mask=mask.numpy())
        print('Reference complete:', file.name, flush=True)


def validate():
    import cv2
    import numpy as np
    import torch
    from modules.mobile_model import MobileRuntime, align
    from modules.runtime import registry
    directory = ROOT/'models/mobilefaceswap'
    engine = MobileRuntime(directory, 'cpu')
    manifest = json.loads((ROOT/'assets/examples/manifest.json').read_text())
    for pair in manifest['pairs']:
        source = cv2.imread(str(ROOT/'assets/examples'/Path(pair['source']).name))
        target = cv2.imread(str(ROOT/'assets/examples'/Path(pair['target']).name))
        source_face, target_face = registry.detect(source)[0], registry.detect(target)[0]
        crop, _ = align(source, source_face, 224)
        crop = cv2.resize(crop, (112, 112))[:, :, ::-1].transpose(2, 0, 1).copy()[None].astype(np.float32)/255
        normalized = (crop-np.array([.485, .456, .406], np.float32).reshape(1, 3, 1, 1))/np.array([.229, .224, .225], np.float32).reshape(1, 3, 1, 1)
        target_crop, _ = align(target, target_face, 224)
        blob = target_crop[:, :, ::-1].transpose(2, 0, 1).copy()[None].astype(np.float32)/255
        np.savez(CACHE/f"input-{pair['id']}.npz", source=normalized, target=blob)
        model = engine.source(source, source_face)
        with torch.inference_mode():
            image, mask = model(torch.from_numpy(blob))
        np.savez(CACHE/f"actual-{pair['id']}.npz", image=image.numpy(), mask=mask.numpy())
    subprocess.run([sys.executable, __file__, '--reference'], check=True, timeout=120)
    reports = []
    for pair in manifest['pairs']:
        expected = np.load(CACHE/f"reference-{pair['id']}.npz")
        actual = np.load(CACHE/f"actual-{pair['id']}.npz")
        error = float(np.abs(actual['image']-expected['image']).mean())
        reports.append({'pair':pair['id'], 'image_mae_0_1':error,
            'mask_mae_0_1':float(np.abs(actual['mask']-expected['mask']).mean()), 'passed':error<1e-4})
    (ROOT/'outputs/benchmarks/mobile-paddle-parity.json').write_text(json.dumps(reports,indent=2))
    print(json.dumps(reports,indent=2),flush=True)
    if not all(r['passed'] for r in reports):
        raise RuntimeError('The port differs from the Paddle reference. Do not select it.')
    file = directory/'manifest.json'
    data = json.loads(file.read_text())
    data['paddle_reference_parity'] = reports
    file.write_text(json.dumps(data,indent=2))


if __name__ == '__main__':
    run_reference() if '--reference' in sys.argv else validate()
