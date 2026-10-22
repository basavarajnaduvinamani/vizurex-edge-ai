"""Conservative capture checks, not model confidence or an OOD detector.

Thresholds are fixed engineering heuristics, not fitted to benchmark test labels.
Factory capture data is required before enabling this policy operationally.
"""
import cv2
import numpy as np
from PIL import Image

POLICY_VERSION = 'capture-heuristic-v1'


def assess_capture(image):
    width, height = image.size
    resized = image.convert('RGB').resize((256 if width <= height else int(256 * width / height),
                                          256 if height <= width else int(256 * height / width)),
                                         Image.Resampling.BILINEAR)
    left, top = round((resized.width - 224) / 2), round((resized.height - 224) / 2)
    crop = resized.crop((left, top, left + 224, top + 224))
    gray = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2GRAY)
    metrics = {'laplacian_variance': float(cv2.Laplacian(gray, cv2.CV_64F).var()),
               'dark_fraction': float((gray < 12).mean()),
               'bright_fraction': float((gray > 248).mean()),
               'width': image.width, 'height': image.height}
    reasons = []
    if min(image.size) < 224:
        reasons.append('Image is too small; move closer or use a higher-resolution capture.')
    if metrics['dark_fraction'] > 0.70:
        reasons.append('Most of the inspection region is too dark.')
    if metrics['bright_fraction'] > 0.70:
        reasons.append('Most of the inspection region is saturated or overexposed.')
    if metrics['laplacian_variance'] < 12:
        reasons.append('Insufficient visible detail; check focus, motion and framing.')
    return {'passed': not reasons, 'reasons': reasons, 'metrics': metrics,
            'policy_version': POLICY_VERSION,
            'limitation': 'Heuristic capture checks; passing does not establish correct product, pose or defect visibility.'}
