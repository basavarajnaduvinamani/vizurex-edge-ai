"""Real pretrained synthetic-bank functional check, not an accuracy study."""
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from deploy.public_demo.app import app


def main():
    output=ROOT/'artifacts/sprint-2026-11-01/public-smoke.json'
    if output.exists():raise FileExistsError('Preserve previous smoke result')
    with TestClient(app) as client:
        results={name:client.post('/inspect/'+name).json() for name in ['normal','scratch']}
        assert all(np.isfinite(r['score']) and np.isfinite(r['threshold']) for r in results.values())
        checks=dict(health=client.get('/health').status_code==200,
                    png=client.get('/sample/normal').content.startswith(b'\x89PNG'),
                    unknown_sample_rejected=client.post('/inspect/unknown').status_code==422,
                    bodies_rejected=client.post('/inspect/normal',content=b'x').status_code==413,
                    no_upload_route=client.post('/inspect',content=b'x').status_code in [404,413])
    payload=dict(results=results,checks=checks,passed=all(checks.values()),
                 scope='Actual pretrained encoder with generated references. Functional test only, not industrial accuracy or public hosting.')
    output.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps(payload))
    if not payload['passed']:raise SystemExit(1)


if __name__=='__main__':main()
