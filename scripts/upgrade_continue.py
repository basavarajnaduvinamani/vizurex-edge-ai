"""Wait for this intake/first breadth batch, then run remaining work sequentially."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/2026-10-30'


def main():
    manifest=json.loads((OUT/'step2-intake/source.json').read_text())
    while True:
        complete=OUT/'step2-breadth-a/completed.json'
        failures=OUT/'step2-breadth-a/failures.json'
        try:
            finished=len(json.loads(complete.read_text()))+len(json.loads(failures.read_text()))
        except (FileNotFoundError,json.JSONDecodeError):finished=0
        intake=OUT/'step2-intake/failures.json'
        if finished==12 and intake.exists():
            problems=json.loads(intake.read_text())
            if problems:raise RuntimeError('Intake failures require review before more runs')
            for entry in manifest['files']:
                path=ROOT/'data/raw/mvtec_ad'/entry['path']
                if not path.exists() or path.stat().st_size!=entry['size']:
                    raise ValueError('Incomplete pinned category: '+entry['path'])
            break
        print(json.dumps(dict(waiting_for='first breadth batch and verified intake',finished_first_batch=finished)),flush=True)
        time.sleep(30)
    command=[sys.executable,str(ROOT/'scripts/upgrade_execute.py'),'--stage','step2-breadth-b',
             '--categories','leather','metal_nut','pill','screw','tile','toothbrush','wood','zipper',
             '--seeds','0','1','2','--engines','current']
    (OUT/'step2-breadth-b-launch.json').write_text(json.dumps(command,indent=2),encoding='utf-8')
    # Failed category workers remain evidence; later successful categories still run.
    result=subprocess.run(command,cwd=ROOT)
    (OUT/'step2-breadth-b-returncode.json').write_text(json.dumps(dict(returncode=result.returncode)),encoding='utf-8')
    stages=['step1','step2-existing','step2-breadth-a','step2-breadth-b']
    subprocess.run([sys.executable,str(ROOT/'scripts/upgrade_pipeline_tail.py'),'--stages',*stages],cwd=ROOT,check=True)


if __name__=='__main__':main()
