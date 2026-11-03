"""Prepare license-safe drawings and independently pretrained DINOv2 export.

AnomalyDINO-style baseline: https://arxiv.org/abs/2405.14529 . Not a new method.
Never reads benchmark images, WCTE weights, or inherited memory banks.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/onboarding/assets'
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    import torch
    import timm
    import onnx
    from safetensors.torch import load_file
    from PIL import ImageEnhance, ImageFilter
    from deploy.public_demo.app import drawing

    OUT.mkdir(parents=True, exist_ok=True)
    samples = OUT / 'samples'
    samples.mkdir(exist_ok=True)
    manifest = {'kind': 'generated sample', 'references': [], 'calibration': [], 'tests': []}
    for group, seeds in [('references', range(8)), ('calibration', range(100, 108))]:
        for seed in seeds:
            name = f'{group}-{seed:03}.png'
            drawing(seed).save(samples / name)
            manifest[group].append({'path': 'samples/' + name, 'label': 'normal', 'seed': seed})
    for seed in range(200, 210):
        for scratch in [False, True]:
            label = 'scratch' if scratch else 'normal'
            name = f'test-{label}-{seed}.png'
            drawing(seed, scratch=scratch).save(samples / name)
            manifest['tests'].append({'path': 'samples/' + name, 'label': label, 'seed': seed})
    for name, image in [('dark', ImageEnhance.Brightness(drawing(210)).enhance(.08)),
                        ('blur', drawing(211).filter(ImageFilter.GaussianBlur(5)))]:
        image.save(samples / f'{name}.png')
    manifest['image_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in samples.glob('*.png')}
    (OUT / 'samples.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Only the independently pretrained checkpoint already fingerprinted in S2.
    intake = json.loads((ROOT / 'artifacts/finish-fewshot/model-intake.json').read_text())
    entry = next(x for x in intake['weights'] if x['path'].endswith('.safetensors'))
    weight = ROOT / entry['path']
    if hashlib.sha256(weight.read_bytes()).hexdigest() != entry['sha256']:
        raise ValueError('Pretrained checkpoint fingerprint changed')
    torch.set_num_threads(4)
    model = timm.create_model('vit_small_patch14_dinov2.lvd142m', pretrained=False,
                              img_size=224, num_classes=0)
    state = load_file(str(weight))
    # timm checkpoint originally uses 518px; resample its positional embedding
    # with the same official timm checkpoint filter used by pretrained=True.
    from timm.models.vision_transformer import checkpoint_filter_fn
    model.load_state_dict(checkpoint_filter_fn(state, model), strict=True)
    model.eval()

    class PatchTokens(torch.nn.Module):
        def __init__(self, network):
            super().__init__(); self.network = network

        def forward(self, images):
            return self.network.forward_features(images)[:, 1:, :]

    wrapper = PatchTokens(model).eval()
    graph = OUT / 'dinov2-vits14.onnx'
    if not graph.exists():
        torch.onnx.export(wrapper, torch.zeros(1, 3, 224, 224), str(graph),
                          input_names=['image'], output_names=['patches'],
                          opset_version=17, do_constant_folding=True, dynamo=False)
    onnx.checker.check_model(str(graph))
    class PatchScore(torch.nn.Module):
        def forward(self, patches, bank):
            patches = torch.nn.functional.normalize(patches, dim=-1, eps=1e-12)
            bank = torch.nn.functional.normalize(bank, dim=-1, eps=1e-12)
            distances = (1 - torch.matmul(patches, bank.T)).clamp(min=0)
            patch_scores = distances.min(dim=-1).values
            return patch_scores, patch_scores.topk(3).values.mean()

    scorer = OUT / 'score.onnx'
    torch.onnx.export(PatchScore(), (torch.ones(256, 384), torch.ones(2048, 384)),
                      str(scorer), input_names=['patches', 'bank'],
                      output_names=['distances', 'score'], dynamic_axes={'bank': {0: 'bank_patches'}},
                      opset_version=17, dynamo=False)
    # Python ground-truth features from identical browser tensors will be
    # produced by verify_onboarding.py after browser execution.
    metadata = dict(model='DINOv2 ViT-S/14', size_bytes=graph.stat().st_size,
                    sha256=hashlib.sha256(graph.read_bytes()).hexdigest(),
                    checkpoint_sha256=entry['sha256'], input=[1, 3, 224, 224],
                    output=[1, 256, 384], opset=17, torch=torch.__version__,
                    timm=timm.__version__, license='Apache-2.0',
                    source='https://github.com/facebookresearch/dinov2',
                    scope='Independently pretrained weights; no WCTE checkpoint/bank')
    (OUT / 'model.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
