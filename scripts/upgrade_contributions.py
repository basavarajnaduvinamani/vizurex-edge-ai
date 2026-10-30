"""File-level provenance ledger; absence upstream is not proof of sole authorship."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=ROOT.parent/'upstream/VisureX'
BASE='498780c6142605d04c1458c04079dc5f7102211f'


def git(*args,cwd=ROOT):
    return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()


def main():
    rows=[]
    for name in git('ls-files').splitlines():
        path=ROOT/name
        if path.suffix not in {'.py','.sh','.ps1','.js','.mjs','.html','.css','.kt','.kts'}:continue
        if not path.is_file():continue
        original=UPSTREAM/name
        equal=(original.is_file() and path.read_text(encoding='utf-8-sig').replace('\r\n','\n')==
               original.read_text(encoding='utf-8-sig').replace('\r\n','\n'))
        rows.append(dict(path=name,current_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            inherited_sha256=hashlib.sha256(original.read_bytes()).hexdigest() if original.is_file() else None,
            classification='inherited unchanged text' if equal else ('inherited file extended' if original.is_file()
                else 'not present in supplied inherited snapshot; human/AI authorship not established by file absence')))
    result=dict(command=[sys.executable,*sys.argv],execution_commit=git('rev-parse','HEAD'),
        branch=git('branch','--show-current'),base_commit=BASE,
        inherited_snapshot=git('rev-parse','HEAD',cwd=UPSTREAM),
        inherited_status=git('status','--short',cwd=UPSTREAM),inherited_remotes=git('remote','-v',cwd=UPSTREAM),
        upgrade_changed_paths=git('diff','--name-status',BASE,'HEAD').splitlines(),files=rows,
        policy='PatchCore is an established inherited method. Ledger separates supplied source, project extensions and this-session upgrades. It does not establish a novel algorithm, sole human authorship, hardware validation or deployment.')
    target=ROOT/'results/2026-10-30/step8-contributions.json'
    if target.exists():raise FileExistsError('Preserve existing ledger')
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(files=len(rows),source=str(target))),flush=True)


if __name__=='__main__':main()
