"""Bounded sequential run launcher; raw logs and partial results survive failure."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stage',required=True)
    p.add_argument('--categories',nargs='+',required=True)
    p.add_argument('--seeds',nargs='+',type=int,default=[0])
    p.add_argument('--engines',nargs='+',choices=['official','current'],default=['official','current'])
    p.add_argument('--geometry',action='store_true')
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
                with (output/'worker.log').open('w',encoding='utf-8') as log:
                    result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                if result.returncode:
                    failures.append(dict(run=key,returncode=result.returncode,log=str(output/'worker.log')))
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
