"""Frozen patch-feature backbones behind one interface.

Every backbone maps a batch of ImageNet-normalized images (B x 3 x H x W) to
patch features of shape (B, h * w, D) plus the patch grid (h, w). The detector
never sees which network produced them, so DINOv2 and the inherited PatchCore
embedding can be compared with the same shots, splits and scoring code.
"""
from __future__ import annotations

from typing import Protocol, Sequence, Tuple

import numpy as np
import torch


class PatchBackbone(Protocol):
    name: str

    def embed(self, images: torch.Tensor) -> Tuple[np.ndarray, Tuple[int, int]]:
        """Return float32 patch features (B, h * w, D) and the grid (h, w)."""


class DinoV2Backbone:
    """Last-layer DINOv2 patch tokens via timm (as used by AnomalyDINO).

    ``pretrained=True`` downloads weights from the Hugging Face hub on first
    use; the owner runs this on a machine or Colab with that access. Tests use
    ``pretrained=False`` and never download.
    """

    def __init__(self, model_name: str = "vit_small_patch14_dinov2.lvd142m",
                 image_size: int = 224, pretrained: bool = True,
                 device: torch.device = torch.device("cpu")):
        import timm

        self.name = f"dinov2:{model_name}@{image_size}"
        self.device = device
        # img_size resamples the pretrained position embedding to the chosen
        # input size; the patch grid is then image_size / 14 on each side.
        self.model = timm.create_model(model_name, pretrained=pretrained,
                                       img_size=image_size, num_classes=0)
        self.model.eval().to(device)
        self.grid = tuple(int(x) for x in self.model.patch_embed.grid_size)

    def embed(self, images):
        with torch.no_grad():
            tokens = self.model.forward_features(images.to(self.device, torch.float))
        # Drop the class token and any register tokens; keep spatial patches.
        tokens = tokens[:, self.model.num_prefix_tokens:]
        if tokens.shape[1] != self.grid[0] * self.grid[1]:
            raise ValueError(f"Unexpected token count {tokens.shape[1]} for grid {self.grid}")
        return tokens.cpu().numpy().astype(np.float32), self.grid


class PatchCoreBackbone:
    """The repository's PatchCore embedding, exactly as Phase 1 configured it.

    Uses ``patchcore.patchcore.PatchCore._embed``: WideResNet-50-2 layer2 and
    layer3, 3x3 local patch aggregation, 1024-dimensional preprocessing and a
    384-dimensional target embedding. Construction order follows
    ``bin/run_patchcore1.py`` (load backbone, then ``PatchCore.load``), so the
    inherited feature-shape probe behaves as it did for the Phase 1 models.
    ``network`` lets tests inject a small random-weight module instead.
    """

    def __init__(self, backbone_name: str = "wideresnet50",
                 layers: Sequence[str] = ("layer2", "layer3"), image_size: int = 224,
                 pretrain_embed_dimension: int = 1024, target_embed_dimension: int = 384,
                 patchsize: int = 3, pretrained: bool = True,
                 device: torch.device = torch.device("cpu"), network: torch.nn.Module = None):
        import patchcore.backbones
        import patchcore.patchcore

        network = network if network is not None else patchcore.backbones.load(backbone_name, pretrained)
        network.name = backbone_name
        self.name = f"patchcore:{backbone_name}:{'+'.join(layers)}@{image_size}"
        self.device = device
        self.model = patchcore.patchcore.PatchCore(device)
        self.model.load(backbone=network, layers_to_extract_from=list(layers), device=device,
                        input_shape=(3, image_size, image_size),
                        pretrain_embed_dimension=pretrain_embed_dimension,
                        target_embed_dimension=target_embed_dimension, patchsize=patchsize)

    def embed(self, images):
        images = images.to(self.device, torch.float)
        features, patch_shapes = self.model._embed(images, provide_patch_shapes=True)
        features = np.asarray(features, dtype=np.float32)
        grid = tuple(int(x) for x in patch_shapes[0])
        return features.reshape(images.shape[0], grid[0] * grid[1], -1), grid


class TinyRandomBackbone:
    """Seeded random-weight convolutional stub for offline tests and smoke runs.

    It has no pretrained knowledge. Any number produced with it only checks
    that the pipeline executes; it is never a result.
    """

    def __init__(self, dim: int = 16, seed: int = 0):
        generator = torch.Generator().manual_seed(seed)
        self.name = f"tiny-random:{dim}:seed{seed}"
        self.net = torch.nn.Sequential(
            torch.nn.Conv2d(3, dim, 3, stride=2, padding=1), torch.nn.ReLU(),
            torch.nn.Conv2d(dim, dim, 3, stride=2, padding=1), torch.nn.ReLU(),
            torch.nn.Conv2d(dim, dim, 3, stride=2, padding=1),
        )
        with torch.no_grad():
            for parameter in self.net.parameters():
                parameter.copy_(torch.randn(parameter.shape, generator=generator) * 0.3)
        self.net.eval()

    def embed(self, images):
        with torch.no_grad():
            maps = self.net(images.to(torch.float))
        b, d, h, w = maps.shape
        return maps.permute(0, 2, 3, 1).reshape(b, h * w, d).numpy().astype(np.float32), (h, w)


class TinyResNetLike(torch.nn.Module):
    """Random-weight module exposing ``layer2``/``layer3`` like a torchvision
    ResNet, so tests can drive ``PatchCoreBackbone`` without downloads."""

    def __init__(self, seed: int = 0):
        super().__init__()
        torch.manual_seed(seed)
        self.stem = torch.nn.Sequential(torch.nn.Conv2d(3, 8, 3, stride=2, padding=1), torch.nn.ReLU())
        self.layer2 = torch.nn.Sequential(torch.nn.Conv2d(8, 16, 3, stride=2, padding=1), torch.nn.ReLU())
        self.layer3 = torch.nn.Sequential(torch.nn.Conv2d(16, 24, 3, stride=2, padding=1), torch.nn.ReLU())

    def forward(self, x):
        return self.layer3(self.layer2(self.stem(x)))
