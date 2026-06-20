from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / 'cc_memory' / 'mem.py'
RERANK_HELPER = ROOT / 'cc_memory' / 'rerank_helper.py'
REAL_DB = ROOT / 'cc_memory' / 'memory.db'
EMBED_PY = Path(r'C:\Users\22957\zmd_embed_ab\venv\Scripts\python.exe')
RERANK_PY = Path(os.environ.get('CC_MEMORY_RERANK_PYTHON', r'C:\Users\22957\zmd_embed_ab\venv\Scripts\python.exe'))
RERANK_MODEL = 'Qwen/Qwen3-Reranker-0.6B'


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

    def test_cross_session_preamble_on_query(self) -> None:
        # design B: query commands surface unread cross-session changes WITHOUT
        # advancing the watermark; only boot marks them read.
        # fresh session (no watermark) -> silent, there is no baseline to delta against.
        r = self.run_mem('search', '记忆', env={'CLAUDE_CODE_SESSION_ID': 'TESTfresh-no-watermark'})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('Heads-up', r.stdout)

        test_sid = 'TESTbehind-watermark'
        with sqlite3.connect(self.db) as con:
            maxid = con.execute('SELECT COALESCE(MAX(id),0) FROM mutations').fetchone()[0]
            if maxid == 0:
                self.skipTest('temp db has no mutations to delta against')
            con.execute(
                'INSERT INTO read_watermarks(session_id,last_seen_mutation_id,last_query_at) VALUES(?,?,?)',
                (test_sid, 0, '2026-01-01T00:00:00Z'),
            )
            con.commit()

        behind = {'CLAUDE_CODE_SESSION_ID': test_sid}
        r2 = self.run_mem('search', '记忆', env=behind)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn('Heads-up', r2.stdout)
        self.assertIn('unread change', r2.stdout)

        # design B core: a query command must NOT advance the watermark.
        with sqlite3.connect(self.db) as con:
            wm = con.execute(
                'SELECT last_seen_mutation_id FROM read_watermarks WHERE session_id=?', (test_sid,)
            ).fetchone()[0]
        self.assertEqual(wm, 0, 'query command must not advance the watermark (design B)')

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

    def fake_rerank_env(self) -> dict[str, str]:
        fake_root = self.tmp / 'fake_rerank_runtime'
        fake_st = fake_root / 'sentence_transformers'
        fake_st.mkdir(parents=True)
        fake_st.joinpath('__init__.py').write_text(
            """
class CrossEncoder:
    def __init__(self, *args, **kwargs):
        pass

    def predict(self, pairs, **kwargs):
        scores = []
        for _query, doc in pairs:
            text = doc.lower()
            if 'rerank-keep-alpha' in text:
                scores.append(0.95)
            else:
                scores.append(0.05)
        return scores
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


class _Sigmoid:
    def __call__(self, value):
        return value


class _NN:
    Sigmoid = _Sigmoid


cuda = _Cuda()
nn = _NN()
""".lstrip(),
            encoding='utf-8',
        )
        python_path = str(fake_root)
        if os.environ.get('PYTHONPATH'):
            python_path += os.pathsep + os.environ['PYTHONPATH']
        return {
            'CC_MEMORY_RERANK_PYTHON': sys.executable,
            'PYTHONPATH': python_path,
            'HF_HOME': str(self.tmp / 'hf_cache'),
            'HF_HUB_OFFLINE': '1',
            'TRANSFORMERS_OFFLINE': '1',
        }

    def add_rerank_fixture_facts(self) -> None:
        keep = self.run_mem(
            'set-fact', '--force', '--id', 'rerank-keep-alpha',
            '--subject', 'rerank', '--predicate', 'keep',
            '--value', 'rerank-keep-alpha marker for a high relevance relation candidate',
        )
        self.assertEqual(keep.returncode, 0, keep.stdout + keep.stderr)
        drop = self.run_mem(
            'set-fact', '--force', '--id', 'rerank-drop-alpha',
            '--subject', 'rerank', '--predicate', 'drop',
            '--value', 'rerank-drop-alpha marker for a lexical false positive relation candidate',
        )
        self.assertEqual(drop.returncode, 0, drop.stdout + drop.stderr)

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

    def test_rerank_suggest_prunes_low_candidate_and_keeps_high(self) -> None:
        self.add_rerank_fixture_facts()
        env = self.fake_rerank_env()
        p = self.run_mem(
            'suggest',
            '--title', 'rerank-keep-alpha rerank-drop-alpha',
            '--body', 'candidate relation discovery',
            '--rerank',
            '--json',
            env=env,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        suggestions = json.loads(p.stdout)
        ids = [s['id'] for s in suggestions]
        self.assertIn('rerank-keep-alpha', ids)
        self.assertNotIn('rerank-drop-alpha', ids)
        kept = next(s for s in suggestions if s['id'] == 'rerank-keep-alpha')
        self.assertEqual(kept['rerank_score'], 0.95)
        self.assertGreaterEqual(kept['score'], 12.0)

    def test_add_entry_rerank_prunes_before_store_and_gate_still_fails(self) -> None:
        self.add_rerank_fixture_facts()
        env = self.fake_rerank_env()
        add = self.run_mem(
            '--session', 'rerank-test',
            'add-entry', '--id', 'rerank-gate-entry',
            '--title', 'rerank-keep-alpha rerank-drop-alpha',
            '--body', 'candidate relation discovery',
            '--rerank',
            env=env,
        )
        self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
        self.assertIn('relation suggestions stored: 1', add.stdout)
        rows = self.run_mem('relations', '--all', '--json')
        self.assertEqual(rows.returncode, 0, rows.stdout + rows.stderr)
        stored_for_entry = [
            row for row in json.loads(rows.stdout)
            if row['source_type'] == 'entry' and row['source_id'] == 'rerank-gate-entry'
        ]
        targets = {row['target_id'] for row in stored_for_entry}
        self.assertIn('rerank-keep-alpha', targets)
        self.assertNotIn('rerank-drop-alpha', targets)
        chk = self.run_mem('check')
        self.assertNotEqual(chk.returncode, 0, 'check must FAIL while reranked high-score suggestions are pending')
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

    def test_rerank_backend_absent_keeps_suggest_stdout_unchanged(self) -> None:
        self.add_rerank_fixture_facts()
        args = (
            'suggest',
            '--title', 'rerank-keep-alpha rerank-drop-alpha',
            '--body', 'candidate relation discovery',
        )
        baseline = self.run_mem(*args)
        self.assertEqual(baseline.returncode, 0, baseline.stdout + baseline.stderr)
        env = {'CC_MEMORY_RERANK_PYTHON': str(self.tmp / 'missing-rerank-python.exe')}
        degraded = self.run_mem(*args, '--rerank', env=env)
        self.assertEqual(degraded.returncode, 0, degraded.stdout + degraded.stderr)
        self.assertEqual(degraded.stdout, baseline.stdout)
        self.assertIn('rerank suggestions unavailable', degraded.stderr)

    def test_set_fact_rerank_does_not_trigger_semantic_backend(self) -> None:
        # regression: set-fact --rerank (no --semantic) must NOT silently activate the P1 embed backend.
        env = {
            'CC_MEMORY_EMBED_PYTHON': str(self.tmp / 'missing-embed-python.exe'),
            'CC_MEMORY_RERANK_PYTHON': str(self.tmp / 'missing-rerank-python.exe'),
        }
        p = self.run_mem(
            '--session', 'rerank-only', 'set-fact', '--id', 'rerank-only-fact',
            '--subject', 'rerank', '--predicate', 'only',
            '--value', '记忆系统 memory.db codex workflow rerank only marker',
            '--rerank', env=env,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        err = p.stdout + p.stderr
        self.assertNotIn(
            'semantic suggestions unavailable', err,
            'set-fact --rerank must not probe the embed backend when --semantic is absent',
        )
        self.assertIn('rerank suggestions unavailable', err)

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

    def test_real_qwen_rerank_helper_smoke_when_cached(self) -> None:
        hf_home = Path(os.environ.get('HF_HOME', r'E:\caches\huggingface'))
        model_cache = hf_home / 'hub' / 'models--Qwen--Qwen3-Reranker-0.6B'
        if not RERANK_PY.exists():
            self.skipTest('rerank venv python is absent')
        if not model_cache.exists():
            self.skipTest('Qwen reranker cache is absent')
        env = os.environ.copy()
        env.update({
            'HF_HOME': str(hf_home),
            'HF_HUB_CACHE': str(hf_home / 'hub'),
            'HF_XET_CACHE': str(hf_home / 'xet'),
            'HF_HUB_OFFLINE': '1',
            'TRANSFORMERS_OFFLINE': '1',
        })
        payload = {
            'query': 'What is the capital of China?',
            'docs': [
                'The capital of China is Beijing.',
                'A bicycle wheel uses spokes and a tire.',
            ],
            'model': RERANK_MODEL,
        }
        p = subprocess.run(
            [str(RERANK_PY), str(RERANK_HELPER)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=600,
            cwd=ROOT,
            env=env,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        scores = json.loads(p.stdout)['scores']
        self.assertEqual(len(scores), 2)
        self.assertGreater(scores[0], scores[1])


if __name__ == '__main__':
    unittest.main()
