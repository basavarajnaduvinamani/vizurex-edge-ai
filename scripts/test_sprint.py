"""Offline regression checks for full-shot repeats and verified recovery."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_fewshot import make_category
from sprint_analysis import category_bootstrap, summarize

ROOT = Path(__file__).resolve().parents[1]


class SprintRecoveryTests(unittest.TestCase):
    def test_category_bootstrap_and_incomplete_coverage(self):
        self.assertEqual(category_bootstrap([.5,.5])['ci95'],[.5,.5])
        self.assertEqual(category_bootstrap([.2,.8]),category_bootstrap([.2,.8]))
        with self.assertRaisesRegex(ValueError,'Incomplete breadth'):
            summarize([])

    def test_full_seeds_reuse_and_reject_corrupted_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            data = make_category(base/'data')
            def command(output, *extra):
                return [sys.executable,str(ROOT/'scripts/run_fewshot.py'),
                        '--data-root',str(data),'--categories','bottle',
                        '--methods','tiny_random','--shots','full','--seeds','0','1',
                        '--full-shot-all-seeds','--no-pixel-metrics',
                        '--resize','64','--imagesize','64','--output',str(output),*extra]
            first=base/'first'
            result=subprocess.run(command(first),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            source=first/'results.json'
            payload=json.loads(source.read_text())
            self.assertEqual([r['seed'] for r in payload['runs']],[0,1])
            second=base/'second'
            result=subprocess.run(command(second,'--reuse-results',str(source)),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            imported=json.loads((second/'results.json').read_text())
            self.assertEqual(imported['imported_records'],2)
            self.assertEqual(imported['timings'],[])
            self.assertEqual([r['image_auroc'] for r in imported['runs']],
                             [r['image_auroc'] for r in payload['runs']])
            (first/payload['runs'][0]['predictions_path']).write_text('corrupt')
            result=subprocess.run(command(base/'third','--reuse-results',str(source)),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Reuse sidecar hash mismatch',result.stderr)


if __name__=='__main__':unittest.main()
