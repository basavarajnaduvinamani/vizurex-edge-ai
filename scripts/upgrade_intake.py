"""Read local evidence before interpreting new runs; hash without changing it."""
from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    files=[ROOT/'artifacts/phase1-20261021/runs/summary.json',
           ROOT/'artifacts/smoke/mvtec-bottle-smoke/results.csv',
           ROOT/'artifacts/phase2/api_real_model_tests.json',
           ROOT/'artifacts/phase3/capture-stress/summary.json',
           ROOT/'artifacts/model-bundles/catalog.json',
           ROOT/'artifacts/portable-candidate/v2/bottle/verification.json',
           ROOT/'artifacts/software-checks/python.xml',ROOT.parent/'06_upgrade_walmart.md']
    result=dict(command=[sys.executable,*sys.argv],fetched_at=datetime.now().astimezone().isoformat(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        files=[],python=sys.version,packages={name:importlib.metadata.version(name) for name in
            ['torch','torchvision','numpy','scipy','scikit-learn','faiss-cpu','Pillow','psutil','httpx','uvicorn']})
    for p in files:
        content=p.read_bytes()
        result['files'].append(dict(path=str(p),bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),modified=datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(),
            note='Read locally; source body not redistributed. Historical inputs are not new session results.'))
    output=ROOT/'results/2026-10-30/local_intake.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(files=[x['path'] for x in result['files']],fetched_at=result['fetched_at'])),flush=True)


if __name__=='__main__':main()
