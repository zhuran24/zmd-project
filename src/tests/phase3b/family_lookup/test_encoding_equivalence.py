from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.family_lookup.encoding_equivalence as audit_module
from src.search.phase3b.family_lookup.encoding_equivalence import (
    build_family_lookup_relation_equivalence_report,
    build_phase3b_family_lookup_encoding_equivalence,
    render_phase3b_family_lookup_encoding_equivalence_markdown,
    render_phase3b_family_lookup_encoding_equivalence_text,
)


class _FakeDelegate:
    def __init__(self) -> None:
        self._power_pole_use_shell_lookup = True
        self._power_pole_family_name_by_int = {0: "family_000", 1: "family_001"}
        self._power_pole_shell_lookup_rows = [
            (0, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (2, 3, 1),
        ]
        self._power_pole_family_tuple_rows = []


class _FakeModel:
    def __init__(self) -> None:
        self._coordinate_delegate = _FakeDelegate()
        self.build_stats = {
            "power_family_lookup_encoding": {
                "encoding": "table",
                "table_constraint_count": 2,
            },
            "power_pole_shell_distance_encoding": {"encoding": "element"},
            "power_pole_shell_lookup_pairs": {"pair_count": 4},
            "master_domain_table_rows": 0,
            "power_coverage": {"witness_encoding": {"encoding": "element"}},
        }


def test_relation_equivalence_accepts_linear_guards_and_shell_pair_index() -> None:
    report = build_family_lookup_relation_equivalence_report(
        shell_lookup_rows=[
            (0, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (2, 3, 1),
        ],
        family_name_by_int={0: "family_000", 1: "family_001"},
    )

    assert report["use_shell_lookup"] is True
    assert report["shell_lookup_row_count"] == 4
    assert report["linear_shell_guards"]["equivalent"] is True
    assert report["linear_shell_guards"]["shape_counts"] == {
        "single": 1,
        "upper_triangle": 1,
    }
    assert report["shell_pair_index"]["equivalent"] is True
    assert report["shell_pair_index"]["pair_count"] == 4
    assert report["sentinel"]["active_relation_excludes_sentinel"] is True


def test_relation_equivalence_detects_shell_pair_conflicts() -> None:
    report = build_family_lookup_relation_equivalence_report(
        shell_lookup_rows=[
            (0, 0, 0),
            (0, 0, 1),
        ],
        family_name_by_int={0: "family_000", 1: "family_001"},
    )

    assert report["linear_shell_guards"]["equivalent"] is True
    assert report["shell_pair_index"]["equivalent"] is False
    assert report["shell_pair_index"]["pair_conflict_count"] == 1


def test_relation_equivalence_skips_full_tuple_fallback() -> None:
    report = build_family_lookup_relation_equivalence_report(
        shell_lookup_rows=[],
        family_name_by_int={0: "family_000"},
        use_shell_lookup=False,
        family_tuple_rows=[(0, 0, 0, 0)],
    )

    assert report["use_shell_lookup"] is False
    assert report["status"] == "skipped"
    assert report["skip_reason"] == "full_pose_tuple_fallback"
    assert report["family_tuple_row_count"] == 1


def test_family_lookup_encoding_equivalence_builds_no_solve_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (_FakeModel(), SimpleNamespace()),
    )

    report = build_phase3b_family_lookup_encoding_equivalence(
        tmp_path / "project",
        candidate="67x13",
    )

    assert report["metadata"]["source"] == "phase3b_family_lookup_encoding_equivalence_v1"
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["candidate_elimination_claim"] is False
    assert report["status"]["outcome"] == "relations_equivalent"
    assert report["relation_equivalence"]["linear_shell_guards"]["equivalent"] is True
    assert report["relation_equivalence"]["shell_pair_index"]["equivalent"] is True
    assert _check_status(report, "solver_not_invoked") == "pass"
    assert _check_status(report, "linear_shell_guards_relation_equivalent") == "pass"
    assert "Family Lookup Encoding Equivalence" in (
        render_phase3b_family_lookup_encoding_equivalence_markdown(report)
    )
    assert "solver_invoked=false" in (
        render_phase3b_family_lookup_encoding_equivalence_text(report)
    )


def test_family_lookup_encoding_equivalence_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "family_lookup" / "build_encoding_equivalence.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family lookup encoding equivalence" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_lookup_encoding_equivalence_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_lookup_encoding_equivalence.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_family_lookup_encoding_equivalence_v1"
    assert payload["metadata"]["solver_invoked"] is False
    assert (output_dir / "family_lookup_encoding_equivalence.md").exists()
    assert (output_dir / "family_lookup_encoding_equivalence.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return check.get("status")
    raise AssertionError(f"check not found: {check_id}")
