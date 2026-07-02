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

BACKDATED = "2020-01-01T00:00:00Z"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mem = _load("_ccmem_prune_under_test", MEM)


class PruneScanTwoTierTests(unittest.TestCase):
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
                "--relink-min-age-days",
                "7",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(self.out.exists(), proc.stdout)
        return json.loads(self.out.read_text(encoding="utf-8"))

    # --- report navigation helpers -------------------------------------------------
    def det(self, report: dict, flag: str, section: str | None = None) -> list[dict]:
        group = report["deterministic"][flag]
        if section:
            return group[section]
        return group["locked_review_only"] + group["candidates"]

    def det_ids(self, report: dict, flag: str, section: str | None = None) -> set[str]:
        return {r["item_id"] for r in self.det(report, flag, section)}

    def adv_ids(self, report: dict, flag: str) -> set[str]:
        return {r["item_id"] for r in report["advisory"][flag]}

    # --- fixtures ------------------------------------------------------------------
    def _add_entry(self, con, entry_id, title, body, *, pinned=False, metadata=None) -> None:
        mem.add_entry_row(con, entry_id, title, body, pinned=pinned, metadata=metadata or {})

    def _add_fact(self, con, fact_id, subject, predicate, value) -> None:
        mem.add_fact_row(con, fact_id, subject, predicate, value)

    def _backdate(self, con, typ, node_id) -> None:
        table = "facts" if typ == "fact" else "entries"
        con.execute(f"UPDATE {table} SET created_at=? WHERE id=?", (BACKDATED, node_id))

    def _add_embedding_model(self, con) -> str:
        model_id = mem.embedding_model_id("fake/prune-scan")
        con.execute(
            "INSERT OR REPLACE INTO embedding_models(id,provider,model_name,dim,normalize,device,created_at,metadata_json)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (model_id, mem.EMBED_PROVIDER, "fake/prune-scan", 3, 1, "cpu", mem.now(), "{}"),
        )
        return model_id

    def _add_embedding(self, con, model_id, typ, node_id, vector) -> None:
        table = "facts" if typ == "fact" else "entries"
        row = con.execute(f"SELECT * FROM {table} WHERE id=?", (node_id,)).fetchone()
        self.assertIsNotNone(row)
        text = mem.node_text_for_relation(row, typ)
        con.execute(
            "INSERT OR REPLACE INTO node_embeddings(node_type,node_id,model_id,content_hash,dim,dtype,vector_blob,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (typ, node_id, model_id, mem.node_content_hash(typ, node_id, text), len(vector), "float32", mem.vector_to_blob(vector), mem.now()),
        )

    def _populate(self, con) -> None:
        model_id = self._add_embedding_model(con)

        # advisory: duplicate (same kind, high cosine, not denied)
        self._add_entry(con, "dup-a", "Dup Alpha A", "same durable guidance about alpha routing")
        self._add_entry(con, "dup-b", "Dup Alpha B", "same durable guidance about alpha routing copy")
        self._add_embedding(con, model_id, "entry", "dup-a", [1.0, 0.0, 0.0])
        self._add_embedding(con, model_id, "entry", "dup-b", [1.0, 0.0, 0.0])

        # duplicate denial: kind mismatch
        self._add_entry(con, "dup-kind-rule", "Rule-like", "cosine twin but kind mismatch", metadata={"kind": "rule"})
        self._add_entry(con, "dup-kind-entry", "Plain", "cosine twin but kind mismatch")
        self._add_embedding(con, model_id, "entry", "dup-kind-rule", [0.0, 1.0, 0.0])
        self._add_embedding(con, model_id, "entry", "dup-kind-entry", [0.0, 1.0, 0.0])

        # duplicate denial: fact subject mismatch
        self._add_fact(con, "fact-subj-a", "subject-a", "same", "cosine twin subject a")
        self._add_fact(con, "fact-subj-b", "subject-b", "same", "cosine twin subject b")
        self._add_embedding(con, model_id, "fact", "fact-subj-a", [0.0, 0.0, 1.0])
        self._add_embedding(con, model_id, "fact", "fact-subj-b", [0.0, 0.0, 1.0])

        # deterministic: relink_candidate (aged orphan flagged; fresh orphan gated out)
        self._add_entry(con, "relink-old", "Aged orphan", "old standalone note with no edges")
        self._backdate(con, "entry", "relink-old")
        self._add_entry(con, "relink-fresh", "Fresh orphan", "just-created note, edges may not be linked yet")
        self._add_entry(con, "relink-locked-old", "Pinned aged orphan", "aged orphan but pinned", pinned=True)
        self._backdate(con, "entry", "relink-locked-old")
        self._add_entry(con, "relink-badtime", "Unparseable-age orphan", "orphan whose created_at cannot be parsed")
        con.execute("UPDATE entries SET created_at='not-a-date' WHERE id='relink-badtime'")

        # deterministic: active_superseded (unlocked; the SUPERSEDES edge is the signal, not a lock)
        self._add_entry(con, "super-source", "Replacement", "the replacement guidance")
        self._add_entry(con, "super-target", "Superseded but active", "old guidance replaced by super-source")
        mem.add_edge_row(con, "entry", "super-source", "SUPERSEDES", "entry", "super-target", reason="test")

        # deterministic: active_superseded but LOCKED by a non-SUPERSEDES incoming edge
        self._add_entry(con, "super-source2", "Replacement 2", "second replacement")
        self._add_entry(con, "related-src", "Related source", "points at the locked target")
        self._add_entry(con, "super-target-locked", "Superseded + referenced", "replaced yet still referenced")
        mem.add_edge_row(con, "entry", "super-source2", "SUPERSEDES", "entry", "super-target-locked", reason="test")
        mem.add_edge_row(con, "entry", "related-src", "RELATED_TO", "entry", "super-target-locked", reason="test")

        # deterministic: dead_ref (load-bearing missing path, no benign explanation)
        self._add_entry(con, "deadref-live", "Live broken ref", "Loader imports src/zz_missing_live_module.py during boot")

        # advisory: dead_ref_uncertain via history record
        self._add_entry(con, "deadref-history", "History record", "Issue fixed; the old src/zz_gone_history.py was retired")
        # advisory: dead_ref_uncertain via prose example
        self._add_entry(con, "deadref-prose", "Prose example", "Use a path like src/zz_example_prose.py for the handler")

        # advisory: oversized
        oversized = "\n\n".join(
            [
                "# Topic A\n- item one\n- item two\n- item three",
                "# Topic B\n- item four\n- item five\n- item six",
                "# Topic C\nThe body keeps going long enough to cross the small test threshold.",
                "Paragraph four with more operational detail.",
                "Paragraph five with another topic.",
            ]
        )
        self._add_entry(con, "oversized-entry", "Mixed oversized", oversized)

        # advisory: cross_layer_overlap_concern (same-name vnext card)
        self._add_entry(con, "vnext-existing-card", "Vnext Existing Card", "active source already has a same-name vnext card")
        self.cards.joinpath("vnext-existing-card.md").write_text(
            "---\ntitle: Vnext Existing Card\n---\n# Vnext Existing Card\n", encoding="utf-8"
        )

        # prune-self governance item must never be scanned
        self._add_entry(con, "prune-self-entry", "Prune self", "this governance item must not be scanned")

    # --- tests ---------------------------------------------------------------------
    def test_report_is_two_tier_with_expected_flags(self) -> None:
        report = self.run_scan()
        self.assertNotIn("groups", report)
        self.assertEqual(set(report["deterministic"]), {"relink_candidate", "active_superseded", "dead_ref"})
        self.assertEqual(
            set(report["advisory"]),
            {"duplicate", "oversized", "cross_layer_overlap_concern", "dead_ref_uncertain"},
        )
        self.assertEqual(report["schema_version"], "prune-scan-v2-two-tier")
        # promotion was cut entirely
        self.assertNotIn("promotion_candidate", report["deterministic"])
        self.assertNotIn("promotion_candidate", report["advisory"])

    def test_relink_age_gate(self) -> None:
        report = self.run_scan()
        candidates = self.det_ids(report, "relink_candidate", "candidates")
        self.assertIn("entry:relink-old", candidates)
        self.assertNotIn("entry:relink-fresh", self.det_ids(report, "relink_candidate"))
        # pinned aged orphan is locked, not an actionable candidate
        self.assertIn("entry:relink-locked-old", self.det_ids(report, "relink_candidate", "locked_review_only"))
        self.assertNotIn("entry:relink-locked-old", candidates)
        # unparseable created_at fails closed → never an actionable candidate
        self.assertNotIn("entry:relink-badtime", self.det_ids(report, "relink_candidate"))

    def test_active_superseded_supersedes_edge_is_signal_not_lock(self) -> None:
        report = self.run_scan()
        self.assertIn("entry:super-target", self.det_ids(report, "active_superseded", "candidates"))
        # a non-SUPERSEDES incoming edge still locks it for review
        self.assertIn("entry:super-target-locked", self.det_ids(report, "active_superseded", "locked_review_only"))
        self.assertNotIn("entry:super-target-locked", self.det_ids(report, "active_superseded", "candidates"))

    def test_dead_ref_three_exclusions(self) -> None:
        report = self.run_scan()
        self.assertIn("entry:deadref-live", self.det_ids(report, "dead_ref"))
        # history record and prose example are downgraded to advisory, never deterministic
        self.assertNotIn("entry:deadref-history", self.det_ids(report, "dead_ref"))
        self.assertNotIn("entry:deadref-prose", self.det_ids(report, "dead_ref"))
        self.assertIn("entry:deadref-history", self.adv_ids(report, "dead_ref_uncertain"))
        self.assertIn("entry:deadref-prose", self.adv_ids(report, "dead_ref_uncertain"))

    def test_advisory_flags_populated(self) -> None:
        report = self.run_scan()
        self.assertIn("entry:dup-a <-> entry:dup-b", self.adv_ids(report, "duplicate"))
        self.assertIn("entry:oversized-entry", self.adv_ids(report, "oversized"))
        self.assertIn("entry:vnext-existing-card", self.adv_ids(report, "cross_layer_overlap_concern"))

    def test_duplicate_denial_and_prune_self_exclusion(self) -> None:
        report = self.run_scan()
        dup = self.adv_ids(report, "duplicate")
        self.assertNotIn("entry:dup-kind-rule <-> entry:dup-kind-entry", dup)
        self.assertFalse(any("fact-subj" in item for item in dup))
        all_ids = "\n".join(
            r["item_id"]
            for group in (report["deterministic"], report["advisory"])
            for flag in group
            for r in (
                group[flag]["locked_review_only"] + group[flag]["candidates"]
                if isinstance(group[flag], dict)
                else group[flag]
            )
        )
        self.assertNotIn("prune-self-entry", all_ids)

    def test_preflight_not_enforced_for_tmp_db(self) -> None:
        report = self.run_scan()
        self.assertFalse(report["preflight"].get("enforced", True))

    def test_scan_does_not_mutate_database_bytes(self) -> None:
        before = self.db.read_bytes()
        self.run_scan()
        after = self.db.read_bytes()
        self.assertEqual(before, after)


