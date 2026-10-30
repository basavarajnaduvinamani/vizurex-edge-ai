"""Offline tests for the few-shot harness: random-weight stubs and synthetic
images only. No downloads, datasets, GPU or pretrained weights are needed."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import torch  # noqa: E402
from visurex_fewshot import backbones, data, detector, metrics, report  # noqa: E402


def make_category(root: Path, category='bottle', train=10, good=3, defect=3, size=64):
    """MVTec-shaped fixture: smooth textured normals, defects with a bright square."""
    rng = np.random.default_rng(123)
    base = np.linspace(60, 160, size)[None, :, None] + np.zeros((size, size, 3))

    def save(relative, array):
        target = root / category / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.clip(array, 0, 255).astype(np.uint8)).save(target)

    for i in range(train):
        save(f'train/good/{i:03d}.png', base + rng.normal(0, 6, base.shape))
    for i in range(good):
        save(f'test/good/{i:03d}.png', base + rng.normal(0, 6, base.shape))
    for i in range(defect):
        image = base + rng.normal(0, 6, base.shape)
        mask = np.zeros((size, size), dtype=np.uint8)
        y, x = 16 + 8 * i, 20
        image[y:y + 14, x:x + 14] = 255
        mask[y:y + 14, x:x + 14] = 255
        save(f'test/scratch/{i:03d}.png', image)
        save(f'ground_truth/scratch/{i:03d}_mask.png', np.stack([mask] * 3, axis=-1)[..., 0])
    return root


class ShotSelectionAndSplits(unittest.TestCase):
    def test_select_shots_is_seeded_and_bounded(self):
        a, b = data.select_shots(20, 4, seed=0), data.select_shots(20, 4, seed=0)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(len(set(a.tolist())), 4)
        self.assertTrue(((a >= 0) & (a < 20)).all())
        self.assertFalse(np.array_equal(a, data.select_shots(20, 4, seed=1)))
        np.testing.assert_array_equal(data.select_shots(5, 'full', seed=9), np.arange(5))
        with self.assertRaises(ValueError):
            data.select_shots(3, 4, seed=0)
        with self.assertRaises(ValueError):
            data.select_shots(3, 0, seed=0)

    def test_reference_pool_and_validation_follow_repository_split(self):
        with tempfile.TemporaryDirectory() as temp:
            root = make_category(Path(temp))
            splits = data.load_splits(str(root), 'bottle', resize=64, imagesize=56)
            train = [Path(r[2]).name for r in splits['train'].data_to_iterate]
            val = [Path(r[2]).name for r in splits['val'].data_to_iterate]
            self.assertEqual(train, [f'{i:03d}.png' for i in range(8)])
            self.assertEqual(val, ['008.png', '009.png'])
            self.assertEqual(len(splits['test']), 6)
            self.assertEqual(data.find_categories(str(root)), ['bottle'])


class DetectorTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.grid = (4, 4)
        self.reference = rng.normal(size=(3, 16, 8)).astype(np.float32)

    def test_reference_patches_score_zero_and_outlier_dominates_max(self):
        for metric in ('cosine', 'l2'):
            model = detector.KShotPatchNN(detector.DetectorConfig(metric=metric, aggregation='max'))
            model.fit(self.reference, self.grid)
            self.assertEqual(model.memory_size, 48)
            self.assertLess(model.patch_scores(self.reference[:1]).max(), 1e-4)
            query = self.reference[:1].copy()
            query[0, 5] = -query[0, 5] * 10
            patch = model.patch_scores(query)
            self.assertEqual(int(patch[0].argmax()), 5)
            self.assertAlmostEqual(model.image_scores(patch)[0], float(patch.max()), places=5)

    def test_mean_top_aggregation(self):
        model = detector.KShotPatchNN(detector.DetectorConfig(aggregation='mean_top', top_fraction=0.25))
        patch = np.array([[0., 1., 2., 3., 4., 5., 6., 7.]], dtype=np.float32)
        self.assertAlmostEqual(model.image_scores(patch)[0], 6.5)

    def test_coreset_reduces_memory_and_maps_have_image_size(self):
        config = detector.DetectorConfig(metric='l2', aggregation='max', coreset_fraction=0.25)
        model = detector.KShotPatchNN(config, seed=0).fit(self.reference, self.grid)
        self.assertEqual(model.memory_size, 12)
        scores, maps = model.predict(self.reference[:2], image_size=(32, 32))
        self.assertEqual(scores.shape, (2,))
        self.assertEqual(maps.shape, (2, 32, 32))
        self.assertTrue(np.isfinite(maps).all())

    def test_masking_keeps_centre_foreground(self):
        h, w = 8, 8
        features = np.zeros((2, h * w, 4), dtype=np.float32)
        centre = np.zeros((h, w), dtype=bool)
        centre[2:6, 2:6] = True
        features[:, centre.ravel(), 0] = 5.0
        features += np.random.default_rng(1).normal(0, 0.01, features.shape).astype(np.float32)
        mask = detector.ForegroundMask(features, (h, w))(features)
        np.testing.assert_array_equal(mask[0], centre.ravel())

    def test_invalid_config_and_unfitted_use(self):
        with self.assertRaises(ValueError):
            detector.DetectorConfig(metric='manhattan')
        with self.assertRaises(RuntimeError):
            detector.KShotPatchNN(detector.DetectorConfig()).patch_scores(self.reference)


class MetricTests(unittest.TestCase):
    def test_threshold_and_counts(self):
        self.assertAlmostEqual(metrics.validation_threshold(np.arange(101)), 99.0)
        result = metrics.image_metrics([0.1, 0.2, 0.9, 0.95], [0, 0, 1, 1], threshold=0.5)
        self.assertEqual((result['tp'], result['fp'], result['tn'], result['fn']), (2, 0, 2, 0))
        self.assertEqual(result['image_auroc'], 1.0)
        self.assertEqual(result['false_alarm_rate'], 0.0)
        self.assertIsNone(metrics.image_metrics([0.1, 0.2], [0, 0], 0.5)['image_auroc'])
        with self.assertRaises(ValueError):
            metrics.validation_threshold([])

    def test_aupro_bounds(self):
        gt = np.zeros((2, 16, 16), dtype=bool)
        gt[0, 2:6, 2:6] = True
        gt[1, 10:14, 8:12] = True
        rng = np.random.default_rng(0)
        perfect = gt.astype(float) + rng.uniform(0, 0.1, gt.shape)
        self.assertAlmostEqual(metrics.compute_aupro(gt, perfect), 1.0, places=3)
        self.assertLess(metrics.compute_aupro(gt, 1.0 - perfect), 0.05)
        self.assertGreater(metrics.pixel_auroc(gt, perfect), 0.99)
        self.assertIsNone(metrics.compute_aupro(np.zeros_like(gt), perfect))


class BackboneAdapterTests(unittest.TestCase):
    def test_tiny_random_backbone_is_deterministic(self):
        images = torch.randn(2, 3, 32, 32)
        a, grid = backbones.TinyRandomBackbone(seed=3).embed(images)
        b, _ = backbones.TinyRandomBackbone(seed=3).embed(images)
        self.assertEqual(grid, (4, 4))
        self.assertEqual(a.shape, (2, 16, 16))
        np.testing.assert_array_equal(a, b)

    def test_patchcore_adapter_uses_repository_embedding(self):
        backbone = backbones.PatchCoreBackbone(
            'tiny', image_size=32, pretrain_embed_dimension=32, target_embed_dimension=16,
            network=backbones.TinyResNetLike())
        features, grid = backbone.embed(torch.randn(2, 3, 32, 32))
        self.assertEqual(grid, (8, 8))  # layer2 stride 4 at 32 px
        self.assertEqual(features.shape, (2, 64, 16))
        self.assertEqual(features.dtype, np.float32)

    def test_dinov2_adapter_strips_prefix_tokens_without_download(self):
        backbone = backbones.DinoV2Backbone('vit_small_patch14_dinov2', image_size=56, pretrained=False)
        features, grid = backbone.embed(torch.randn(1, 3, 56, 56))
        self.assertEqual(grid, (4, 4))
        self.assertEqual(features.shape, (1, 16, 384))


class ReportTests(unittest.TestCase):
    def test_summary_and_table_come_only_from_records(self):
        runs = [{'category': 'bottle', 'method': 'm', 'k': '1', 'seed': s, 'image_auroc': v,
                 'defect_recall': 1.0, 'false_alarm_rate': 0.0, 'pixel_aupro': None,
                 'nn_ms_per_image_median': 2.0} for s, v in ((0, 0.5), (1, 0.7))]
        summary = report.summarize(runs)
        self.assertAlmostEqual(summary[0]['image_auroc_mean'], 0.6)
        table = report.markdown_table(summary, [], 'results.json')
        self.assertIn('0.6000 ± 0.1000', table)
        self.assertIn('n/a', table)


class ExperimentScriptTests(unittest.TestCase):
    def run_script(self, data_root, output, *extra):
        return subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'run_fewshot.py'), '--data-root', str(data_root),
             '--output', str(output), '--methods', 'tiny_random', '--shots', '1', '2', 'full',
             '--seeds', '0', '1', '--resize', '64', '--imagesize', '56', '--threads', '1', *extra],
            capture_output=True, text=True)

    def test_end_to_end_outputs_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = make_category(Path(temp) / 'data')
            output = Path(temp) / 'out'
            completed = self.run_script(root, output)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads((output / 'results.json').read_text())
            self.assertTrue(payload['dataset_checks'][0]['passed'])
            # k=1 and k=2 for two seeds each, k=full once.
            self.assertEqual(len(payload['runs']), 5)
            run = payload['runs'][0]
            self.assertEqual(run['validation_count'], 2)
            self.assertEqual(run['test_count'], 6)
            import csv,hashlib
            predictions=output/run['predictions_path']
            self.assertEqual(hashlib.sha256(predictions.read_bytes()).hexdigest(),run['predictions_sha256'])
            rows=list(csv.DictReader(predictions.open()))
            self.assertEqual(len(rows),run['test_count'])
            self.assertEqual(sum(int(r['label'])==1 and int(r['predicted'])==0 for r in rows),run['fn'])
            self.assertEqual(sum(int(r['label'])==0 and int(r['predicted'])==1 for r in rows),run['fp'])
            self.assertTrue((output/run['calibration_path']).is_file())
            self.assertIsNotNone(run['pixel_aupro'])
            pool = {f'{i:03d}.png' for i in range(8)}
            for record in payload['runs']:
                self.assertTrue(set(record['references']) <= pool)
            self.assertEqual(len(payload['runs'][-1]['references']), 8)
            self.assertIn('tiny_random', (output / 'results.md').read_text())
            self.assertTrue((output / 'fewshot_auroc.png').stat().st_size > 0)
            self.assertTrue((output / 'environment.json').is_file())
            again = self.run_script(root, output)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn('Refusing to overwrite', again.stderr)

    def test_failed_dataset_check_is_recorded_and_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = make_category(Path(temp) / 'data')
            (root / 'bottle/test/good/000.png').write_bytes((root / 'bottle/train/good/000.png').read_bytes())
            output = Path(temp) / 'out'
            completed = self.run_script(root, output)
            self.assertEqual(completed.returncode, 1)
            payload = json.loads((output / 'results.json').read_text())
            self.assertFalse(payload['dataset_checks'][0]['passed'])
            self.assertEqual(payload['runs'], [])


if __name__ == '__main__':
    unittest.main()
