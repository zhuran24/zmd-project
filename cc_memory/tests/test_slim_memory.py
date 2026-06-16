from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / 'cc_memory' / 'mem.py'
REAL_DB = ROOT / 'cc_memory' / 'memory.db'


@unittest.skipUnless(REAL_DB.exists(), 'no cc_memory/memory.db to copy')
class SlimMemoryTests(unittest.TestCase):
    """Runs mem.py against an isolated temp copy of the real db; never touches live state."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='slim_mem_test_'))
        self.db = self.tmp / 'memory.db'
        self.export = self.tmp / 'MEMORY.md'
        shutil.copy2(REAL_DB, self.db)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_mem(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MEM), '--db', str(self.db), '--export', str(self.export), *args],
            cwd=ROOT, text=True, capture_output=True, timeout=30,
        )

    def test_boot(self) -> None:
        p = self.run_mem('boot')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('One source of truth', p.stdout)

    def test_check_and_export(self) -> None:
        p = self.run_mem('export')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.run_mem('check')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_impact_core_fact(self) -> None:
        p = self.run_mem('impact', 'fact-impact-before-memory-change')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('impact from fact:', p.stdout)

    def test_search(self) -> None:
        p = self.run_mem('search', 'memory')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.strip())


if __name__ == '__main__':
    unittest.main()
