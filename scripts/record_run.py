"""Record an actual local command without changing its experiment settings."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def hardware():
    info={}
    for key,command in {
        'cpu':['powershell','-NoProfile','-Command','(Get-CimInstance Win32_Processor).Name'],
        'gpu':['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],
    }.items():
        try:
            r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
            info[key]=dict(command=command,exit_status=r.returncode,stdout=r.stdout.strip(),stderr=r.stderr.strip())
        except (OSError,subprocess.TimeoutExpired) as exc:info[key]=dict(error=str(exc))
    return info


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--record-dir',type=Path,required=True)
    p.add_argument('command',nargs=argparse.REMAINDER)
    args=p.parse_args();command=args.command
    if command and command[0]=='--':command=command[1:]
    if not command:raise ValueError('A command is required')
    output=args.record_dir.resolve()
    if not output.is_relative_to(ROOT):raise ValueError('Record directory must stay in project')
    output.mkdir(parents=True,exist_ok=True)
    target=output/'execution.json'
    if target.exists():raise FileExistsError('Preserve earlier execution: '+str(target))
    for cmd in [['git','status','--short'],['git','stash','list']]:
        subprocess.run(cmd,cwd=ROOT,stdout=subprocess.DEVNULL,check=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    data=dict(command=command,cwd=str(ROOT),execution_commit=commit,hardware=hardware(),
              start_utc=datetime.now(timezone.utc).isoformat(),exit_status=None)
    target.write_text(json.dumps(data,indent=2),encoding='utf-8')
    environment=os.environ.copy()
    temp=ROOT/'artifacts/pytest-finish';temp.mkdir(parents=True,exist_ok=True)
    environment['PYTEST_DEBUG_TEMPROOT']=str(temp)
    begin=time.perf_counter()
    with (output/'console.log').open('w',encoding='utf-8') as stream:
        completed=subprocess.run(command,cwd=ROOT,env=environment,stdout=stream,stderr=subprocess.STDOUT)
    data.update(end_utc=datetime.now(timezone.utc).isoformat(),exit_status=completed.returncode,
                wall_seconds=time.perf_counter()-begin,console=str((output/'console.log').relative_to(ROOT)))
    target.write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps(data),flush=True)
    raise SystemExit(completed.returncode)


if __name__=='__main__':main()
