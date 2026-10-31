"""Bounded sequential run launcher; raw logs and partial results survive failure."""
import argparse
import json
import subprocess
import sys
import time
import psutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stage',required=True)
    p.add_argument('--categories',nargs='+',required=True)
    p.add_argument('--seeds',nargs='+',type=int,default=[0])
    p.add_argument('--engines',nargs='+',choices=['official','current'],default=['official','current'])
    p.add_argument('--geometry',action='store_true')
    p.add_argument('--max-worker-rss-bytes',type=int,default=2_000_000_000,
                   help='Safety cap, not a measured memory claim; blocked runs remain recorded')
    args=p.parse_args()
    root=ROOT/'results/2026-10-30'/args.stage
    root.mkdir(parents=True,exist_ok=True)
    summaries=[]
    failures=[]
    for category in args.categories:
        for seed in args.seeds:
            for engine in args.engines:
                key=f'{category}_seed{seed}_{engine}'
                output=root/key
                if output.exists():
                    raise FileExistsError(f'New run requires unused output directory: {output}')
                output.mkdir()
                cmd=[sys.executable,str(ROOT/'scripts/upgrade_benchmark.py'),
                    '--category',category,'--seed',str(seed),'--engine',engine,'--stage',args.stage]
                if args.geometry and engine=='current':cmd.append('--geometry')
                (output/'command.json').write_text(json.dumps(cmd,indent=2),encoding='utf-8')
                print('START '+key,flush=True)
                peak=0;blocked=None
                with (output/'worker.log').open('w',encoding='utf-8') as log:
                    process=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    while process.poll() is None:
                        run_meta=output/'run.json'
                        if run_meta.exists():
                            try:
                                pid=json.loads(run_meta.read_text())['worker_pid']
                                worker=psutil.Process(pid);rss=worker.memory_info().rss;peak=max(peak,rss)
                                if rss>args.max_worker_rss_bytes:
                                    blocked='Worker exceeded configured RSS safety cap; use larger-memory compute without changing the benchmark protocol.'
                                    worker.terminate()
                            except (psutil.Error,KeyError,json.JSONDecodeError):pass
                        time.sleep(0.25)
                    returncode=process.returncode
                (output/'resource_monitor.json').write_text(json.dumps(dict(
                    observed_worker_rss_peak_bytes=peak,configured_rss_cap_bytes=args.max_worker_rss_bytes,
                    sampling_seconds=0.25,blocked=blocked),indent=2),encoding='utf-8')
                if returncode:
                    failures.append(dict(run=key,returncode=returncode,blocked=blocked,log=str(output/'worker.log')))
                    print('FAILED '+key,flush=True)
                else:
                    summary=json.loads((output/'summary.json').read_text())
                    summaries.append(summary)
                    print('DONE '+key+' '+json.dumps(summary['metrics']),flush=True)
                (root/'completed.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
                (root/'failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    print(json.dumps(dict(completed=len(summaries),failures=failures)),flush=True)
    if failures:sys.exit(1)


if __name__=='__main__':main()
