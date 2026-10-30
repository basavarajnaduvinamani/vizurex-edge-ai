"""Local HTTP resource profile in the actual serving worker, never the launcher."""
import time
BOOT=time.perf_counter()
import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['VISUREX_BUNDLE_ROOT']=str(ROOT/'artifacts/model-bundles')
os.environ.pop('VISUREX_LAN_IP',None);os.environ.pop('VISUREX_ACCESS_KEY',None)
import httpx
import numpy as np
from PIL import Image
import psutil
import uvicorn
from backend.app import app
from backend.engine import TRANSFORM


def main():
    out=ROOT/'results/2026-10-30/step6'
    out.mkdir(parents=True,exist_ok=True)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8001,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    client=httpx.Client(base_url='http://127.0.0.1:8001',timeout=120)
    while not server.started:
        if not thread.is_alive():raise RuntimeError('Profile server failed')
        time.sleep(0.05)
    ready=time.perf_counter()-BOOT
    result=dict(command=[sys.executable,*sys.argv],seed=0,
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        pid=os.getpid(),startup_seconds=ready,
        startup_scope='worker script first instruction through imports and HTTP server readiness; excludes OS process creation',
        host='127.0.0.1',port=8001,torch_threads=__import__('torch').get_num_threads(),
        torch_interop_threads=__import__('torch').get_num_interop_threads(),records=[],
        started_at=__import__('datetime').datetime.now().astimezone().isoformat(),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__),ROOT/'backend/app.py',ROOT/'backend/engine.py']},
        deployed_bundle_manifests={category:json.loads((ROOT/'artifacts/model-bundles/models'/category/'manifest.json').read_text())
            for category in ['bottle','grid','transistor']})
    try:
        for category in ['bottle','grid','transistor']:
            base=ROOT/'data/raw/mvtec_ad'/category/'test'
            normals=sorted((base/'good').glob('*.png'))[:15]
            anomalies=sorted(p for p in base.glob('*/*.png') if p.parent.name!='good')[:15]
            for repeat,path in enumerate(normals+anomalies):
                content=path.read_bytes()
                tick=time.perf_counter()
                with Image.open(io.BytesIO(content)) as im:
                    image=im.convert('RGB');TRANSFORM(image).unsqueeze(0)
                preprocessing=time.perf_counter()-tick
                tick=time.perf_counter()
                response=client.post('/api/inspect',data={'category':category,'quality_mode':'benchmark'},
                    files={'image':(path.name,content,'image/png')})
                response.raise_for_status();payload=response.json()
                elapsed=time.perf_counter()-tick
                result['records'].append(dict(category=category,image=str(path.relative_to(base)),
                    input_sha256=hashlib.sha256(content).hexdigest(),model_version=payload['model_version'],
                    anomaly_score=payload.get('anomaly_score'),threshold=payload.get('threshold'),
                    cold_start=payload['cold_start'],decision=payload['decision'],
                    preprocessing_seconds_separate_probe=preprocessing,http_roundtrip_seconds=elapsed,
                    server_processing_ms=payload['timing']['server_processing_ms'],
                    model_inference_ms=payload['timing']['model_inference_ms'],
                    worker_rss_bytes=psutil.Process().memory_info().rss,
                    worker_peak_working_set_bytes=getattr(psutil.Process().memory_info(),'peak_wset',None)))
            (out/'raw.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        summaries={}
        for category in ['bottle','grid','transistor']:
            rows=[r for r in result['records'] if r['category']==category]
            warm=[r for r in rows if not r['cold_start']]
            summaries[category]=dict(cold=rows[0],warm_requests=len(warm),
                **{k:dict(p50=float(np.percentile([r[k] for r in warm],50)),
                          p95=float(np.percentile([r[k] for r in warm],95)))
                    for k in ['preprocessing_seconds_separate_probe','http_roundtrip_seconds',
                              'server_processing_ms','model_inference_ms']})
        result['summary']=summaries
        result['worker_peak_working_set_bytes']=getattr(psutil.Process().memory_info(),'peak_wset',None)
        result['limitations']='Serving and load-generator threads share this measured worker; peak includes both and loaded category models. Warm component preprocessing probe is separate from HTTP request, not a decomposed sum. Laptop loopback only; no phone/glasses latency claim.'
        (out/'raw.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (out/'summary.json').write_text(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2),encoding='utf-8')
        print(json.dumps(result['summary']),flush=True)
    finally:
        client.close();server.should_exit=True;thread.join(timeout=10)


if __name__=='__main__':main()
