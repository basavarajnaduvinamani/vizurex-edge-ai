"""Regression tests for dataset validation; no benchmark images needed."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.category = self.root / 'fixture'
        for relative, colour in [('train/good/000.png', 10), ('test/good/000.png', 20),
                                 ('test/defect/000.png', 30), ('ground_truth/defect/000_mask.png', 255)]:
            target = self.category / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (8, 8), (colour, colour, colour)).save(target)

    def tearDown(self):
        self.temp.cleanup()

    def run_validator(self):
        return subprocess.run([sys.executable, str(Path(__file__).with_name('validate_mvtec_category.py')),
                               str(self.root), '--category', 'fixture'], capture_output=True, text=True)

    def test_valid(self):
        self.assertEqual(self.run_validator().returncode, 0)

    def test_duplicate(self):
        (self.category / 'test/good/000.png').write_bytes((self.category / 'train/good/000.png').read_bytes())
        self.assertNotEqual(self.run_validator().returncode, 0)

    def test_wrong_mask_name_even_with_matching_count(self):
        (self.category / 'ground_truth/defect/000_mask.png').rename(self.category / 'ground_truth/defect/999_mask.png')
        self.assertNotEqual(self.run_validator().returncode, 0)

    def test_empty_training(self):
        (self.category / 'train/good/000.png').unlink()
        self.assertNotEqual(self.run_validator().returncode, 0)


if __name__ == '__main__':
    unittest.main()
