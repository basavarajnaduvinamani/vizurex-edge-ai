"""Export frozen shipped bundles and measure paired, equal-output CPU calls."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
import numpy as np
from PIL import Image
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.engine import Registry,TRANSFORM,CATEGORIES
from backend.portable_model import PortablePatchCore


def main():
    import onnx
    import onnxruntime as ort
    ort.disable_telemetry_events()
    torch.set_num_threads(4)
    output=ROOT/'artifacts/sprint-2026-11-01/onnx'
    if output.exists():raise FileExistsError('Preserve earlier export attempt')
    output.mkdir(parents=True)
    registry=Registry(bundle_root=ROOT/'artifacts/model-bundles')
    summaries=[]
    for category in CATEGORIES:
        folder=output/category;folder.mkdir()
        detector,threshold,_,identity=registry._load(category)
        candidate=PortablePatchCore(detector).eval()
        destination=folder/'detector.onnx'
        sample=torch.zeros((1,3,224,224))
        with torch.no_grad():
            torch.onnx.export(candidate,(sample,),str(destination),opset_version=17,dynamo=False,
                              input_names=['normalised_rgb'],output_names=['anomaly_score','patch_distances'])
        onnx.checker.check_model(str(destination))
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        session=ort.InferenceSession(str(destination),sess_options=options,providers=['CPUExecutionProvider'])
        paths=sorted((ROOT/'data/raw/mvtec_ad'/category/'test').glob('*/*.png'))
        rows=[]
        for index,path in enumerate(paths):
            with Image.open(path) as image:tensor=TRANSFORM(image.convert('RGB')).unsqueeze(0)
            array=tensor.numpy()
            if index==0:
                for _ in range(2):
                    with torch.no_grad():candidate(tensor)
                    session.run(None,{'normalised_rgb':array})
            values={};times={}
            for method in (['portable_torch','onnx'] if index%2==0 else ['onnx','portable_torch']):
                begin=time.perf_counter()
                if method=='onnx':score,patches=session.run(None,{'normalised_rgb':array})
                else:
                    with torch.no_grad():score,patches=candidate(tensor)
                    score,patches=score.numpy(),patches.numpy()
                times[method]=(time.perf_counter()-begin)*1000
                values[method]=float(score[0])
                if not np.isfinite(patches).all():raise ValueError('Nonfinite raw map')
            begin=time.perf_counter();native,_=detector.predict(tensor)
            times['shipped_torch_smoothed_map']=(time.perf_counter()-begin)*1000
            values['shipped_torch']=float(native[0])
            rows.append(dict(image=str(path.relative_to(ROOT/'data/raw/mvtec_ad'/category/'test')),
                             input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),scores=values,timing_ms=times,
                             score_delta=abs(values['onnx']-values['shipped_torch']),
                             graph_delta=abs(values['onnx']-values['portable_torch']),
                             decision_agrees=bool((values['onnx']>=threshold)==(values['shipped_torch']>=threshold))))
            (folder/'per_image.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        summary=dict(category=category,images=len(rows),source_model_sha256=identity,
                     onnx_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),threshold=threshold,
                     max_score_delta=max(r['score_delta'] for r in rows),
                     max_graph_delta=max(r['graph_delta'] for r in rows),
                     agreeing_decisions=sum(r['decision_agrees'] for r in rows),
                     timing_ms={m:dict(p50=float(np.percentile([r['timing_ms'][m] for r in rows],50)),
                                      p95=float(np.percentile([r['timing_ms'][m] for r in rows],95)))
                                for m in rows[0]['timing_ms']},
                     private_source=str((folder/'per_image.json').relative_to(ROOT)))
        summary['passed']=summary['max_score_delta']<=.001 and summary['max_graph_delta']<=.001 and summary['agreeing_decisions']==len(rows)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        summaries.append(summary)
        print(json.dumps(summary),flush=True)
        if not summary['passed']:raise ValueError('ONNX parity failed; do not deploy or retune threshold')
    result=dict(protocol='docs/ONNX_PROTOCOL_SPRINT.md',device='CPU',threads=4,
                packages={n:importlib.metadata.version(n) for n in ['torch','onnx','onnxruntime','numpy']},models=summaries,
                scope='Warm preprocessed model calls only; portable Torch and ONNX return raw maps; shipped Torch returns smoothed maps. Not device or end-to-end timing.')
    target=ROOT/'docs/sprint/S4_RESULTS';target.mkdir(parents=True,exist_ok=True)
    (target/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    text='# S4: frozen shipped-model ONNX check\n\nPortable wrapper around WCTE\'s inherited PatchCore. '+result['scope']+'\n\nSource: `S4_RESULTS/summary.json`.\n\n'
    text+='| Category | Images | Max score delta | Decisions agreeing | Portable Torch p50 / p95 ms | ONNX p50 / p95 ms | Shipped Torch, smoothed map p50 / p95 ms |\n|---|---:|---:|---:|---|---|---|\n'
    for r in summaries:
        t=r['timing_ms'];text+=f"| {r['category']} | {r['images']} | {r['max_score_delta']} | {r['agreeing_decisions']} | {t['portable_torch']['p50']} / {t['portable_torch']['p95']} | {t['onnx']['p50']} / {t['onnx']['p95']} | {t['shipped_torch_smoothed_map']['p50']} / {t['shipped_torch_smoothed_map']['p95']} |\n"
    text+='\nDINOv2 export and INT8 quantisation were not executed. The serving app was not changed to ONNX; this is an export/parity/timing candidate. Physical-device testing remains pending.\n'
    (ROOT/'docs/sprint/S4_RESULTS.md').write_text(text,encoding='utf-8')


if __name__=='__main__':main()
