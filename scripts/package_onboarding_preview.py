"""Package the already tested static artifact for a protected preview only."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'artifacts/onboarding'


def main():
    dist = FOLDER / 'dist'
    target = FOLDER / 'preview'
    output = target / '.vercel/output'
    static = output / 'static'
    static.mkdir(parents=True, exist_ok=True)
    project = json.loads((FOLDER / 'vercel-project-response.json').read_text(encoding='utf-8-sig'))
    if project.get('name') != 'visurex-onboarding':
        raise ValueError('Wrong preview project')
    if project.get('ssoProtection', {}).get('deploymentType') not in {'all', 'all_except_custom_domains'}:
        raise ValueError('Authentication protection required before packaging')
    manifest = []
    for source in sorted(dist.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(dist)
        destination = static / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError('Preview differs from tested artifact')
        manifest.append({'path': relative.as_posix(), 'sha256': digest, 'bytes': source.stat().st_size})
    headers = {h['key']: h['value'] for h in json.loads((dist / 'vercel.json').read_text())['headers'][0]['headers']}
    (output / 'config.json').write_text(json.dumps({'version': 3, 'routes': [
        {'src': '/(.*)', 'headers': headers, 'continue': True}, {'handle': 'filesystem'}]}, indent=2))
    (target / '.vercel/project.json').write_text(json.dumps({'projectId': project['id'], 'orgId': project['accountId']}))
    (FOLDER / 'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps({'files': len(manifest), 'bytes': sum(r['bytes'] for r in manifest),
                      'hashes_verified': True, 'deployed': False, 'environment': 'preview'}))


if __name__ == '__main__':
    main()
