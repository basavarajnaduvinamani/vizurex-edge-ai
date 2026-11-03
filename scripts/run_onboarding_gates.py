"""Run the full software gate once on the final candidate; retain exact logs."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ('artifacts/platform/final/software' if '--platform' in sys.argv else 'artifacts/onboarding/final-gates')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    python = str(ROOT / '.venv-fewshot/Scripts/python.exe')
    # Avoid shared global pytest temp folders owned by another sandbox/session.
    # Unique workspace path is new: pytest never clears any existing user data.
    temp = OUT / f'pytest-temp-{time.time_ns()}'
    commands = {
        'python': [python, '-m', 'pytest',
                   'backend/test_api.py', 'backend/test_network.py', 'backend/test_quality.py',
                   'backend/test_bundles.py', 'backend/test_model_restore.py', 'backend/test_portable.py',
                   'scripts/test_capture_manifest.py', 'scripts/test_dataset_validator.py',
                   'scripts/test_fewshot.py', 'scripts/test_upgrade_metrics.py', 'scripts/test_sprint.py',
                   'scripts/test_onboarding.py', '-q', f'--junitxml={OUT / "python.xml"}',
                   f'--basetemp={temp}'],
        'frontend': ['node', 'scripts/test_frontend.mjs'],
        'onboarding': ['node', '--test', 'deploy/onboarding/test/core.test.mjs',
                       'deploy/onboarding/test/build.test.mjs',
                       'deploy/onboarding/test/platform-domain.test.mjs'],
        'dependency': [python, '-m', 'pip', 'check'],
    }
    results = {}
    for name, command in commands.items():
        start = time.perf_counter()
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (OUT / f'{name}.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        results[name] = dict(command=command, exit_code=process.returncode, seconds=time.perf_counter()-start)
        (OUT / 'execution.json').write_text(json.dumps(results, indent=2))
        print(f'{name}: exit {process.returncode}\n{process.stdout[-1500:]}', flush=True)
        if process.returncode:
            raise SystemExit(process.returncode)
    print('All final software gates passed.', flush=True)


if __name__ == '__main__':
    main()
