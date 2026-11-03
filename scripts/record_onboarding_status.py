"""Record the observed hosting block and current GitHub snapshot, no deployment."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/onboarding'
DOC = ROOT / 'docs/step1'


def main():
    deployments = json.loads((ART / 'deployment-list.json').read_text(encoding='utf-8-sig'))
    assert deployments['deployments'] == []
    project = json.loads((ART / 'vercel-project-verified.json').read_text(encoding='utf-8-sig'))
    assert project['ssoProtection']['deploymentType'] == 'all_except_custom_domains'
    github = json.loads((ART / 'github.json').read_text(encoding='utf-8-sig'))
    checks = github['statusCheckRollup']
    github_status = ('FAILED' if any(c['conclusion'] in {'FAILURE', 'CANCELLED', 'TIMED_OUT'} for c in checks)
                     else 'SUCCESS' if checks and all(c['conclusion'] == 'SUCCESS' for c in checks)
                     else 'PENDING')
    (DOC / 'github.json').write_text(json.dumps({
        'status': github_status,
        'source': 'gh pr view 4 --json headRefOid,isDraft,state,url,statusCheckRollup',
        'snapshot': github}, indent=2))
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    status = dict(date='2026-11-04', status='BLOCKED_FIRST_DEPLOYMENT_REQUIRES_PRODUCTION',
                  environment='preview', url=None, deployed=False, public=False,
                  protected_verified=False, project_protection_verified=True,
                  project='visurex-onboarding', deployments_count=0, source_commit=sha,
                  owner_authorization='Protected preview only; no production/public release',
                  cli_observation="Can't create a Preview deployment. This project has no deployments yet, and a project's first deployment is assigned to Production.",
                  attempted_command='vercel deploy --prebuilt --environment preview --yes --json --meta sourceCommit=<source_commit> --cwd artifacts/onboarding/preview',
                  exit_code=1, official_source='https://vercel.com/docs/domains/working-with-domains/deploying-and-redirecting',
                  response_sources=['artifacts/onboarding/deployment-list.json', 'artifacts/onboarding/vercel-project-verified.json'],
                  action='Stopped; no --prod, production bootstrap or REST workaround attempted')
    (DOC / 'preview.json').write_text(json.dumps(status, indent=2))
    print(json.dumps(status))


if __name__ == '__main__':
    main()
