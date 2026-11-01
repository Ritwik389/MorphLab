MobileFaceSwap: A Lightweight Framework for Video Face Swapping, Xu et al., AAAI 2022.

Reference files model.py and arcface.py are retained unmodified from
https://github.com/Seanseattle/MobileFaceSwap/tree/master/models (retrieved 1 November 2026).
They are used only by the optional Paddle numerical comparison script.

The runtime port in modules/mobile_model.py replaces Paddle with PyTorch, transposes
linear checkpoint weights, maps batch-normalization parameters, specializes the generator
in memory per identity, and runs it on Apple's MPS GPU. The original architecture and
pretrained parameters are retained. This is an engineering adaptation, not a newly trained model.

Upstream license: ../MobileFaceSwap.LICENSE (Apache-2.0).
