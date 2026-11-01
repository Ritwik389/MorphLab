"""Compare native precision variants and the live model on the three bundled pairs."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import onnx
import onnxruntime as ort
import coremltools as ct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.runtime import registry, paste_face
from modules.mobile_model import MobileRuntime
from insightface.utils.face_align import norm_crop2

directory = ROOT/'outputs/quality'
directory.mkdir(parents=True,exist_ok=True)
options = ort.SessionOptions();options.intra_op_num_threads = 2;options.log_severity_level = 3
path = ROOT/'models/inswapper_128.onnx'
cpu = ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
emap = onnx.numpy_helper.to_array(onnx.load(str(path)).graph.initializer[-1])
models = {}
for file in (ROOT/'.cache/coreml').glob('*/manifest.json'):
    metadata = json.loads(file.read_text())
    if metadata['validated']:
        models[metadata['precision']] = ct.models.MLModel(str(file.parent/'swapper.mlpackage'))
mobile = MobileRuntime(ROOT/'models/mobilefaceswap','mps')
manifest = json.loads((ROOT/'assets/examples/manifest.json').read_text())
report = []
for pair in manifest['pairs']:
    source = cv2.imread(str(ROOT/'assets/examples'/Path(pair['source']).name))
    target = cv2.imread(str(ROOT/'assets/examples'/Path(pair['target']).name))
    source_face, face = registry.detect(source)[0], registry.detect(target)[0]
    embedding = registry.embedding(source,source_face)
    embedding /= np.linalg.norm(embedding)
    latent = embedding.reshape(1,-1)@emap;latent /= np.linalg.norm(latent)
    crop, transform = norm_crop2(target,face.kps,128)
    blob = cv2.dnn.blobFromImage(crop,1/255.,(128,128),swapRB=True)
    names = [x.name for x in cpu.get_inputs()]
    expected = cpu.run(None,{names[0]:blob,names[1]:latent})[0]
    outputs = {'cpu_fp32':expected}
    outputs.update({name:next(iter(model.predict({'target':blob,'source':latent}).values())) for name,model in models.items()})
    results = {}
    for name, pixels in outputs.items():
        fake = np.clip(pixels[0].transpose(1,2,0)[:,:,::-1]*255,0,255).astype(np.uint8)
        results[name] = paste_face(target,fake,transform)
        report.append({'pair':pair['id'],'model':name,'raw_mae_vs_fp32_0_1':float(np.abs(pixels-expected).mean())})
    identity = mobile.source(source,source_face)
    fake, transform, mask = mobile.predict(target,face,identity)
    results['mobile_mps'] = paste_face(target,fake,transform,mask)
    report.append({'pair':pair['id'],'model':'mobile_mps','raw_mae_vs_fp32_0_1':None})
    for name,result in results.items():
        cv2.imwrite(str(directory/f"{pair['id']}-{name}.jpg"),result)
        faces = registry.detect(result,recognition=True)
        entry = next(r for r in report if r['pair']==pair['id'] and r['model']==name)
        entry['source_output_embedding_cosine'] = float(np.dot(embedding,faces[0].normed_embedding)) if faces else None
        entry['quality_metrics_are_heuristics'] = True
(ROOT/'outputs/benchmarks/quality-comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