class PrunePureHelperTests(unittest.TestCase):
    """In-process tests for branchy logic the subprocess e2e cannot reach hermetically."""

    @staticmethod
    def _decide(**kw):
        base = {"branch": "main", "status_ok": True, "dirty": [], "soft_dirty": [], "require_branch": "main", "allow_dirty": False}
        base.update(kw)
        return mem.prune_preflight_decision(**base)

    def test_preflight_decision_fail_closed(self) -> None:
        clean = self._decide()
        self.assertTrue(clean["clean"])
        self.assertFalse(clean["blocked"])
        # wrong branch / hard dirty / no branch all hard-block
        self.assertTrue(self._decide(branch="feature")["blocked"])
        self.assertTrue(self._decide(dirty=["M cc_memory_vnext/cards/x.md"])["blocked"])
        self.assertTrue(self._decide(branch=None)["blocked"])
        # B2: unreadable git status is fail-closed, even on main with no dirty
        self.assertTrue(self._decide(status_ok=False)["blocked"])
        # B3: a dirty memory.db is SOFT — it warns but does not block
        soft = self._decide(soft_dirty=["M cc_memory/memory.db"])
        self.assertFalse(soft["blocked"])
        self.assertTrue(soft["warnings"])
        # --allow-dirty overrides the hard block
        overridden = self._decide(branch="feature", dirty=["M x"], allow_dirty=True)
        self.assertFalse(overridden["blocked"])
        self.assertTrue(overridden["allow_dirty"])

    def test_parse_dirty_hard_soft_split(self) -> None:
        self.assertEqual(mem.prune_parse_dirty(False, "anything"), ([], []))
        text = "?? scratch.log\n M src/foo.py\nR  old.py -> new.py\n M cc_memory/memory.db\n"
        hard, soft = mem.prune_parse_dirty(True, text)
        self.assertIn("M src/foo.py", hard)
        self.assertTrue(any("new.py" in h for h in hard))  # rename keeps the new path
        self.assertFalse(any("scratch.log" in h for h in hard))  # untracked ignored
        self.assertTrue(any("memory.db" in s for s in soft))
        self.assertFalse(any("memory.db" in h for h in hard))

    def test_missing_paths_respect_repo_boundary(self) -> None:
        # absolute path outside the repo must not be treated as a missing in-repo ref
        self.assertEqual(mem.prune_missing_repo_paths("see C:/Windows/zz_nonexist_qq.txt now"), [])
        # a `..` escape is rejected (".." is not in the allowed first-component set)
        self.assertEqual(mem.prune_missing_repo_paths("see ../sub/zz_outside_qq.py now"), [])

    def test_path_is_externalized(self) -> None:
        for art in mem.PRUNE_EXTERNALIZED_ARTIFACTS:
            self.assertTrue(mem.prune_path_is_externalized(art))
            self.assertTrue(mem.prune_path_is_externalized("./" + art))
        self.assertFalse(mem.prune_path_is_externalized("src/some_other_file.py"))

    def test_node_age_days(self) -> None:
        ref = mem.prune_parse_ts("2026-01-10T00:00:00Z")
        self.assertEqual(mem.prune_node_age_days({"created_at": "2026-01-01T00:00:00Z"}, ref), 9)
        self.assertIsNone(mem.prune_node_age_days({"created_at": "not-a-date"}, ref))

    def _craft_node(self, node_id: str, body: str, **kw) -> dict:
        return {
            "type": "entry",
            "id": node_id,
            "ref": f"entry:{node_id}",
            "row": None,
            "title": kw.get("title", ""),
            "body": body,
            "text": body,
            "status": "active",
            "kind": kw.get("kind", "entry"),
            "confidence": kw.get("confidence", "medium"),
            "pinned": kw.get("pinned", False),
            "subject": "",
            "created_at": kw.get("created_at", mem.now()),
            "body_bytes": len(body.encode("utf-8")),
        }

    def test_dead_ref_externalized_downgrade(self) -> None:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        mem.init_schema(con)
        saved = mem.PRUNE_EXTERNALIZED_ARTIFACTS
        mem.PRUNE_EXTERNALIZED_ARTIFACTS = ("data/preprocessed/zz_external_missing.json",)
        try:
            node = self._craft_node("ext-node", "Resume reads data/preprocessed/zz_external_missing.json on boot")
            deterministic, advisory = mem.prune_dead_ref_records(con, [node])
            self.assertEqual(deterministic, [])
            self.assertEqual(len(advisory), 1)
            self.assertEqual(advisory[0]["flag"], "dead_ref_uncertain")
            self.assertIn("externalized", advisory[0]["signals"][0])
        finally:
            mem.PRUNE_EXTERNALIZED_ARTIFACTS = saved
            con.close()


if __name__ == "__main__":
    unittest.main()
