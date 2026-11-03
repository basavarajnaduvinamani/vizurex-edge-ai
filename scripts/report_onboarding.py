"""Write source-backed Step 1 report, only after real gates and preview checks."""
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/onboarding'
DOC = ROOT / 'docs/step1'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parity = json.loads((DOC / 'browser_parity.json').read_text())
    light = json.loads((DOC / 'lighthouse.json').read_text())
    execution = json.loads((ART / 'final-gates/execution.json').read_text())
    assert set(execution) == {'python', 'frontend', 'onboarding', 'dependency'}
    assert all(row['exit_code'] == 0 for row in execution.values())
    assert parity['passed']
    xml = ET.parse(ART / 'final-gates/python.xml').getroot()
    tests = sum(int(s.attrib['tests']) for s in xml.iter('testsuite'))
    frontend = int(re.search(r'(\d+) frontend regression checks passed',
                            (ART / 'final-gates/frontend.log').read_text()).group(1))
    node_log = (ART / 'final-gates/onboarding.log').read_text()
    node = int(re.search(r'# pass (\d+)', node_log).group(1))
    # The build-output/image hash checks require ignored local model assets;
    # CI runs the five pure core tests, not those two artifact checks.
    configured_ci = tests + frontend + node - 2
    suite = {'date': '2026-11-04', 'python_passed': tests, 'frontend_checks_passed': frontend,
             'new_node_tests_passed': node, 'configured_ci_checks': configured_ci,
             'local_software_total': tests + frontend + node,
             'browser_acceptance_checks': parity['checks'], 'dependency_check': 'passed',
             'warning': 'One existing Starlette/httpx deprecation warning',
             'ci_scope': 'Configured checks; hosted run status is recorded separately.'}
    (DOC / 'tests.json').write_text(json.dumps(suite, indent=2))
    preview = json.loads((DOC / 'preview.json').read_text())
    assert preview['environment'] == 'preview' and preview['public'] is False
    blocked = preview.get('status', '').startswith('BLOCKED')
    assert preview.get('protected_verified') or (blocked and not preview.get('deployed'))
    s2 = json.loads((ROOT / 'docs/sprint/S2_RESULTS/summary.json').read_text())
    rows = {r['method']: r for r in s2['macro'] if r['group'] == 'all' and r['k'] == '8'}
    dino, pc = rows['dinov2_vits14'], rows['patchcore_wrn50']
    fmt = lambda row: f"{row['mean']:.4f} [{row['ci95'][0]:.4f}, {row['ci95'][1]:.4f}]"
    timing = parity['timing']
    t = lambda k: f"{timing[k]['ms']:.1f} ms [95% CI {timing[k]['ci95'][0]:.1f}, {timing[k]['ci95'][1]:.1f}]"
    ci = json.loads((DOC / 'github.json').read_text()) if (DOC / 'github.json').exists() else {'status': 'UNKNOWN'}
    lines = {
        'SDE': f"Built and locally verified an in-browser few-shot inspection demo (DINOv2 ONNX in WebAssembly): {timing['p50']['ms']:.1f} ms median per warm generated-image check on laptop CPU; browser/Python decision parity {parity['agreeing']}/{parity['n']}; {configured_ci} checks configured in CI. Hosting is blocked.",
        'APM': "Turned a 15-category benchmark into an eight-reference onboarding flow with separate normal calibration and a RETAKE capture check for a proposed line-inspector workflow; user validation pending.",
        'PRE': f"Benchmarked DINOv2 k-NN (AnomalyDINO-style) versus PatchCore across 15 MVTec AD categories: {fmt(dino)} versus {fmt(pc)} macro AUROC at k=8 (category-bootstrap 95% CIs); pre-registered router rejected."
    }
    report = f'''# MILESTONE_REPORT_STEP1

Date: 4 November 2026. Step 1 only; no robustness study started.

## 1. Outcome and scope

Built a separate, browser-only eight-reference onboarding demo with generated
S5 washer samples and local-photo uploads. Nothing was merged to main.
Protected preview URL: {preview['url'] or 'NONE — BLOCKED; no deployment created'}
Draft PR: https://github.com/basavarajnaduvinamani/vizurex-edge-ai/pull/4
Source commit: `{preview['source_commit']}`. Requested environment: preview, authentication required.
G4 status: {preview['status']}. The new project has zero deployments.
Public release and production remain gated on explicit owner “deploy”.
Source: `docs/step1/preview.json`.

## 2. Preflight and attribution

Base: draft PR #3, head `d1c2937d5f5a79a7b0e4fcd7aaf0c7f299c3f5e0`.
New branch: `claude/demo-onboarding-2026-11`. Original stash preserved.
S5 contained FastAPI sample-only app, page, requirements, Dockerfile, README,
licenses/notices and reused patch-feature source. It used a separate generated
WRN patch-NN bank: normal score 0.05514240264892578 (GOOD), scratch score
1.0108609199523926 (ANOMALY), normal-only threshold 0.06378932237625122;
functional checks passed, not an accuracy estimate or prior deployment.
Source: `docs/sprint/S5_RESULTS/status.json`.

AnomalyDINO (Damm et al., WACV 2025), confirmed from the paper:
https://arxiv.org/html/2405.14529v3 ; official code linked there:
https://github.com/dammsi/AnomalyDINO . Our ViT-S/14 cosine patch-neighbour,
top-1%-mean baseline uses 224px crops, no masking/rotations by default,
and a disjoint normal-only p99 threshold. It differs from the paper's
448/672px preprocessing, masking and rotation settings. Benchmarked/adapted
and studied; not a new detection method or exact paper-result reproduction.
PatchCore: https://arxiv.org/abs/2106.08265 .

## 3. Working product

- Teach: eight normal thumbnails; separate normal calibration (eight generated
  calibration drawings; visitor minimum two, explicitly unvalidated).
- Check: generated or local image, real GOOD/ANOMALY, frozen threshold, score,
  fixed-scale patch heatmap and measured request latency.
- RETAKE: capture check runs before scoring; no fabricated score on rejection.
  Known benchmark blur failures remain visible. Not a reliable OOD/quality gate.
- Same-device WASM CPU, one thread. No inference server, analytics or transmitted
  photo upload. Test-time images never update the bank/threshold.
- Real photos and 2–3 owned sample parts remain pending; capture plan:
  `CAPTURE_SAMPLES.md`. Generated samples cannot establish real-part accuracy.

Sources: `deploy/onboarding/`, `docs/step1/browser_parity.json`.

## 4. Export, parity and latency

| Measurement | Final measured value | Source |
|---|---|---|
| DINOv2 exported model | {parity['model']['size_bytes']:,} bytes | `docs/step1/browser_parity.json` |
| Graph SHA-256 | `{parity['model']['sha256']}` | same |
| Browser vs Python decisions | {parity['agreeing']}/{parity['n']} (agreement CI {parity['agreement_ci95']}) | same |
| Max absolute score difference | {parity['max_score_delta']:.12g} | same |
| Threshold difference | {parity['threshold_delta']:.12g} | same |
| Browser warm p50 | {t('p50')} | same |
| Browser warm p95 | {t('p95')} | same |
| Runtime | Chrome {parity['browser']}; WASM, one CPU thread | same |

Timing n={parity['n']} sequential warm generated-image checks; includes decode,
preprocessing, capture check, encoder and scoring. Excludes model download and
bank onboarding. Percentile CIs bootstrap requests within this session, not
different devices. Final run is used even though earlier runs were faster.
Python receives the identical browser-decoded/cropped pixels. This is scoring
parity, not decoder parity; maximum browser-versus-PIL pixel difference was
{parity['browser_vs_pil_max_pixel_delta']}. Agreement interval is descriptive;
synthetic paired samples are not independent factory trials. No factory accuracy claim.

## 5. Existing benchmark evidence shown on the page

| k=8 macro AUROC | Mean and category-bootstrap 95% CI | Source |
|---|---|---|
| DINOv2 | {fmt(dino)} | `docs/sprint/S2_RESULTS/summary.json` |
| PatchCore | {fmt(pc)} | same |

Page also shows all measured k=1,2,4,8,16 rows and intervals, texture/object
splits, the negative router result, and the earlier separate PatchCore ONNX
parity/timing. No MVTec images are distributed. Benchmark thresholds need
additional normal calibration beyond k. Not eight photos total.
Sources: `docs/sprint/S2_RESULTS.md`, `S3_RESULTS.md`, `S4_RESULTS.md`.

## 6. Gates and verification

| Gate | Result | Evidence |
|---|---|---|
| Python | {tests} passed | `artifacts/onboarding/final-gates/python.xml` |
| Existing frontend | {frontend} checks passed | `artifacts/onboarding/final-gates/frontend.log` |
| New JS/core/build tests | {node} passed | `artifacts/onboarding/final-gates/onboarding.log` |
| Dependency consistency | passed | `artifacts/onboarding/final-gates/dependency.log` |
| Browser acceptance | {parity['checks']} checks, desktop + 390px, light + dark | `artifacts/onboarding/verification/browser.json` |
| Mobile Lighthouse performance / accessibility / best practices / SEO | {' / '.join(str(light['scores'][k]) for k in ['performance','accessibility','best-practices','seo'])} | `docs/step1/lighthouse.json` |
| Protected preview (G4) | BLOCKED: first deployment requires Production; none created | `docs/step1/preview.json` |

Lighthouse {light['version']} measures initial lazy-loading page, not inference.
Screenshots: `artifacts/onboarding/verification/screenshots/` (16 full-page PNGs).
Build guard checks forbidden data paths, image filename allowlist and generated
image hashes. Hosted GitHub status: {ci.get('status','UNKNOWN')}; configured
CI checks are distinguished from a confirmed hosted run. Two local build-output
tests use ignored assets and do not run in the lightweight hosted workflow.

## 7. Limitations and deviations

- No owned-part photos, physical glasses test, factory pilot or deployment impact.
- Only generated functional examples; no tuning/reliability study was started.
- Shared-pixel parity does not prove identical decoding across browsers/devices.
- Browser heatmap is unsmoothed patch distance, not benchmark segmentation.
- The initial suite hit global pytest-temp permissions (61 passed, 1 setup
  error). The final run used a fresh workspace temp directory; tests unchanged.
- Browser harness fixes retained the restrictive CSP and distinguished local
  blob thumbnails from external traffic; no privacy checks were disabled.
- Cloud creation was initially auto-review blocked; owner then explicitly
  authorized a protected preview. No billing changes or production promotion.
- Vercel CLI refused the first Preview deployment because this new project
  requires its first deployment to be Production. No --prod or API workaround
  was used. Only an empty protected project exists; no public/preview URL.
  Official source: https://vercel.com/docs/domains/working-with-domains/deploying-and-redirecting
- Referenced `_COMMON_RULES.txt`/R9 and design brief were unavailable. This report
  states actual evidence in explicit sections rather than claiming that template was read.

## 8. Resume lines supported by generated evidence

**SDE:** {lines['SDE']}

**APM:** {lines['APM']}

**PRE:** {lines['PRE']}

Sources: `docs/step1/tests.json`, `browser_parity.json`, `preview.json`,
`docs/sprint/S2_RESULTS/summary.json`, `docs/sprint/S3_RESULTS.md`.
“Shipped”, “public demo”, real-part reliability, user adoption and factory impact are not supported.

## 9. Stop

Strongest result: a measured browser-only flow with matching generated-sample decisions.
Weakest gap: no owned-part/real capture qualification.
One next upgrade: collect the pre-split owned-part capture pack, only after the next instruction.
STOP. No robustness study, main merge, production release or public-access change.
'''
    (ROOT / 'MILESTONE_REPORT_STEP1.md').write_text(report, encoding='utf-8')
    facts = f'''# RESUME_FACTS_VisureX

Updated 2026-11-04. Step 1 facts; generated examples are not a factory benchmark.

| Fact | Number / status | Source file |
|---|---|---|
| DINOv2 k=8 macro AUROC, 15 categories, 3 seeds | {fmt(dino)} | docs/sprint/S2_RESULTS/summary.json |
| PatchCore k=8 macro AUROC, same benchmark | {fmt(pc)} | docs/sprint/S2_RESULTS/summary.json |
| Browser decision parity | {parity['agreeing']}/{parity['n']}; CI {parity['agreement_ci95']} | docs/step1/browser_parity.json |
| Max score delta | {parity['max_score_delta']} | docs/step1/browser_parity.json |
| Warm browser p50 / p95 | {t('p50')} / {t('p95')} | docs/step1/browser_parity.json |
| DINOv2 graph bytes | {parity['model']['size_bytes']} | docs/step1/browser_parity.json |
| Local software checks | {tests}+{frontend}+{node}={tests+frontend+node} passed | docs/step1/tests.json |
| Browser acceptance | {parity['checks']} checks | docs/step1/browser_parity.json |
| Configured hosted CI | {configured_ci} checks; actual status separately recorded | docs/step1/tests.json; docs/step1/github.json |
| Lighthouse mobile | {light['scores']} | docs/step1/lighthouse.json |
| Hosting | protected preview BLOCKED; zero deployments | docs/step1/preview.json |

APM: {lines['APM']}

Pre-doc: {lines['PRE']}

SDE: {lines['SDE']}

## Do not say
- New anomaly-detection method, invented PatchCore/AnomalyDINO, or exact paper reproduction.
- Eight photos total, validated upload threshold, factory-ready, 100% accuracy.
- Shipped/public reviewer link, measured glasses/mobile latency, or on-device Android parity.
- Used by 50+ MSMEs, completed pilot, time savings, publication or adoption.
- Held-out real captures or robustness improvement from generated samples.

## Interview questions
1. Why extra normal images? The bank's own examples self-match; disjoint normal
   calibration avoids that trivial threshold. Small calibration sets remain unvalidated.
2. What does parity establish? Same decisions and tiny score differences on
   browser-decoded generated pixels; not camera/decoder/factory generalisation.
3. What did not work? The registered router criterion failed, and the inherited
   heuristic previously let synthetic blur through. Neither negative result is hidden.
'''
    (ROOT / 'RESUME_FACTS_VisureX.md').write_text(facts, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
