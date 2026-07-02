"""Tests for the cc_memory hook backstop: finalize收口 + drain lease + WAL checkpoint
busy-detection + the PostToolUse mutation regex + REVIEW_MARK exit-code discrimination.

Covers the concurrency-sensitive surface added 2026-06-19 (entry
cc-memory-hook-4-a-i-gpu-posttooluse-async). All db work runs on isolated temp copies /
temp dbs; the live store is never touched. GPU is never invoked (finalize --no-gpu)."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / "cc_memory" / "mem.py"
HOOK = ROOT / "cc_memory" / "hooks" / "cc_mem_hook.py"
REAL_DB = ROOT / "cc_memory" / "memory.db"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mem = _load("_ccmem_under_test", MEM)
hook = _load("_cchook_under_test", HOOK)


class MutationRegexTests(unittest.TestCase):
    POS = [
        "python cc_memory/mem.py set-fact --subject x --predicate y --value z",
        'python cc_memory/mem.py --db "C:/claude pj/zmd-pj/cc_memory/memory.db" set-fact --subject a',
        "python cc_memory/mem.py --db=C:/x add-entry --title t",
        'python cc_memory/mem.py --export "C:/a b/MEMORY.md" link a b',
        "python cc_memory/mem.py review-relation 5 accept",
        "python cc_memory/mem.py --session abc add-event --text hi",
    ]
    NEG = [
        "python cc_memory/mem.py boot",
        "python cc_memory/mem.py read some-link-node",
        'python cc_memory/mem.py search "add-entry foo"',
        "python cc_memory/mem.py finalize",
        "python cc_memory/mem.py rebuild-embeddings",
        "python cc_memory/mem.py --session add-entry read foo",  # flag value == subcommand name
        "echo just mentioning mem.py here",
    ]

    def test_positives_match(self) -> None:
        for cmd in self.POS:
            self.assertTrue(hook._MUTATION_RE.search(cmd), f"should match: {cmd}")

    def test_negatives_reject(self) -> None:
        for cmd in self.NEG:
            self.assertFalse(hook._MUTATION_RE.search(cmd), f"should NOT match: {cmd}")

    def test_finalize_never_self_triggers(self) -> None:
        self.assertNotIn("finalize", mem_mutating := set(hook.MUTATING))
        self.assertNotIn("rebuild-embeddings", mem_mutating)


class LeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lease_test_"))
        self.lock = self.tmp / ".finalize.lock"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_acquire_busy_release(self) -> None:
        with mem.finalize_lease(path=self.lock):
            self.assertTrue(self.lock.exists())
            # a second acquire while held must be refused
            with self.assertRaises(mem._LeaseBusy):
                with mem.finalize_lease(path=self.lock):
                    pass
        self.assertFalse(self.lock.exists(), "lease must be released on exit")

    def test_stale_lock_is_stolen(self) -> None:
        self.lock.write_bytes(b"99999-0")  # foreign token
        old = time.time() - 10_000
        os.utime(self.lock, (old, old))  # make it look stuck
        with mem.finalize_lease(path=self.lock, stale_seconds=900):
            self.assertTrue(self.lock.exists())
        self.assertFalse(self.lock.exists())

    def test_release_does_not_delete_foreign_lock(self) -> None:
        # Acquire, then simulate being stolen-from: overwrite with a foreign token.
        with mem.finalize_lease(path=self.lock):
            self.lock.write_bytes(b"different-owner")
        # our release must NOT have deleted the foreign lock
        self.assertTrue(self.lock.exists())
        self.assertEqual(self.lock.read_bytes(), b"different-owner")


class CheckpointWalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wal_test_"))
        self.db = self.tmp / "t.db"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ok_when_uncontended(self) -> None:
        con = mem.connect(self.db)
        con.execute("CREATE TABLE t(x)")
        con.execute("INSERT INTO t VALUES(1)")
        con.commit()
        con.close()
        self.assertEqual(mem._checkpoint_wal(self.db), "ok")

    def test_busy_then_ok_under_reader(self) -> None:
        con = mem.connect(self.db)
        con.execute("CREATE TABLE t(x)")
        con.execute("INSERT INTO t VALUES(1)")
        con.commit()
        reader = sqlite3.connect(str(self.db))
        reader.execute("PRAGMA busy_timeout=200")
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM t").fetchall()  # pin an old snapshot
        con.execute("INSERT INTO t VALUES(2)")
        con.commit()  # WAL frames past the reader's mark
        self.assertEqual(mem._checkpoint_wal(self.db), "busy")
        reader.commit()
        reader.close()
        self.assertEqual(mem._checkpoint_wal(self.db), "ok")
        con.close()


@unittest.skipUnless(REAL_DB.exists(), "no cc_memory/memory.db to copy")
class FinalizeExitPolicyTests(unittest.TestCase):
    """finalize --no-gpu against a temp copy: structural error -> exit 2 (wake),
    pending high-score suggestion -> exit 0 (soft, no wake)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="finalize_test_"))
        self.db = self.tmp / "memory.db"
        self.export = self.tmp / "MEMORY.md"
        shutil.copy2(REAL_DB, self.db)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _finalize(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MEM), "--db", str(self.db), "--export", str(self.export), "finalize", "--no-gpu"],
            cwd=ROOT, text=True, capture_output=True, timeout=60,
        )

    def test_clean_copy_exits_ok(self) -> None:
        proc = self._finalize()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("status=ok", proc.stdout)

    def test_structural_error_exits_2(self) -> None:
        con = sqlite3.connect(str(self.db))
        con.execute(
            "INSERT INTO edges(source_type,source_id,edge_type,target_type,target_id,hard,reason,created_at) "
            "VALUES('entry','memory-runtime-protocol','DEPENDS_ON','fact','__does_not_exist__',1,'test',?)",
            (mem.now(),),
        )
        con.commit()
        con.close()
        proc = self._finalize()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("status=check_fail", proc.stdout)

    def test_pending_review_exits_0(self) -> None:
        con = sqlite3.connect(str(self.db))
        con.row_factory = sqlite3.Row
        ids = [r["id"] for r in con.execute("SELECT id FROM entries WHERE status='active' ORDER BY id LIMIT 2")]
        self.assertEqual(len(ids), 2, "need two entries to wire a suggestion")
        con.execute(
            "INSERT INTO relation_suggestions("
            "source_type,source_id,target_type,target_id,suggested_edge_type,score,signals_json,status,created_at) "
            "VALUES('entry',?,'entry',?,'RELATED_TO',99.0,'[]','pending',?) "
            "ON CONFLICT(source_type,source_id,target_type,target_id) DO UPDATE SET score=99.0,status='pending'",
            (ids[0], ids[1], mem.now()),
        )
        con.commit()
        con.close()
        proc = self._finalize()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("status=pending_review", proc.stdout)


if __name__ == "__main__":
    unittest.main()
