# Publication audit — 4 November 2026

Scope: complete reachable history of the own `vizurex-edge-ai` repository,
including local branches, fetched remote branches/tags and the preserved stash.
Preflight head: `dd8dfa02bbe84e73eb03ca0915fa1a62b9254ba8`.
The checkout is not shallow. Upstream `DeepWCTE/VisureX` was read only.

| Check | Observed result | Source |
|---|---|---|
| Reachable commits inventoried | 66 | `artifacts/publication-audit/inventory.json` |
| Refs inventoried | 13 | same |
| Unique file-content versions inspected | 881 | same; `all-blobs/` materialisation |
| Total unique blob bytes | 14,346,842 | same |
| Gitleaks | 8.30.1; official release archive checksum verified | `artifacts/publication-audit/tools/checksums.txt` |
| Full history secret scan | no findings; exit 0 | `artifacts/publication-audit/gitleaks-full.json`, `.log` |
| Independent all-blob secret scan | no findings; exit 0 | `artifacts/publication-audit/gitleaks-blobs.json`, `.log` |
| Tracked .env files / weight or data binaries | none identified | `inventory.json`, `candidate_findings: []` |
| Notebook attachments / saved cell output | none in the one notebook version | same |
| Image file versions | six; manually reviewed below | same |

Gitleaks Git command used explicit default rules, `--all --full-history -m
--root`, ignored inline allow comments, decoded content and traversed archives
up to depth three, with a 1024 MB target limit (largest observed blob: 2,664,818
bytes). It reported 65 diff-bearing commits; the independent tree enumeration
covered all 66 reachable commits. No suppression/baseline was supplied. The
separate directory scan examined every materialised blob, including snapshots
whose extension/path would otherwise affect file-name exclusions.

The inventory includes benchmark score exports and filename manifests; those
are results/provenance, not redistributed benchmark photographs. No MVTec AD
image, WCTE industrial capture, personal photograph or model bank was identified.
Raw/model/build artifacts remain ignored and outside Git.

## Image review

| Path | Classification | Introducing commit |
|---|---|---|
| `docs/images/demo-anomaly-desktop.png` | Synthetic, explicitly simulated UI fixture | `d9b35953a9dd95db6d84294eee1581385eaeaba0` |
| `docs/images/demo-anomaly-mobile.png` | Same synthetic fixture at mobile width | same |
| `docs/images/demo-retake-desktop.png` | Simulated RETAKE UI, no object photograph | same |
| `docs/results/FEWSHOT_2026-10-30/masked/fewshot_auroc.png` | Numeric result plot | See path/commit map in `inventory.json` |
| `docs/results/FEWSHOT_2026-10-30/primary/fewshot_auroc.png` | Numeric result plot | same |
| `docs/results/FEWSHOT_2026-10-30/sanity/fewshot_auroc.png` | Numeric smoke/result plot | same |

All six unique image versions were inspected, not only their filenames. No
other binary content was found by the inventory's binary-content check.

## Licence and publication gate

The existing root `LICENSE` is identical to upstream's `LICENSE`: Apache-2.0,
SHA-256 `88046bf22d5b4f4b8cc85079ae6aae5424a3a1999db952ed152828ff325b2c6d`.
`NOTICE` retains Amazon attribution. No replacement licence was introduced.
DINOv2 and ONNX Runtime redistribution notices are retained separately.

Owner explicitly authorized making the repository public only after a clean
audit. Before changing visibility, rerun the full Git and blob scans on the
candidate containing the new header/status/README/audit records. Stop on any
finding. No history rewrite, force push or main merge is authorized here.
The new front-door README and page are changes on draft PR #4; the owner still
controls merging them onto the default branch.

Site deployment is separate: the protected-preview attempt remains blocked by
Vercel's first-deployment Production rule. Publishing source does not authorize
a Production bootstrap or public site deployment.
