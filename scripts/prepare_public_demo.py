"""Build an allowlisted, private-data-free review package; never deploy."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    target=ROOT/'artifacts/sprint-2026-11-01/public-space-package'
    if target.exists():raise FileExistsError('Preserve previous package')
    target.mkdir(parents=True)
    sources=[ROOT/'deploy/public_demo'/x for x in ['app.py','index.html','requirements.txt','Dockerfile','README.md']]
    sources += [ROOT/'LICENSE',ROOT/'NOTICE']
    sources += [p for name in ['patchcore','visurex_fewshot'] for p in (ROOT/'src'/name).rglob('*.py')]
    manifest=[]
    for source in sources:
        relative=source.relative_to(ROOT/'src') if source.is_relative_to(ROOT/'src') else Path(source.name)
        if source.is_relative_to(ROOT/'src'):relative=Path('src')/relative
        destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
        manifest.append(dict(path=relative.as_posix(),sha256=hashlib.sha256(destination.read_bytes()).hexdigest()))
    (target/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(dict(package=str(target.relative_to(ROOT)),files=len(manifest),deployed=False)))


if __name__=='__main__':main()
