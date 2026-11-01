# Models, data and intended use

MorphLab integrates existing pretrained models for a college/research face-editing demonstration. It does not claim a new generator, universal deepfake detection, anonymity, or state-of-the-art recognition accuracy.

| Component | Purpose | Evidence / limit |
|---|---|---|
| InsightFace detection/ArcFace | Faces and appearance association | Recognition similarity is a heuristic, not an identity probability |
| InsightFace106 landmarks | Current-frame alignment during motion | Does not supply per-landmark visibility or universal occlusion detection |
| INSwapper128 CPU/native CoreML | Higher-fidelity standard photo/video path | Precision parity and actual runtime must be checked |
| MobileFaceSwap224/MPS | Lightweight Mac live generator | Faster but historically weaker identity similarity |
| AdaFaceIR50 WebFace4M | Offline independent identity evaluator | Separate model; pretraining identities may overlap other models |

Original model sources, pinned revisions and SHA-256 values are in `models-manifest.json`; Mobile and CoreML compatibility manifests accompany their local weights. AdaFace source/license is retained under `third_party/adaface`, and checkpoint/source checksums in `experiments/adaface.json`. Run original-author parity validation separately from performance benchmarking.

The initial motion corpus uses Livingstone & Russo's RAVDESS, doi:10.1371/journal.pone.0196391, https://zenodo.org/records/1188976. It is CC BY-NC-SA4.0: non-commercial, attribution and share-alike restrictions apply. Downloaded raw media stays in `.cache/evaluation/corpus` and is excluded from Git, Docker and public CI artifacts. Development actors01–04, validation05–08 and held-out09–12 do not cross partitions.

Studio speech/expression clips do not establish diverse natural lighting, broad head rotations, real people crossing, demographic fairness or coffee-mug occlusion. Derived composites explicitly record their synthetic provenance and composition-box annotations; these are not reviewed anatomical face boxes. Additional authorized footage and annotation review are required for those claims. Public-domain NASA sample-image attribution remains in `assets/examples/ATTRIBUTION.md`.

Use source photographs and target footage with appropriate rights/permission. Do not infer commercial rights to pretrained weights from an open-source code licence. This iteration does not add persistent biometric favourites, automatic camera access on landing, or external telemetry.

Live analysis now uses InsightFace SCRFD500MF and MobileFaceNet (buffalo_sc, research-only pretrained weights) to reduce per-frame detection/re-identification cost. These are used for live association, not as a replacement source encoder for the generator or the independent AdaFace evaluator. The stronger standard analyser remains for exports. Accuracy/appearance thresholds need the same held-out tracking evaluation; latency gains are not proof of equal recognition accuracy.

Native CoreML's INT8 label describes compressed weights; it does not imply that every operation uses integer arithmetic. Compute units are eligible under CoreML's selected configuration; per-operation GPU/Neural Engine placement has not been profiled with Instruments. Mobile inference uses the validated Torch MPS device. Available providers, selected runtime, and actual measured performance are separate facts.

The author requested that human release checks remain pending. Review-kit generation does not constitute author review: the rating sheet is blank, reviewer count is zero, and the held-out corpus remains unfrozen/unreviewed. Natural 3D turns, genuine crossings, challenging real lighting and foreground-object occlusion remain unvalidated conditions.
