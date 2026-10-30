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


def test_exact_pro_matches_independent_small_threshold_sweep():
    from scipy.ndimage import label
    masks = np.zeros((2, 5, 5), dtype=bool)
    masks[0, 0, 0] = True
    masks[0, 3:5, 3:5] = True
    masks[1, 1:3, 1:3] = True
    maps = np.random.default_rng(31).integers(0, 9, size=masks.shape).astype('float32')
    regions = []
    for image, mask in enumerate(masks):
        components, count = label(mask, np.ones((3, 3)))
        regions.extend((image, components == k) for k in range(1, count+1))
    points = [(0.0, 0.0)]
    for threshold in sorted(np.unique(maps), reverse=True):
        pred = maps >= threshold
        fpr = np.mean(pred[~masks])
        pro = np.mean([pred[image][region].mean() for image, region in regions])
        points.append((fpr, pro))
    x, y = np.array(points).T
    cutoff = x < 0.3
    expected = np.trapezoid(np.r_[y[cutoff], np.interp(0.3, x, y)],
                            np.r_[x[cutoff], 0.3]) / 0.3
    assert np.isclose(pixel_metrics(masks, maps)['aupro_fpr_0_3'], expected)


def test_vectorised_radial_profile_matches_nested_reference():
    from upgrade_geometry_breadth import radial_profile
    gray=np.random.default_rng(17).integers(0,256,(65,65)).astype(np.float32)/3
    for cy,cx,radius in [(32.5,32.5,25.5),(5.0,5.0,40.0)]:
        profile=np.zeros(200);count=np.zeros(200)
        for angle in np.linspace(0,2*np.pi,360,endpoint=False):
            ca,sa=np.cos(angle),np.sin(angle)
            for b in range(200):
                r=b/200*radius;yi=int(round(cy+r*sa));xi=int(round(cx+r*ca))
                if 0<=yi<65 and 0<=xi<65:
                    profile[b]+=gray[yi,xi];count[b]+=1
        profile[count>0]/=count[count>0]
        assert np.array_equal(profile,radial_profile(gray,cy,cx,radius))
