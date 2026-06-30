from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / "cc_memory" / "mem.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mem = _load("_ccmem_prune_under_test", MEM)


class PruneScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="prune_scan_test_"))
        self.db = self.tmp / "memory.db"
        self.out = self.tmp / "report.json"
        self.cards = self.tmp / "cards"
        self.cards.mkdir()
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        mem.init_schema(con)
        self._populate(con)
        con.commit()
        con.close()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_scan(self) -> dict:
        proc = subprocess.run(
            [
                sys.executable,
                str(MEM),
                "--db",
                str(self.db),
                "prune",
                "scan",
                "--out",
                str(self.out),
                "--cards-dir",
                str(self.cards),
                "--duplicate-cosine-threshold",
                "0.90",
                "--oversized-bytes",
                "128",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(self.out.exists(), proc.stdout)
        return json.loads(self.out.read_text(encoding="utf-8"))

    def records(self, report: dict, flag: str, section: str | None = None) -> list[dict]:
        group = report["groups"][flag]
        if section:
            return group[section]
        return group["locked_review_only"] + group["unlocked_candidates"]

    def item_ids(self, report: dict, flag: str, section: str | None = None) -> set[str]:
        return {record["item_id"] for record in self.records(report, flag, section)}

    def _add_entry(
        self,
        con: sqlite3.Connection,
        entry_id: str,
        title: str,
        body: str,
        *,
        pinned: bool = False,
        metadata: dict | None = None,
    ) -> None:
        mem.add_entry_row(con, entry_id, title, body, pinned=pinned, metadata=metadata or {})

    def _add_fact(self, con: sqlite3.Connection, fact_id: str, subject: str, predicate: str, value: str) -> None:
        mem.add_fact_row(con, fact_id, subject, predicate, value)

    def _add_embedding_model(self, con: sqlite3.Connection) -> str:
        model_id = mem.embedding_model_id("fake/prune-scan")
        con.execute(
            """
            INSERT OR REPLACE INTO embedding_models(id,provider,model_name,dim,normalize,device,created_at,metadata_json)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (model_id, mem.EMBED_PROVIDER, "fake/prune-scan", 3, 1, "cpu", mem.now(), "{}"),
        )
        return model_id

    def _add_embedding(self, con: sqlite3.Connection, model_id: str, typ: str, node_id: str, vector: list[float]) -> None:
        table = "facts" if typ == "fact" else "entries"
        row = con.execute(f"SELECT * FROM {table} WHERE id=?", (node_id,)).fetchone()
        self.assertIsNotNone(row)
        text = mem.node_text_for_relation(row, typ)
        con.execute(
            """
            INSERT OR REPLACE INTO node_embeddings(node_type,node_id,model_id,content_hash,dim,dtype,vector_blob,created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                typ,
                node_id,
                model_id,
                mem.node_content_hash(typ, node_id, text),
                len(vector),
                "float32",
                mem.vector_to_blob(vector),
                mem.now(),
            ),
        )

    def _populate(self, con: sqlite3.Connection) -> None:
        model_id = self._add_embedding_model(con)

        self._add_entry(con, "dup-overlap-a", "Duplicate Alpha A", "same durable guidance about alpha routing")
        self._add_entry(con, "dup-overlap-b", "Duplicate Alpha B", "same durable guidance about alpha routing copy")
        self._add_embedding(con, model_id, "entry", "dup-overlap-a", [1.0, 0.0, 0.0])
        self._add_embedding(con, model_id, "entry", "dup-overlap-b", [1.0, 0.0, 0.0])

        self._add_entry(con, "dup-kind-rule", "Rule-like note", "cosine twin but kind mismatch", metadata={"kind": "rule"})
        self._add_entry(con, "dup-kind-entry", "Plain note", "cosine twin but kind mismatch")
        self._add_embedding(con, model_id, "entry", "dup-kind-rule", [0.0, 1.0, 0.0])
        self._add_embedding(con, model_id, "entry", "dup-kind-entry", [0.0, 1.0, 0.0])

        self._add_fact(con, "fact-subject-a", "subject-a", "same", "cosine twin subject a")
        self._add_fact(con, "fact-subject-b", "subject-b", "same", "cosine twin subject b")
        self._add_embedding(con, model_id, "fact", "fact-subject-a", [0.0, 0.0, 1.0])
        self._add_embedding(con, model_id, "fact", "fact-subject-b", [0.0, 0.0, 1.0])

        self._add_entry(con, "stale-active-covered", "Old active covered", "old guidance that should have been superseded")
        self._add_entry(con, "stale-replacement", "Replacement", "replacement guidance")
        mem.add_edge_row(con, "entry", "stale-replacement", "SUPERSEDES", "entry", "stale-active-covered", reason="test")

        self._add_entry(
            con,
            "stale-missing-path",
            "Deprecated low confidence path",
            "This obsolete low-confidence note references src/no_such_file_zz.py for old handling.",
            metadata={"confidence": "low"},
        )

        self._add_entry(con, "orphan-entry", "Lonely", "no edges touch this node")

        oversized = "\n\n".join(
            [
                "# Topic A\n- item one\n- item two\n- item three",
                "# Topic B\n- item four\n- item five\n- item six",
                "# Topic C\nThe body keeps going long enough to cross the small test threshold.",
                "Paragraph four with more unrelated operational detail.",
                "Paragraph five with another topic.",
            ]
        )
        self._add_entry(con, "oversized-mixed-entry", "Mixed oversized", oversized)

        promotion = (
            "Owner protocol: agents must preserve the authority boundary and never bypass the gate. "
            "This durable rule belongs in route-time memory because future sessions need it before acting. "
            "The note is intentionally long enough to look like a stable card candidate."
        )
        self._add_entry(con, "promotion-protocol", "Promotion protocol", promotion)

        self._add_entry(con, "vnext-existing-card", "Vnext Existing Card", "active source already has a same-name vnext card")
        self.cards.joinpath("vnext-existing-card.md").write_text(
            "---\ntitle: Vnext Existing Card\n---\n# Vnext Existing Card\n",
            encoding="utf-8",
        )

        self._add_entry(con, "locked-pinned-orphan", "Pinned orphan", "pinned node with no edges", pinned=True)
        self._add_entry(con, "prune-self-entry", "Prune self", "this governance item must not be scanned")

    def test_prune_scan_reports_all_six_flag_types(self) -> None:
        report = self.run_scan()
        self.assertIn("entry:dup-overlap-a <-> entry:dup-overlap-b", self.item_ids(report, "duplicate_or_overlap"))
        self.assertIn("entry:stale-active-covered", self.item_ids(report, "stale_or_low_value"))
        self.assertIn("entry:orphan-entry", self.item_ids(report, "orphan"))
        self.assertIn("entry:oversized-mixed-entry", self.item_ids(report, "oversized_mixed"))
        self.assertIn("entry:promotion-protocol", self.item_ids(report, "promotion_candidate"))
        self.assertIn("entry:vnext-existing-card", self.item_ids(report, "archive_candidate"))
        promotion = next(record for record in self.records(report, "promotion_candidate") if record["item_id"] == "entry:promotion-protocol")
        self.assertEqual(promotion["confidence"], "low")

    def test_safety_locked_items_are_not_unlocked_candidates(self) -> None:
        report = self.run_scan()
        locked = self.item_ids(report, "orphan", "locked_review_only")
        unlocked = self.item_ids(report, "orphan", "unlocked_candidates")
        self.assertIn("entry:locked-pinned-orphan", locked)
        self.assertNotIn("entry:locked-pinned-orphan", unlocked)
        record = next(record for record in self.records(report, "orphan", "locked_review_only") if record["item_id"] == "entry:locked-pinned-orphan")
        self.assertTrue(record["safety_lock"]["locked"])
        self.assertIn("pinned", record["safety_lock"]["reasons"])

    def test_duplicate_denial_gates_and_prune_self_exclusion(self) -> None:
        report = self.run_scan()
        duplicate_ids = "\n".join(self.item_ids(report, "duplicate_or_overlap"))
        self.assertNotIn("dup-kind-rule", duplicate_ids)
        self.assertNotIn("fact-subject-a", duplicate_ids)
        all_ids = "\n".join(
            record["item_id"]
            for flag in report["groups"]
            for section in ("locked_review_only", "unlocked_candidates")
            for record in report["groups"][flag][section]
        )
        self.assertNotIn("prune-self-entry", all_ids)

    def test_scan_does_not_mutate_database_bytes(self) -> None:
        before = self.db.read_bytes()
        self.run_scan()
        after = self.db.read_bytes()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
