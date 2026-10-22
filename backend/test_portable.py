from unittest import TestCase
import torch
from torch.nn import functional as F
from backend.portable_model import ExactAdaptiveMean


class PortableMeanTests(TestCase):
    def test_exact_adaptive_mean_mapping(self):
        generator = torch.Generator().manual_seed(0)
        for input_size, output_size in ((4608, 1024), (9216, 1024), (2048, 384), (11, 3)):
            value = torch.randn((8, input_size), generator=generator)
            expected = F.adaptive_avg_pool1d(value[:, None, :], output_size).squeeze(1)
            actual = ExactAdaptiveMean(input_size, output_size)(value)
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)
