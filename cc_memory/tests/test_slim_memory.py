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

    def test_suggest_returns_candidates(self) -> None:
        # querying terms that overlap existing memory should surface relation candidates
        p = self.run_mem('suggest', '--title', 'codex workflow', '--body', 'workflow 派子代理用 codex')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('relation suggestions', p.stdout)

    def test_add_entry_triggers_review_gate(self) -> None:
        # add-entry auto-creates pending relation suggestions; check must then FAIL (option-A gate)
        add = self.run_mem('--session', 'test-sess', 'add-entry', '--id', 'gate-test-entry',
                            '--title', 'gate test', '--body', '记忆系统 memory.db impact 影响面 codex workflow')
        self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
        self.assertIn('relation suggestions stored', add.stdout)
        chk = self.run_mem('check')
        self.assertNotEqual(chk.returncode, 0, 'check must FAIL while high-score suggestions are pending')
        self.assertIn('need review', chk.stdout + chk.stderr)

    def test_watermark_reports_other_session_changes(self) -> None:
        # session A boots (sets watermark), session B mutates, session A re-boots and sees B's change
        self.assertEqual(self.run_mem('--session', 'sess-A', 'boot').returncode, 0)
        b = self.run_mem('--session', 'sess-B', 'set-fact', '--id', 'wm-test-fact',
                         '--subject', 'x', '--predicate', 'y', '--value', 'z')
        self.assertEqual(b.returncode, 0, b.stdout + b.stderr)
        a2 = self.run_mem('--session', 'sess-A', 'boot')
        self.assertEqual(a2.returncode, 0, a2.stdout + a2.stderr)
        self.assertIn('sess-B', a2.stdout)


if __name__ == '__main__':
    unittest.main()
