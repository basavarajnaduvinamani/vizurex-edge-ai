# Parallel read-only Phase 1 audit

Work only in C:/Users/Viraj/OneDrive/Desktop/vizurex-edge-ai.
Another agent is actively restoring dependencies and reproducing the baseline.
Do not edit source, install packages, run training, use Git writes, or touch
upstream files. Do not download datasets or execute inherited pickle files.

Read upstream/VisureX and development to independently audit:
1. Which active source changes distinguish development from the inherited code?
2. Are training, validation, threshold calibration and test scoring separated?
3. Does any test-score normalization affect image decisions or segmentation?
4. Are the geometric judge and defect bank active on MVTec?
5. Does saved-model inference reproduce training-time preprocessing and normalization?
6. Identify missing dependencies, hard-coded paths, or misleading claims.

Return a concise table: severity, file and exact line, evidence, consequence,
recommended fix. Distinguish active Python from commented historical code.
Do not call a result fabricated or invalid without demonstrated evidence.
Do not assume zero exact overlap proves independence of physical objects.
Return your findings in chat; do not change any local file.
