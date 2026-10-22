"""Fixed-shape, tensor-only PatchCore candidate for portable inference.

Only the verified WideResNet50 layer2/layer3, 1NN, 224px recipe is supported.
No image decoding or Gaussian heatmap smoothing is part of this graph.
"""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .engine import PatchCore
from patchcore import backbones


class ExactAdaptiveMean(nn.Module):
    def __init__(self, input_size, output_size):
        super().__init__()
        starts = np.floor(np.arange(output_size) * input_size / output_size).astype('int64')
        ends = np.ceil((np.arange(output_size) + 1) * input_size / output_size).astype('int64')
        width = int((ends - starts).max())
        indices = starts[:, None] + np.arange(width)[None, :]
        valid = indices < ends[:, None]
        self.register_buffer('indices', torch.from_numpy(np.minimum(indices, input_size - 1).flatten()))
        self.register_buffer('mask', torch.from_numpy(valid.astype('float32')))
        self.register_buffer('lengths', torch.from_numpy((ends - starts).astype('float32')))
        self.output_size, self.width = output_size, width

    def forward(self, x):
        selected = torch.index_select(x, 1, self.indices).reshape(-1, self.output_size, self.width)
        return (selected * self.mask).sum(dim=-1) / self.lengths


class PortablePatchCore(nn.Module):
    def __init__(self, detector: PatchCore):
        super().__init__()
        if detector.backbone.name != 'wideresnet50' or detector.anomaly_scorer.n_nearest_neighbours != 1:
            raise ValueError('Portable candidate supports only the verified WideResNet50 1NN recipe')
        if tuple(detector.layers_to_extract_from) != ('layer2', 'layer3') or tuple(detector.input_shape) != (3, 224, 224) or detector.target_embed_dimension != 384 or detector.patch_maker.patchsize != 3:
            raise ValueError('Portable candidate recipe mismatch')
        backbone = backbones.load('wideresnet50', pretrained=False)
        backbone.load_state_dict(detector.backbone.state_dict(), strict=True)
        backbone.eval()
        self.stem = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu, backbone.maxpool, backbone.layer1)
        self.layer2, self.layer3 = backbone.layer2, backbone.layer3
        self.pool2 = ExactAdaptiveMean(512 * 9, 1024)
        self.pool3 = ExactAdaptiveMean(1024 * 9, 1024)
        self.pool_final = ExactAdaptiveMean(2048, 384)
        index = detector.anomaly_scorer.nn_method.search_index
        bank = np.asarray(index.reconstruct_n(0, index.ntotal), dtype='float32')
        self.register_buffer('bank_t', torch.from_numpy(bank.T.copy()))
        self.register_buffer('bank_norm', torch.from_numpy((bank ** 2).sum(axis=1))[None, :])
        if detector.score_min is None or detector.score_max is None or detector.score_max <= detector.score_min:
            raise ValueError('Portable candidate needs frozen score normalisation')
        self.score_min, self.score_range = float(detector.score_min), float(detector.score_max - detector.score_min)
        self.eval()

    def embed(self, image):
        layer2 = self.layer2(self.stem(image))
        layer3 = self.layer3(layer2)
        patches2 = F.unfold(layer2, 3, padding=1).transpose(1, 2).reshape(784, 512 * 9)
        patches3 = F.unfold(layer3, 3, padding=1).reshape(1, 1024 * 9, 14, 14)
        patches3 = F.interpolate(patches3, size=(28, 28), mode='bilinear', align_corners=False)
        patches3 = patches3.reshape(1, 1024 * 9, 784).transpose(1, 2).reshape(784, 1024 * 9)
        return self.pool_final(torch.cat((self.pool2(patches2), self.pool3(patches3)), dim=1))

    def forward(self, image):
        features = self.embed(image)
        distances = (features.square().sum(dim=1, keepdim=True) + self.bank_norm - 2 * features.matmul(self.bank_t)).clamp_min(0)
        patches = distances.min(dim=1).values
        score = ((patches.max().reshape(1) - self.score_min) / self.score_range).clamp_min(0)
        return score, patches.reshape(1, 28, 28)
