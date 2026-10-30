import numpy as np
from upgrade_metrics import image_metrics, pixel_metrics


def test_perfect_pixel_separation():
    masks = np.array([[[0, 1], [0, 0]], [[0, 0], [1, 0]]], dtype=bool)
    result = pixel_metrics(masks, masks.astype('float32'))
    assert result['pixel_auroc'] == 1.0
    assert np.isclose(result['aupro_fpr_0_3'], 1.0)
    assert result['connected_regions'] == 2


def test_reversed_pixel_separation():
    masks = np.array([[[0, 1], [0, 0]]], dtype=bool)
    result = pixel_metrics(masks, (~masks).astype('float32'))
    assert result['pixel_auroc'] == 0.0
    assert result['aupro_fpr_0_3'] == 0.0


def test_ties_do_not_get_order_advantage():
    masks = np.array([[[0, 1], [0, 0]]], dtype=bool)
    result = pixel_metrics(masks, np.ones(masks.shape, dtype='float32'))
    assert result['pixel_auroc'] == 0.5
    assert np.isclose(result['aupro_fpr_0_3'], 0.15)


def test_image_threshold():
    result = image_metrics([0, 1, 1, 0], [0, 2, 0.5, 1.1], 1)
    assert result['missed_defects'] == 1
    assert result['false_alarms'] == 1
