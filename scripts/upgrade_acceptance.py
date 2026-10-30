"""Known-image contract checks using recorded historical expectations, not fixtures."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/'results/2026-10-30/step7'
    output.mkdir(parents=True,exist_ok=True)
    # Expected outcomes are acceptance requirements, not hardcoded measured scores.
    cases=[('bottle','good/000.png','GOOD'),('bottle','broken_large/000.png','ANOMALY')]
    rows=[]
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=120) as client:
        health=client.get('/api/health');health.raise_for_status()
        for category,relative,expected in cases:
            image=ROOT/'data/raw/mvtec_ad'/category/'test'/relative
            tick=time.perf_counter()
            response=client.post('/api/inspect',data={'category':category,'quality_mode':'benchmark'},
                                 files={'image':(image.name,image.read_bytes(),'image/png')})
            response.raise_for_status();body=response.json()
            row=dict(category=category,image=relative,image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                expected=expected,actual=body['decision'],passed=body['decision']==expected,
                score=body['anomaly_score'],threshold=body['threshold'],
                actual_png_overlay=body['images']['overlay'].startswith('data:image/png;base64,'),
                inspection_id=body['inspection_id'],http_roundtrip_seconds=time.perf_counter()-tick)
            rows.append(row)
    log=ROOT/'artifacts/inspections/inspections.jsonl'
    entries=[json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    ids={row['inspection_id'] for row in entries}
    for row in rows:row['metadata_log_present']=row['inspection_id'] in ids
    result=dict(command=[sys.executable,*sys.argv],seed=0,
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        server='http://127.0.0.1:8000',checks=rows,
        log_location=str(log.relative_to(ROOT)),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    (output/'acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
    if not all(r['passed'] and r['actual_png_overlay'] and r['metadata_log_present'] for r in rows):
        raise AssertionError('Known-image acceptance check failed')


if __name__=='__main__':main()
