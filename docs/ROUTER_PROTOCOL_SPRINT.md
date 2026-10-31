# S3: fixed normal-only router

Register and commit before running `scripts/sprint_router.py`. This is an
exploratory analysis on the completed S2 benchmark: S2's aggregate test outcomes
have already been inspected. Normal-only inputs to a rule do not make this an
unseen confirmatory evaluation. No new detector, thresholds or features are fit.
This extends WCTE's inherited PatchCore system; it does not invent either backbone.

## One rule, fixed in advance

For each category, reference budget and seed, load ONLY each model's normal
validation score vector from its calibration sidecar. Calculate
`(p99(scores) - median(scores)) / (abs(median(scores)) + 1e-12)`.
Choose the lower relative upper-tail dispersion; exact ties choose PatchCore.
This proxy measures stability on normals, not defect sensitivity. Do not tune it
or replace it after looking at the comparison. The detector's existing p99
operating threshold is unchanged.

## Leave-one-category-out evaluation

Each category is an evaluation fold. The held-out category may provide its normal
calibration images, as it would at onboarding. Test labels and scores from every
category are excluded from selection. There are no learned cross-category
parameters, so the other-category training partition is deliberately unused.
This is LOCO evaluation of a fixed rule, not a trained meta-router or evidence of
unseen-category generalisation.

Write all choices and calibration hashes BEFORE opening the test-metric CSV.
Then evaluate on the frozen S2 per-seed AUROCs. Compare always-DINOv2,
always-PatchCore, the router, and an oracle that selects the higher test AUROC
per category/budget/seed. The oracle is a labelled upper bound, never deployable.

Primary comparison: k=8 macro category AUROC. All other budgets are descriptive.
Use the same category bootstrap as v2 (10,000 paired resamples, seed 20261101,
percentile 95% intervals). The registered comparison criterion is a positive
lower paired-interval endpoint against BOTH fixed backbones at k=8. Report all
results if it loses, and do not change the rule. The prior practical-use failure
is not overturned by a better macro score.
