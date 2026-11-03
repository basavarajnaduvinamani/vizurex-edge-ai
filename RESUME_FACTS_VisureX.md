# RESUME_FACTS_VisureX

Updated 2026-11-04. Step 1 facts; generated examples are not a factory benchmark.

| Fact | Number / status | Source file |
|---|---|---|
| DINOv2 k=8 macro AUROC, 15 categories, 3 seeds | 0.9560 [0.9267, 0.9814] | docs/sprint/S2_RESULTS/summary.json |
| PatchCore k=8 macro AUROC, same benchmark | 0.9242 [0.8684, 0.9682] | docs/sprint/S2_RESULTS/summary.json |
| Browser decision parity | 20/20; CI [0.8315665290169146, 1] | docs/step1/browser_parity.json |
| Max score delta | 5.304813385009766e-06 | docs/step1/browser_parity.json |
| Warm browser p50 / p95 | 361.4 ms [95% CI 350.5, 444.9] / 602.8 ms [95% CI 460.9, 634.4] | docs/step1/browser_parity.json |
| DINOv2 graph bytes | 86619987 | docs/step1/browser_parity.json |
| Local software checks | 62+31+7=100 passed | docs/step1/tests.json |
| Browser acceptance | 25 checks | docs/step1/browser_parity.json |
| Configured hosted CI | 98 checks; actual status separately recorded | docs/step1/tests.json; docs/step1/github.json |
| Lighthouse mobile | {'performance': 100, 'accessibility': 100, 'best-practices': 100, 'seo': 100} | docs/step1/lighthouse.json |
| Hosting | protected preview BLOCKED; zero deployments | docs/step1/preview.json |

APM: Turned a 15-category benchmark into an eight-reference onboarding flow with separate normal calibration and a RETAKE capture check for a proposed line-inspector workflow; user validation pending.

Pre-doc: Benchmarked DINOv2 k-NN (AnomalyDINO-style) versus PatchCore across 15 MVTec AD categories: 0.9560 [0.9267, 0.9814] versus 0.9242 [0.8684, 0.9682] macro AUROC at k=8 (category-bootstrap 95% CIs); pre-registered router rejected.

SDE: Built and locally verified an in-browser few-shot inspection demo (DINOv2 ONNX in WebAssembly): 361.4 ms median per warm generated-image check on laptop CPU; browser/Python decision parity 20/20; 98 checks configured in CI. Hosting is blocked.

## Do not say
- New anomaly-detection method, invented PatchCore/AnomalyDINO, or exact paper reproduction.
- Eight photos total, validated upload threshold, factory-ready, 100% accuracy.
- Shipped/public reviewer link, measured glasses/mobile latency, or on-device Android parity.
- Used by 50+ MSMEs, completed pilot, time savings, publication or adoption.
- Held-out real captures or robustness improvement from generated samples.

## Publication add-on, 4 November 2026

Pre-publication audit: 66 reachable commits, 881 unique blobs, six inspected
images (synthetic screenshots/plots); no secret or restricted-image findings.
Sources: `docs/PUBLICATION_AUDIT_2026-11-04.md` and its linked raw scan records.
Existing Apache-2.0 licence matches upstream byte-for-byte. This is a repository
publication check, not new model performance, novelty or factory validation.
Header, affiliation, GitHub links and evidence-backed Done/Next lists are UI
copy changes. Site hosting remains blocked. Repository visibility is verified
separately after publication; a clean scan alone is not a publication receipt.

## Interview questions
1. Why extra normal images? The bank's own examples self-match; disjoint normal
   calibration avoids that trivial threshold. Small calibration sets remain unvalidated.
2. What does parity establish? Same decisions and tiny score differences on
   browser-decoded generated pixels; not camera/decoder/factory generalisation.
3. What did not work? The registered router criterion failed, and the inherited
   heuristic previously let synthetic blur through. Neither negative result is hidden.
