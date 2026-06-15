from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from cc_context.memory_system.cli import main as cli_main
from cc_context.memory_system.freshness import check_freshness, save_store, scan
from cc_context.memory_system.graph import build_graph


def write_node(path: Path, name: str, idx: str, desc: str, body: str, typ: str = "feedback") -> None:
    path.write_text(
        f"""---
name: {name}
index_summary: "{idx}"
description: "{desc}"
metadata:
  type: {typ}
---
{body}
""",
        encoding="utf-8",
        newline="\n",
    )


def write_raw(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


class MemorySystemTests(unittest.TestCase):
    def test_bootstrap_command_prints_startup_card(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            (mem / "MEMORY.md").write_text("- [Fact A](fact_a.md) — A\n", encoding="utf-8", newline="\n")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = cli_main(["--mem-dir", str(mem), "--graph-dir", str(graph_dir), "bootstrap"])

            output = stdout.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("# 新会话记忆启动卡", output)
            self.assertIn("状态: OK", output)
            self.assertIn("fact-a", output)

    def test_fact_evidence_creates_hard_dependency_and_impact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "> 事实依据: [[fact-a]]\nBody\n")
            graph = build_graph(mem, graph_dir)
            hard = [e for e in graph.edges if e.source == "entry-b" and e.target == "fact-a" and e.type == "DEPENDS_ON"]
            self.assertEqual(len(hard), 1)
            self.assertEqual(hard[0].line, 8)
            impacted = graph.reverse_dependents("fact-a")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_see_also_fact_link_is_soft(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "相关: [[fact-a]]\n")
            graph = build_graph(mem, graph_dir)
            edges = [e for e in graph.edges if e.source == "entry-b" and e.target == "fact-a"]
            self.assertEqual([(e.type, e.hard) for e in edges], [("MENTIONS", False)])
            self.assertEqual(graph.reverse_dependents("fact-a"), [])

    def test_see_also_word_with_dependency_language_stays_hard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "相关事实 [[fact-a]] 改了本条要跟着改\n")
            graph = build_graph(mem, graph_dir)
            edges = [e for e in graph.edges if e.source == "entry-b" and e.target == "fact-a"]
            self.assertEqual([(e.type, e.hard) for e in edges], [("DEPENDS_ON", True)])
            impacted = graph.reverse_dependents("fact-a")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_non_fact_prefix_fact_link_still_impacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "policy_core.md", "policy-core", "A", "Fact A", "## Fact\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "Body [[policy-core]]\n")
            graph = build_graph(mem, graph_dir)
            impacted = graph.reverse_dependents("policy-core")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_related_to_edge_type_text_is_not_see_also(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "RELATED_TO edge semantics use [[fact-a]]\n")
            graph = build_graph(mem, graph_dir)
            impacted = graph.reverse_dependents("fact-a")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_fact_projection_backlink_creates_entry_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## 首批投影\n- [[entry-b]] — projection\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "Body\n")
            graph = build_graph(mem, graph_dir)
            impacted = graph.reverse_dependents("fact-a")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_projection_backlink_only_inside_projection_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(
                mem / "fact_a.md",
                "fact-a",
                "A",
                "Fact A",
                "正文提到投影 [[entry-a]] 但不是投影段列表项\n\n## 首批投影\n1. 前缀文字 [[entry-b]]\n",
                typ="fact",
            )
            write_node(mem / "entry_a.md", "entry-a", "A", "Entry A", "Body\n")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "Body\n")
            graph = build_graph(mem, graph_dir)
            impacted = graph.reverse_dependents("fact-a")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_frontmatter_inline_map_depends_on_and_related_to(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_raw(
                mem / "policy_core.md",
                """---
name: policy-core
index_summary: Index # stripped
description: "Desc # kept"
metadata: {type: fact}
---
Body
""",
            )
            write_raw(
                mem / "entry_dep.md",
                """---
name: entry-dep
index_summary: Dep
description: Dep
depends_on: [policy-core] # inline list
metadata:
  type: feedback
---
Body
""",
            )
            write_raw(
                mem / "entry_rel.md",
                """---
name: entry-rel
index_summary: Rel
description: Rel
related_to: [policy-core]
metadata:
  type: feedback
---
Body [[policy-core]]
""",
            )
            graph = build_graph(mem, graph_dir)
            self.assertTrue(graph.nodes["policy-core"].is_fact)
            self.assertEqual(graph.nodes["policy-core"].index_summary, "Index")
            self.assertEqual(graph.nodes["policy-core"].description, "Desc # kept")
            depends = [e for e in graph.edges if e.source == "entry-dep" and e.target == "policy-core"]
            self.assertEqual([(e.type, e.origin, e.line) for e in depends], [("DEPENDS_ON", "frontmatter", 5)])
            impacted = graph.reverse_dependents("policy-core")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-dep"])
            related = [e for e in graph.edges if e.source == "entry-rel" and e.target == "policy-core"]
            self.assertEqual([(e.type, e.origin) for e in related], [("RELATED_TO", "frontmatter")])

    def test_overlay_does_not_downgrade_frontmatter_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            write_raw(
                mem / "entry_b.md",
                """---
name: entry-b
index_summary: B
description: Entry B
depends_on: [fact-a]
metadata:
  type: feedback
---
Body
""",
            )
            (graph_dir / "edges.jsonl").write_text(
                '{"from":"entry-b","to":"fact-a","type":"MENTIONS","reason":"too weak"}\n',
                encoding="utf-8",
                newline="\n",
            )
            graph = build_graph(mem, graph_dir)
            edge = [e for e in graph.edges if e.source == "entry-b" and e.target == "fact-a"]
            self.assertEqual([(e.type, e.origin) for e in edge], [("DEPENDS_ON", "frontmatter")])
            impacted = graph.reverse_dependents("fact-a")
            self.assertEqual([node.id for _, _, node in impacted], ["entry-b"])

    def test_overlay_can_downgrade_inferred_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "fact_a.md", "fact-a", "A", "Fact A", "## Fact\n", typ="fact")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "Body [[fact-a]]\n")
            (graph_dir / "edges.jsonl").write_text(
                '{"from":"entry-b","to":"fact-a","type":"MENTIONS","reason":"manual downgrade"}\n',
                encoding="utf-8",
                newline="\n",
            )
            graph = build_graph(mem, graph_dir)
            edge = [e for e in graph.edges if e.source == "entry-b" and e.target == "fact-a"]
            self.assertEqual([(e.type, e.origin) for e in edge], [("MENTIONS", "overlay")])
            self.assertEqual(graph.reverse_dependents("fact-a"), [])

    def test_invalid_overlay_lines_report_errors_without_fake_edges(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "entry_a.md", "entry-a", "A", "Entry A", "Body\n")
            (graph_dir / "edges.jsonl").write_text(
                '{"from": "entry-a", "to": "missing", "type": "NOPE"}\n{bad json\n',
                encoding="utf-8",
                newline="\n",
            )
            graph = build_graph(mem, graph_dir)
            report = graph.validate(check_memory_cap=False, check_live_mirror=False)
            self.assertFalse(any(e.type == "INVALID" for e in graph.edges))
            self.assertIn("unknown overlay edge type", "\n".join(report.errors))
            self.assertIn("invalid overlay JSON", "\n".join(report.errors))
            self.assertEqual(report.stats["edges"], 0)

    def test_hard_edge_type_cycle_detection_matches_impact_predicate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            graph_dir = root / "memory_graph"
            mem.mkdir()
            graph_dir.mkdir()
            write_node(mem / "entry_a.md", "entry-a", "A", "Entry A", "Body\n")
            write_node(mem / "entry_b.md", "entry-b", "B", "Entry B", "Body\n")
            (graph_dir / "edges.jsonl").write_text(
                "\n".join([
                    '{"from":"entry-a","to":"entry-b","type":"SUPERSEDES","hard":false}',
                    '{"from":"entry-b","to":"entry-a","type":"SUPERSEDES","hard":false}',
                ])
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            graph = build_graph(mem, graph_dir)
            report = graph.validate(check_memory_cap=False, check_live_mirror=False)
            self.assertIn("hard dependency cycle", "\n".join(report.errors))

    def test_freshness_body_drift_blocks_even_if_summary_changed_once(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            store = root / "description_review.json"
            mem.mkdir()
            write_node(mem / "entry.md", "entry", "one", "desc one", "body one\n")
            baseline = scan(mem)
            save_store(store, baseline)
            write_node(mem / "entry.md", "entry", "two", "desc two", "body two\n")
            rc, lines = check_freshness(mem, store)
            self.assertEqual(rc, 1)
            self.assertIn("DIRTY entry", "\n".join(lines))

    def test_freshness_deleted_node_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            store = root / "description_review.json"
            mem.mkdir()
            write_node(mem / "entry.md", "entry", "one", "desc one", "body one\n")
            save_store(store, scan(mem))
            (mem / "entry.md").unlink()
            rc, lines = check_freshness(mem, store)
            self.assertEqual(rc, 1)
            self.assertIn("GONE  entry", "\n".join(lines))

    def test_freshness_summary_only_change_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            store = root / "description_review.json"
            mem.mkdir()
            write_node(mem / "entry.md", "entry", "one", "desc one", "body one\n")
            save_store(store, scan(mem))
            write_node(mem / "entry.md", "entry", "two", "desc two", "body one\n")
            rc, lines = check_freshness(mem, store)
            self.assertEqual(rc, 1)
            joined = "\n".join(lines)
            self.assertIn("DIRTY entry: summary metadata changed", joined)
            self.assertIn("description", joined)
            self.assertIn("index_summary", joined)


if __name__ == "__main__":
    unittest.main()
