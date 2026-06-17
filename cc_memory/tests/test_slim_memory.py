from __future__ import annotations

import shutil
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / 'cc_memory' / 'mem.py'
REAL_DB = ROOT / 'cc_memory' / 'memory.db'
EMBED_PY = Path(r'C:\Users\22957\zmd_embed_ab\venv\Scripts\python.exe')


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

    def run_mem(self, *args: str, env: dict[str, str] | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        return subprocess.run(
            [sys.executable, str(MEM), '--db', str(self.db), '--export', str(self.export), *args],
            cwd=ROOT, text=True, capture_output=True, timeout=timeout, env=full_env,
        )

    def fake_embedding_env(self) -> dict[str, str]:
        fake_root = self.tmp / 'fake_embed_runtime'
        fake_st = fake_root / 'sentence_transformers'
        fake_st.mkdir(parents=True)
        fake_st.joinpath('__init__.py').write_text(
            """
import numpy as np


def _vec(text):
    text = text.lower()
    if 'zzztargetalpha' in text or 'qqqquerybeta' in text:
        return [1.0, 0.0, 0.0, 0.0]
    return [0.0, 1.0, 0.0, 0.0]


class SentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, texts, **kwargs):
        return np.asarray([_vec(t) for t in texts], dtype=np.float32)

    def encode_query(self, texts, **kwargs):
        return self.encode(texts, **kwargs)
""".lstrip(),
            encoding='utf-8',
        )
        fake_root.joinpath('torch.py').write_text(
            """
class _Cuda:
    def is_available(self):
        return False

    def empty_cache(self):
        pass


cuda = _Cuda()
""".lstrip(),
            encoding='utf-8',
        )
        python_path = str(fake_root)
        if os.environ.get('PYTHONPATH'):
            python_path += os.pathsep + os.environ['PYTHONPATH']
        return {
            'CC_MEMORY_EMBED_PYTHON': sys.executable,
            'PYTHONPATH': python_path,
            'HF_HOME': str(self.tmp / 'hf_cache'),
            'HF_HUB_OFFLINE': '1',
            'TRANSFORMERS_OFFLINE': '1',
        }

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

    def test_embedding_schema_migration_idempotent(self) -> None:
        p1 = self.run_mem('check')
        self.assertEqual(p1.returncode, 0, p1.stdout + p1.stderr)
        p2 = self.run_mem('check')
        self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)
        con = sqlite3.connect(self.db)
        try:
            tables = {
                row[0]
                for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            self.assertIn('embedding_models', tables)
            self.assertIn('node_embeddings', tables)
            version = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
            self.assertEqual(version, '3')
        finally:
            con.close()

    def test_rebuild_embeddings_populates_node_embeddings_with_gpu_venv(self) -> None:
        if not EMBED_PY.exists():
            self.skipTest('embedding venv python is absent')
        p = self.run_mem('rebuild-embeddings', '--batch-size', '4', timeout=240)
        if p.returncode == 2:
            self.skipTest('embedding backend unavailable: ' + (p.stderr or p.stdout))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        con = sqlite3.connect(self.db)
        try:
            count = con.execute('SELECT count(*) FROM node_embeddings').fetchone()[0]
            dim = con.execute('SELECT dim FROM embedding_models LIMIT 1').fetchone()[0]
            self.assertGreater(count, 0)
            self.assertGreater(dim, 0)
        finally:
            con.close()
        p2 = self.run_mem('rebuild-embeddings', '--batch-size', '4', timeout=240)
        self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)
        self.assertIn('embedded=0', p2.stdout)

    def test_semantic_suggest_merges_and_still_gates(self) -> None:
        env = self.fake_embedding_env()
        target = self.run_mem(
            'set-fact', '--id', 'semantic-target-fact',
            '--subject', 'semantic', '--predicate', 'target', '--value', 'zzztargetalpha',
            env=env,
        )
        self.assertEqual(target.returncode, 0, target.stdout + target.stderr)
        rebuilt = self.run_mem('rebuild-embeddings', '--model', 'fake/semantic-model', env=env, timeout=60)
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout + rebuilt.stderr)
        suggest = self.run_mem(
            'suggest', '--semantic', '--model', 'fake/semantic-model',
            '--title', 'semantic query', '--body', 'qqqquerybeta',
            env=env, timeout=60,
        )
        self.assertEqual(suggest.returncode, 0, suggest.stdout + suggest.stderr)
        self.assertIn('semantic-target-fact', suggest.stdout)
        self.assertIn('dense semantic cosine', suggest.stdout)
        add = self.run_mem(
            '--session', 'semantic-test', 'add-entry', '--id', 'semantic-gate-entry',
            '--title', 'semantic gate', '--body', 'qqqquerybeta',
            '--semantic', '--model', 'fake/semantic-model',
            env=env, timeout=60,
        )
        self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
        self.assertIn('relation suggestions stored', add.stdout)
        chk = self.run_mem('check')
        self.assertNotEqual(chk.returncode, 0, 'check must FAIL while semantic suggestions are pending')
        self.assertIn('need review', chk.stdout + chk.stderr)

    def test_existing_commands_work_when_embedding_backend_absent(self) -> None:
        env = {'CC_MEMORY_EMBED_PYTHON': str(self.tmp / 'missing-python.exe')}
        search = self.run_mem('search', 'memory', env=env)
        self.assertEqual(search.returncode, 0, search.stdout + search.stderr)
        lexical = self.run_mem('suggest', '--title', 'codex workflow', '--body', 'workflow 派子代理用 codex', env=env)
        self.assertEqual(lexical.returncode, 0, lexical.stdout + lexical.stderr)
        self.assertIn('relation suggestions', lexical.stdout)
        semantic = self.run_mem(
            'suggest', '--semantic', '--title', 'codex workflow', '--body', 'workflow 派子代理用 codex',
            env=env,
        )
        self.assertEqual(semantic.returncode, 0, semantic.stdout + semantic.stderr)
        self.assertIn('relation suggestions', semantic.stdout)
        self.assertIn('semantic suggestions unavailable', semantic.stderr)

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
