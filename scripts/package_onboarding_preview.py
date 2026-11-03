"""Package the already tested static artifact for a protected preview only."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'artifacts/onboarding'


def main():
    dist = FOLDER / 'dist'
    platform = '--platform' in sys.argv
    target = ROOT / 'artifacts/platform/release' if platform else FOLDER / 'preview'
    output = target / '.vercel/output'
    static = output / 'static'
    static.mkdir(parents=True, exist_ok=True)
    project = json.loads((FOLDER / 'vercel-project-response.json').read_text(encoding='utf-8-sig'))
    if project.get('name') != 'visurex-onboarding':
        raise ValueError('Wrong preview project')
    if project.get('ssoProtection', {}).get('deploymentType') not in {'all', 'all_except_custom_domains'}:
        raise ValueError('Authentication protection required before packaging')
    manifest = []
    external = []
    for source in sorted(dist.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(dist)
        if platform and relative.parts[:2] == ('face', 'wasm'):
            external.append({'path':relative.as_posix(),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                             'source':'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.2/wasm/'+source.name})
            continue
        destination = static / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError('Preview differs from tested artifact')
        manifest.append({'path': relative.as_posix(), 'sha256': digest, 'bytes': source.stat().st_size})
    headers = {h['key']: h['value'] for h in json.loads((dist / 'vercel.json').read_text())['headers'][0]['headers']}
    routes=[{'src':'/(.*)','headers':headers,'continue':True}]
    if platform:
        routes.append({'src':'/face/wasm/(.*)','dest':'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.2/wasm/$1'})
    routes.append({'handle':'filesystem'})
    (output / 'config.json').write_text(json.dumps({'version':3,'routes':routes},indent=2))
    (target / '.vercel/project.json').write_text(json.dumps({'projectId': project['id'], 'orgId': project['accountId']}))
    manifest_path=ROOT/'artifacts/platform/release-manifest.json' if platform else FOLDER/'build-manifest.json'
    manifest_path.write_text(json.dumps({'files':manifest,'pinned_external_runtime':external},indent=2) if platform else json.dumps(manifest,indent=2))
    print(json.dumps({'files': len(manifest), 'bytes': sum(r['bytes'] for r in manifest),
                      'hashes_verified': True, 'deployed': False, 'environment': 'production candidate' if platform else 'preview',
                      'pinned_external_runtime_files':len(external)}))


if __name__ == '__main__':
    main()
