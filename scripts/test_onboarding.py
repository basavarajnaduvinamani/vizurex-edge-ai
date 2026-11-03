"""Validate the recorded REAL browser run, never substitute a stub for parity."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_measured_browser_parity_record():
    d = json.loads((ROOT / 'docs/step1/browser_parity.json').read_text())
    assert d['passed']
    assert d['n'] == len(d['rows']) == d['agreeing'] == 20
    assert d['max_score_delta'] == max(r['delta'] for r in d['rows'])
    assert d['max_score_delta'] <= .001
    assert all(r['same'] for r in d['rows'])
    assert len({r['source'] for r in d['rows']}) == d['n']


def test_runtime_scope_and_privacy_are_recorded():
    d = json.loads((ROOT / 'docs/step1/browser_parity.json').read_text())
    assert d['provider'] == 'wasm' and d['threads'] == 1
    assert d['external_requests'] == [] and d['page_errors'] == []
    assert 'Not decoder parity' in d['preprocessing_scope']
    assert d['timing']['p95']['ms'] >= d['timing']['p50']['ms'] > 0
    assert d['model']['size_bytes'] > 0


def test_source_numbers_are_not_generated_demo_accuracy():
    summary = json.loads((ROOT / 'docs/sprint/S2_RESULTS/summary.json').read_text())
    rows = [r for r in summary['macro'] if r['group'] == 'all' and r['k'] == '8']
    assert len(rows) == 2
    assert all(len(r['categories']) == 15 and r['replicates'] == 10000 for r in rows)
    assert not json.loads((ROOT / 'docs/step1/browser_parity.json').read_text())['timing_scope'].startswith('Factory')
