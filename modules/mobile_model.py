"""PyTorch port of MobileFaceSwap (Xu et al., AAAI 2022).

Adapted from Seanseattle/MobileFaceSwap, Apache-2.0. See third_party/MobileFaceSwap.LICENSE.
Changes: PyTorch layers, checkpoint conversion, in-memory identity specialization, MPS inference.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn


def final_layers():
    return nn.Sequential(nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True),
        nn.Conv2d(32, 8, 1), nn.BatchNorm2d(8), nn.LeakyReLU(.1),
        nn.Conv2d(8, 3, 3, padding=1), nn.BatchNorm2d(3), nn.LeakyReLU(.1),
        nn.Conv2d(3, 3, 3, padding=1), nn.Tanh())


def mask_layers():
    channels = [512, 128, 64, 32, 8, 2]
    layers = [nn.Sequential(nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True),
        nn.Conv2d(a, a, 3, padding=1, groups=a), nn.Conv2d(a, b, 1), nn.BatchNorm2d(b),
        nn.LeakyReLU(.1)) for a, b in zip(channels, channels[1:])]
    return nn.Sequential(*layers, nn.Conv2d(2, 1, 3, padding=1), nn.Sigmoid())


class Generator(nn.Module):
    def __init__(self):
        super().__init__()
        channels = [3, 32, 64, 128, 256, 512]
        self.Encoder = nn.ModuleList([nn.Sequential(nn.Conv2d(a, a, 4, stride=2, padding=1, groups=a),
            nn.Conv2d(a, b, 1)) for a, b in zip(channels, channels[1:])])
        self.Decoder = nn.ModuleList([nn.Sequential(nn.Conv2d(a, a, 3, padding=1, groups=a),
            nn.Conv2d(a, b, 1)) for a, b in zip([512, 512, 256, 128], [256, 128, 64, 32])])
        self.final = final_layers()
        self.mask = mask_layers()

    def forward(self, data):
        x = (data-.5)/.5
        features = []
        for layer in self.Encoder:
            x = torch.nn.functional.leaky_relu(layer(x), .1)
            features.append(x)
        mask = self.mask(x)
        y = x
        for i, layer in enumerate(self.Decoder):
            y = torch.nn.functional.interpolate(y, scale_factor=2, mode='bilinear', align_corners=True)
            y = torch.nn.functional.leaky_relu(layer(y), .1)
            if i < 3:
                y = torch.cat((y, features[3-i]), dim=1)
        image = (1+self.final(y))/2
        return image*mask+(1-mask)*data, mask


class ConvBlock(nn.Module):
    def __init__(self, a, b):
        super().__init__()
        self.conv = nn.Conv2d(a, b, 3, padding=1)
        self.norm = nn.BatchNorm2d(b)
        self.weight = nn.Conv2d(b, b, 3, padding=1)

    def forward(self, x):
        out = torch.nn.functional.leaky_relu(self.norm(self.conv(x)), .1)
        return out, self.weight(out)


class WeightPrediction(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Conv2d(512, 512, 4)
        self.first_decoder = nn.Conv2d(512, 512, 2)
        self.decoder_norm = nn.BatchNorm2d(512)
        self.norm = nn.BatchNorm2d(512)
        self.encoder = nn.ModuleList([ConvBlock(a, b) for a, b in zip([512, 256, 128, 64, 32], [256, 128, 64, 32, 3])])
        self.decoder = nn.ModuleList([ConvBlock(a, b) for a, b in zip([512, 512, 512, 256], [512, 512, 256, 128])])

    def forward(self, feature):
        feature = torch.nn.functional.leaky_relu(self.norm(self.first(feature)), .1)
        x = feature
        encoder = []
        for layer in self.encoder:
            x, weight = layer(x)
            encoder.append(weight)
        y = torch.nn.functional.leaky_relu(self.decoder_norm(self.first_decoder(feature)), .1)
        decoder = []
        for layer in self.decoder:
            y, weight = layer(y)
            decoder.append(weight)
        return encoder[::-1], decoder


class Modulation(nn.Module):
    def __init__(self, a, b):
        super().__init__()
        self.style = nn.Linear(512, a)
        self.weight = nn.Parameter(torch.empty(b, a, 1, 1))

    def forward(self, identity):
        style = self.style(identity).reshape(1, 1, -1, 1, 1)
        weight = self.weight.unsqueeze(0)*(style+1)
        weight = weight*torch.rsqrt(weight.square().sum(dim=(2, 3, 4), keepdim=True)+1e-16)
        return weight[0]


class IdentityWeights(nn.Module):
    def __init__(self):
        super().__init__()
        self.EncoderModulation = nn.ModuleList([Modulation(a, b) for a, b in zip([3, 32, 64, 128, 256], [32, 64, 128, 256, 512])])
        self.DecoderModulation = nn.ModuleList([Modulation(a, b) for a, b in zip([512, 512, 256, 128], [256, 128, 64, 32])])
        self.predictor = WeightPrediction()
        self.final = final_layers()
        self.mask = mask_layers()

    def specialize(self, identity, feature):
        encoder, decoder = self.predictor(feature)
        net = Generator().eval()
        with torch.no_grad():
            for i, layer in enumerate(net.Encoder):
                layer[0].weight.copy_(encoder[i][0].unsqueeze(1))
                layer[0].bias.zero_()
                layer[1].weight.copy_(self.EncoderModulation[i](identity))
                layer[1].bias.zero_()
            for i, layer in enumerate(net.Decoder):
                layer[0].weight.copy_(decoder[i][0].unsqueeze(1))
                layer[0].bias.zero_()
                layer[1].weight.copy_(self.DecoderModulation[i](identity))
                layer[1].bias.zero_()
            net.final.load_state_dict(self.final.state_dict())
            net.mask.load_state_dict(self.mask.state_dict())
        return net


class SEBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(nn.Linear(channels, channels//16), nn.PReLU(),
                                nn.Linear(channels//16, channels), nn.Sigmoid())
    def forward(self, x):
        return x*self.fc(self.avg_pool(x).flatten(1)).reshape(x.shape[0], x.shape[1], 1, 1)


class IRBlock(nn.Module):
    def __init__(self, a, b, stride=1):
        super().__init__()
        self.bn0 = nn.BatchNorm2d(a)
        self.conv1 = nn.Conv2d(a, a, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(a)
        self.prelu = nn.PReLU()
        self.conv2 = nn.Conv2d(a, b, 3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(b)
        self.downsample = nn.Sequential(nn.Conv2d(a, b, 1, stride=stride, bias=False), nn.BatchNorm2d(b)) if a != b or stride != 1 else None
        self.se = SEBlock(b)
    def forward(self, x):
        out = self.prelu(self.bn1(self.conv1(self.bn0(x))))
        out = self.se(self.bn2(self.conv2(out)))
        return self.prelu(out+(x if self.downsample is None else self.downsample(x)))


class IdentityEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 64, 3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.prelu = nn.PReLU()
        self.maxpool = nn.MaxPool2d(2, 2)
        a = 64
        for i, (b, count) in enumerate(zip([64, 128, 256, 512], [3, 4, 23, 3]), 1):
            layers = [IRBlock(a, b, 1 if i == 1 else 2)] + [IRBlock(b, b) for _ in range(count-1)]
            setattr(self, f'layer{i}', nn.Sequential(*layers))
            a = b
        self.bn2 = nn.BatchNorm2d(512)
        self.dropout = nn.Dropout()
        self.fc = nn.Linear(512*7*7, 512)
        self.bn3 = nn.BatchNorm1d(512)
    def forward(self, x):
        x = self.maxpool(self.prelu(self.bn1(self.conv1(x))))
        for layer in [self.layer1, self.layer2, self.layer3, self.layer4]:
            x = layer(x)
        feature = self.dropout(self.bn2(x))
        return self.bn3(self.fc(feature.flatten(1))), feature


class ArrayUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed = {('numpy.core.multiarray', '_reconstruct'), ('numpy.core.multiarray', 'scalar'),
                   ('numpy', 'ndarray'), ('numpy', 'dtype'), ('collections', 'OrderedDict')}
        if (module, name) not in allowed:
            raise ValueError('Checkpoint contains unsupported objects.')
        return super().find_class(module, name)


def load_paddle(module, path):
    with Path(path).open('rb') as stream:
        values = ArrayUnpickler(stream).load()
    state = {}
    modules = dict(module.named_modules())
    for key, value in values.items():
        if key == 'StructuredToParameterName@@':
            continue
        name = key.replace('._mean', '.running_mean').replace('._variance', '.running_var').replace('._weight', '.weight')
        if not isinstance(value, np.ndarray):
            raise ValueError('Checkpoint value is not an array.')
        owner = modules.get(name.rsplit('.', 1)[0])
        if isinstance(owner, nn.Linear) and name.endswith('.weight'):
            value = value.T
        state[name] = torch.from_numpy(value.copy())
    result = module.load_state_dict(state, strict=False)
    missing = [key for key in result.missing_keys if not key.endswith('num_batches_tracked')]
    if missing or result.unexpected_keys:
        raise ValueError(f'Checkpoint architecture mismatch: {missing}, {result.unexpected_keys}')
    return module.eval()


def align(frame, face, size):
    template = np.array([[38.29459953, 51.69630051], [73.53179932, 51.50139999], [56.02519989, 71.73660278],
                         [41.54930115, 92.3655014], [70.72990036, 92.20410156]])*size/112
    design = np.column_stack((np.asarray(face.kps, np.float64), np.ones(5)))
    transform = np.linalg.lstsq(design, template, rcond=None)[0].T.astype(np.float32)
    return cv2.warpAffine(frame, transform, (size, size)), transform


class MobileRuntime:
    def __init__(self, directory, device='mps'):
        import os
        torch.set_num_threads(2)
        self.device = device
        self.mask_mode = os.getenv('AIMS_MASK_MODE', 'soft')
        self.encoder = load_paddle(IdentityEncoder(), Path(directory)/'arcface.pdparams')
        self.weights = load_paddle(IdentityWeights(), Path(directory)/'MobileFaceSwap_224.pdparams')

    @torch.no_grad()
    def source(self, frame, face):
        crop, _ = align(frame, face, 224)
        crop = cv2.resize(crop, (112, 112))
        tensor = torch.from_numpy(np.ascontiguousarray(crop[:, :, ::-1].transpose(2, 0, 1))).float().unsqueeze(0)/255
        mean = torch.tensor([.485, .456, .406]).reshape(1, 3, 1, 1)
        std = torch.tensor([.229, .224, .225]).reshape(1, 3, 1, 1)
        identity, feature = self.encoder((tensor-mean)/std)
        identity = torch.nn.functional.normalize(identity)
        return self.weights.specialize(identity, feature).to(self.device).eval()

    @torch.inference_mode()
    def predict(self, frame, face, model, timings=None):
        import time
        started = time.perf_counter()
        crop, transform = align(frame, face, 224)
        tensor = torch.from_numpy(np.ascontiguousarray(crop[:, :, ::-1].transpose(2, 0, 1))).float().unsqueeze(0).to(self.device)/255
        aligned = time.perf_counter()
        output, mask = model(tensor)
        pixels = output[0].permute(1, 2, 0).cpu().numpy()[:, :, ::-1]
        mask = mask[0, 0].cpu().numpy()
        generated = time.perf_counter()
        if not np.isfinite(pixels).all() or not np.isfinite(mask).all():
            raise RuntimeError('Mobile GPU produced invalid pixels.')
        fake = np.clip(pixels*255, 0, 255).astype(np.uint8)
        if self.mask_mode == 'binary':
            mask = (mask > .001).astype(np.float32)
            kernel = np.ones((11, 11), np.uint8)
            mask = cv2.erode(cv2.dilate(mask, kernel), kernel, iterations=2)
        elif self.mask_mode == 'raw_soft':
            mask = np.clip(mask, 0, 1)
            oval = np.zeros_like(mask)
            cv2.ellipse(oval, (112,115), (96,106), 0, 0, 360, 1, -1)
            mask *= cv2.GaussianBlur(oval, (15,15), 3)
        else:
            # The network already gates its generated pixels internally. Applying its
            # raw gate a second time weakens identity. Map only its boundary through
            # a smooth transition around the original .001 coverage threshold.
            mask = np.clip((mask-.00025)/.0015,0,1).astype(np.float32)
            mask = mask*mask*(3-2*mask)
            kernel = np.ones((11,11),np.uint8)
            mask = cv2.erode(cv2.dilate(mask,kernel),kernel,iterations=2)
            oval = np.zeros_like(mask)
            cv2.ellipse(oval,(112,115),(104,112),0,0,360,1,-1)
            mask *= cv2.GaussianBlur(oval,(11,11),2)
        mask = cv2.blur(mask, (7,7))
        border = np.zeros_like(mask);border[10:-10, 10:-10] = 1
        mask *= cv2.blur(border, (11, 11))
        if timings is not None:
            timings.update(alignment_upload_ms=(aligned-started)*1000,
                generator_download_ms=(generated-aligned)*1000,
                mask_ms=(time.perf_counter()-generated)*1000)
        return fake, transform, mask
