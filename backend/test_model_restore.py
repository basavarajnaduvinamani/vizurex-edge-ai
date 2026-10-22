"""Regression for the saved nearest-neighbour parameter spelling."""
import pickle
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch
import torch
from backend.engine import PatchCore
from scripts.package_models import state_fingerprint


class RestoreTests(TestCase):
    def test_shared_backbone_fingerprint_detects_changes(self):
        model = torch.nn.Linear(2, 2)
        previous = state_fingerprint(model)
        self.assertEqual(previous, state_fingerprint(model))
        with torch.no_grad():
            model.weight.add_(1)
        self.assertNotEqual(previous, state_fingerprint(model))

    def test_nondefault_neighbours_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'patchcore_params.pkl'
            path.write_bytes(pickle.dumps({'backbone.name': 'wideresnet50',
                                          'anomaly_scorer_num_nn': 3}))
            detector = PatchCore(torch.device('cpu'))
            detector.load = Mock()
            detector.anomaly_scorer = Mock()
            with patch('patchcore.backbones.load', return_value=torch.nn.Identity()):
                detector.load_from_path(folder, torch.device('cpu'), Mock())
            self.assertEqual(detector.load.call_args.kwargs['anomaly_score_num_nn'], 3)
            self.assertNotIn('anomaly_scorer_num_nn', detector.load.call_args.kwargs)
