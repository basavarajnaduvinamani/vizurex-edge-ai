"""Export compact verified results, excluding invalid launcher memory samples."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
evidence = root / 'artifacts/phase1-20261021'
runs = evidence / 'runs'
rows = json.loads((runs / 'summary.json').read_text())
if [r['category'] for r in rows] != ['bottle', 'grid', 'transistor']:
    raise ValueError('All three category verifications must finish before export')
for row in rows:
    # First run monitored Windows venv launchers, not the true training worker.
    row['training_process_peak_rss_bytes'] = None
    row['memory_measurement_note'] = 'Initial launcher-only RSS invalid; training peak not established.'
    row['artifact_size_note'] = 'FAISS and parameter files only; excludes cached pretrained backbone weights.'
inventory = json.loads((evidence / 'inventory.json').read_text())
result = {
    'date': '2026-10-21', 'scope': 'three-category feasibility, one backbone, one seed',
    'results': rows,
    'dataset_checks': {name: {k: v for k, v in entry.items() if k != 'manifest'}
                       for name, entry in inventory['datasets'].items()},
    'source_comparison': inventory['source_comparison'],
    'mirror': json.loads((evidence / 'download_source.json').read_text())['repo'],
    'mirror_revision': json.loads((evidence / 'download_source.json').read_text())['revision'],
    'single_image_memory_observation': {'category': 'bottle', 'process_rss_bytes': 706723840,
        'process_peak_working_set_bytes': 711766016, 'scope': 'one standalone CPU inference, not training peak'},
}
target = root / 'docs/results/PHASE1_RESULTS_2026-10-21.json'
target.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(target)
