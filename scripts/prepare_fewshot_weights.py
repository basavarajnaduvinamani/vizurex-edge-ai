"""Fetch the protocol's frozen weights and fingerprint local model artifacts."""
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    import torch
    from visurex_fewshot.backbones import DinoV2Backbone,PatchCoreBackbone
    torch.set_num_threads(4)
    output=ROOT/'artifacts/finish-fewshot/model-intake.json'
    if output.exists():raise FileExistsError('Preserve previous model intake')
    info=dict(command=sys.argv,packages={n:importlib.metadata.version(n) for n in
        ['torch','torchvision','timm','numpy','faiss-cpu','scipy','scikit-learn']},
        cuda_available=torch.cuda.is_available(),benchmark_device='cpu (unchanged runner)',models=[])
    if info['cuda_available']:
        device=torch.cuda.get_device_properties(0)
        info['available_gpu']=dict(name=device.name,total_memory_bytes=device.total_memory)
    for cls in [DinoV2Backbone,PatchCoreBackbone]:
        model=cls(image_size=224,pretrained=True)
        info['models'].append(dict(name=model.name,pretrained=True,device=str(model.device)))
        del model;gc.collect()
    files=[]
    for variable in ['HF_HOME','TORCH_HOME']:
        folder=Path(os.environ[variable]).resolve()
        if not folder.is_relative_to(ROOT):raise ValueError('Model cache outside project')
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix in {'.safetensors','.pth'}:
                files.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=digest(path)))
    info['weights']=files
    info['protocol_sha256']=digest(ROOT/'docs/FEWSHOT_PROTOCOL.md')
    output.write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info),flush=True)


if __name__=='__main__':main()
