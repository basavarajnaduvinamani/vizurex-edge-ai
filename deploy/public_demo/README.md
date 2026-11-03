---
title: VisureX Synthetic Sample Demo
sdk: docker
app_port: 7860
license: apache-2.0
---

# VisureX public-safe companion

This is a sample-only companion to the WCTE IIT Madras inspection project. The
main project extends WCTE's inherited PatchCore pipeline. This companion reuses
the repository's WRN patch-feature and nearest-neighbour code with a NEW bank
made only from generated washer drawings. It does not serve the shipped
industrial model and makes no industrial-accuracy or factory-impact claim.

All sample pixels are generated at runtime by `app.py`. No MVTec images, real
captures, WCTE datasets, trained industrial bundles, personal data or credentials
are included. Reference and normal-validation drawings use separate fixed seeds;
the example buttons use another seed. The threshold is the p99 of generated
normal-validation scores, not adjusted to make a button pass.

The app downloads official torchvision ImageNet weights on first start. Those
third-party weights retain their own terms; they are not uploaded in this
package. Inherited code retains the root Apache licence and attribution notice.
Generated sample drawings are offered under CC0. Do not interpret these
artificial samples as a realistic industrial dataset.

Only the two built-in sample IDs are accepted. Uploads and request bodies are
rejected. One inference runs at a time, with a bounded process-wide request
limit; no operational inspection history or visitor IP log is persisted by the
app. There is no account system. This is not a general public upload service.

## Hosting gate

**Prepared, not deployed. Owner approval saying `deploy` is required.**
Official documentation checked on 31 October 2026 says Docker compute Spaces
require a paid plan to create; do not assume free CPU deployment is available.
No paid plan, billing or public repository has been enabled by this sprint.
Source: https://huggingface.co/docs/hub/spaces-overview
Docker configuration: https://huggingface.co/docs/hub/spaces-sdks-docker

Run `python scripts/prepare_public_demo.py` from the development folder to create
the reviewed standalone package under `artifacts/sprint-2026-11-01/public-space-package`.
Upload ONLY that package after explicit approval and checking the selected
account's plan. Never upload the development folder, artifacts, datasets or
model bundles. Docker builds have not been claimed unless recorded separately.

Local review: from the development folder, use the prepared benchmark environment
and project Torch cache, then run `python -m uvicorn deploy.public_demo.app:app
--host 127.0.0.1 --port 7861 --no-access-log`. A first start constructs the
synthetic bank; the main inspection server on port 8000 is unaffected.
