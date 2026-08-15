from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from devtools import document_patch_landing as landing


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_DIR = PROJECT_ROOT / "data/repository_governance/document_system"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def _git(root: Path, *args: str) -> bytes:
    return _run(root, "git", *args).stdout


def _write(root: Path, relpath: str, text: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(root: Path, message: str, *paths: str) -> str:
    if paths:
        _git(root, "add", "--", *paths)
    _run(
        root,
        "git",
        "-c",
        "user.name=Landing Test",
        "-c",
        "user.email=landing@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _git(root, "rev-parse", "HEAD").decode().strip()


def _baseline_files(root: Path) -> None:
    _write(root, "README.md", "baseline readme\n")
    _write(root, "CLAUDE.md", "baseline overlay\n")
    _write(root, "docs/项目说明/00_master_roadmap.md", "baseline roadmap\n")
    _write(root, "docs/项目说明/27_status_dashboard.md", "baseline dashboard\n")
    _write(root, "docs/AGENT_OPERATIONS.md", "informational_record_only\n.Codex/\n")
    _write(root, "docs/项目说明/HISTORY.md", "history baseline\n")
    _write(root, "docs/项目说明/ROADMAP.md", "roadmap baseline\n")
    _write(root, "data/knowledge/decisions.jsonl", '{"id":"baseline"}\n')
    _write(root, "data/knowledge/claims.jsonl", "")
    _write(root, "data/knowledge/backfill_triage.json", "{}\n")


def _init_repository(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "switch", "-q", "-c", "landing/test")
    _git(root, "add", ".")
    _commit(root, "supplier baseline")


def _fixture_repository(tmp_path: Path) -> tuple[Path, Path, Path]:
    supplier = tmp_path / "supplier"
    supplier.mkdir(parents=True)
    _baseline_files(supplier)

    patch_repo = tmp_path / "patch-repo"
    shutil.copytree(supplier, patch_repo)
    _init_repository(patch_repo)
    _write(patch_repo, "README.md", "patched readme\n")
    _write(patch_repo, "CLAUDE.md", "canonical package overlay, intentionally excluded\n")
    _write(patch_repo, "docs/项目说明/00_master_roadmap.md", "canonical roadmap successor\n")
    _write(patch_repo, "docs/项目说明/27_status_dashboard.md", "canonical dashboard successor\n")
    patch = tmp_path / "cumulative.patch"
    patch.write_bytes(_git(patch_repo, "diff", "--binary", "--full-index"))

    root = tmp_path / "repo"
    shutil.copytree(supplier, root)
    _init_repository(root)
    _git(root, "rm", "--cached", "CLAUDE.md")
    _commit(root, "real topology overlay")
    with (root / "CLAUDE.md").open("a", encoding="utf-8") as handle:
        handle.write("local overlay drift\n")
    with (root / "docs/项目说明/00_master_roadmap.md").open("a", encoding="utf-8") as handle:
        handle.write("owner decision drift\n")
    with (root / "docs/项目说明/27_status_dashboard.md").open("a", encoding="utf-8") as handle:
        handle.write("A12 and A13 drift\n")
    _commit(
        root,
        "post-snapshot owner and debt drift",
        "docs/项目说明/00_master_roadmap.md",
        "docs/项目说明/27_status_dashboard.md",
    )
    return root, patch, supplier


def _create_plan(root: Path, patch: Path, supplier: Path, output: Path, landing_id: str) -> Path:
    return landing.create_plan(
        root=root,
        patch=patch,
        output=output,
        protocol_arg=PROTOCOL_DIR / "landing.json",
        protocol_schema_arg=PROTOCOL_DIR / "landing.schema.json",
        ack_schema_arg=PROTOCOL_DIR / "landing_ack.schema.json",
        baseline_root=supplier,
        landing_id=landing_id,
    )


def _commit_base_and_confirm(root: Path, plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    landing.apply_base(root=root, plan_path=plan_path)
    _commit(root, "base patch", *plan["base_apply_paths"])
    landing.confirm_base(root=root, plan_path=plan_path)


def _install_protocol(root: Path) -> None:
    paths: list[str] = []
    for name in ("landing.json", "landing.schema.json", "landing_ack.schema.json"):
        relpath = f"data/repository_governance/document_system/{name}"
        destination = root / relpath
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROTOCOL_DIR / name, destination)
        paths.append(relpath)
    _commit(root, "install landing adaptation", *paths)


def _prepare_migration(tmp_path: Path, landing_id: str = "fixture-landing") -> tuple[Path, Path, Path]:
    root, patch, supplier = _fixture_repository(tmp_path)
    plan_path = _create_plan(root, patch, supplier, tmp_path / "plan", landing_id)
    _commit_base_and_confirm(root, plan_path)
    _install_protocol(root)
    landing.begin_migration(root=root, plan_path=plan_path, landing_date="2026-08-14")
    return root, plan_path, plan_path.parent


def _fill_ack(root: Path, plan_dir: Path) -> Path:
    ack_path = plan_dir / "MIGRATION_ACK.json"
    ack = json.loads(ack_path.read_text(encoding="utf-8"))
    records = {record["source_path"]: record for record in ack["records"]}

    (root / "CLAUDE.md").write_text(
        "2026-08-09 blank rebuild\n"
        "/home/zhuran24/zmd-pj-cc-backup-20260809/\n"
        "CLAUDE.md and AGENTS.md are untracked workspace overlays\n",
        encoding="utf-8",
    )

    roadmap_record = records["docs/项目说明/00_master_roadmap.md"]
    roadmap_archive = roadmap_record["archive_path"]
    roadmap_sha = roadmap_record["source_sha256"]
    decision_id = "DECISION-LANDING-OWNER-001"
    with (root / "data/knowledge/decisions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "id": decision_id,
                    "summary": "owner decision drift",
                    "archive": roadmap_archive,
                    "source_sha256": roadmap_sha,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    with (root / "docs/项目说明/HISTORY.md").open("a", encoding="utf-8") as handle:
        handle.write(
            f"owner decision drift migrated from {roadmap_archive} sha256 {roadmap_sha}\n"
        )
    roadmap_obligations = {value["id"]: value for value in roadmap_record["obligations"]}
    roadmap_obligations["owner-decision-register"]["record_ids"] = [decision_id]
    roadmap_obligations["owner-decision-register"]["required_strings"] = ["owner decision drift"]
    roadmap_obligations["owner-history-event"]["required_strings"] = ["owner decision drift"]

    dashboard_record = records["docs/项目说明/27_status_dashboard.md"]
    dashboard_archive = dashboard_record["archive_path"]
    dashboard_sha = dashboard_record["source_sha256"]
    with (root / "docs/项目说明/ROADMAP.md").open("a", encoding="utf-8") as handle:
        handle.write(
            f"A12 and A13 drift migrated from {dashboard_archive} sha256 {dashboard_sha}\n"
        )
    for obligation in dashboard_record["obligations"]:
        obligation["required_strings"] = ["A12 and A13 drift"]

    ack_path.write_text(json.dumps(ack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ack_path


def test_dynamic_landing_bootstraps_externally_and_finalizes_sealed_successors(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_path = _create_plan(root, patch, supplier, plan_dir, "fixture-landing")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["status"] == "READY"
    assert set(plan["drift_paths"]) == {
        "CLAUDE.md",
        "docs/项目说明/00_master_roadmap.md",
        "docs/项目说明/27_status_dashboard.md",
    }
    assert plan["workspace_collision_paths"] == ["CLAUDE.md"]
    assert not (root / landing.DEFAULT_PROTOCOL).exists()
    original_drift = {path: (root / path).read_bytes() for path in plan["drift_paths"]}

    _commit_base_and_confirm(root, plan_path)
    assert (root / "README.md").read_text(encoding="utf-8") == "patched readme\n"
    for path, value in original_drift.items():
        assert (root / path).read_bytes() == value

    with pytest.raises(landing.LandingError, match="cannot read strict JSON"):
        landing.begin_migration(root=root, plan_path=plan_path, landing_date="2026-08-14")
    _install_protocol(root)
    landing.begin_migration(root=root, plan_path=plan_path, landing_date="2026-08-14")
    ack_path = _fill_ack(root, plan_dir)
    receipt = landing.verify_migration(root=root, plan_path=plan_path, ack_path=ack_path)
    assert receipt["kind"] == "migration_verify_pre_finalize"

    final_receipt_path = landing.finalize_migration(root=root, plan_path=plan_path, ack_path=ack_path)
    final_receipt = json.loads(final_receipt_path.read_text(encoding="utf-8"))
    assert final_receipt["successor_source"] == "sealed_plan_package_successors"
    assert (root / "docs/项目说明/00_master_roadmap.md").read_text(encoding="utf-8") == (
        "canonical roadmap successor\n"
    )
    assert (root / "docs/项目说明/27_status_dashboard.md").read_text(encoding="utf-8") == (
        "canonical dashboard successor\n"
    )
    assert "untracked workspace overlays" in (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "CLAUDE.md" not in final_receipt["migration_changed_paths"]
    for path, value in original_drift.items():
        archive = root / "docs/history/status/landing/2026-08-14/fixture-landing" / path
        assert archive.read_bytes() == value


def test_non_conflicting_content_drift_is_discovered_and_blocks_when_unknown(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    with (root / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("locally appended but patch-compatible drift\n")
    plan_path = _create_plan(root, patch, supplier, tmp_path / "plan", "silent-drift")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert "README.md" in plan["content_drift_paths"]
    assert "README.md" in plan["unknown_drift_paths"]
    assert plan["status"] == "BLOCKED"
    with pytest.raises(landing.LandingError, match="unknown or unsupported drift"):
        landing.apply_base(root=root, plan_path=plan_path)


def test_unknown_untracked_patch_collision_blocks(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    extra_repo = tmp_path / "extra-repo"
    shutil.copytree(supplier, extra_repo)
    _init_repository(extra_repo)
    _write(extra_repo, "unknown.md", "baseline unknown\n")
    _commit(extra_repo, "unknown baseline", "unknown.md")
    unknown_supplier = tmp_path / "supplier-plus"
    shutil.copytree(supplier, unknown_supplier)
    _write(unknown_supplier, "unknown.md", "baseline unknown\n")
    _write(extra_repo, "unknown.md", "canonical unknown\n")
    extra = _git(extra_repo, "diff", "--binary", "--full-index", "--", "unknown.md")
    combined = tmp_path / "combined.patch"
    combined.write_bytes(patch.read_bytes() + extra)
    _write(root, "unknown.md", "baseline unknown\n")

    plan_path = _create_plan(root, combined, unknown_supplier, tmp_path / "plan", "unknown-untracked")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["status"] == "BLOCKED"
    assert "unknown.md" in plan["workspace_collision_paths"]
    assert "unknown.md" in plan["unknown_drift_paths"]


def test_plan_refuses_default_branch_repository_output_and_missing_baseline(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    _git(root, "branch", "-m", "main")
    with pytest.raises(landing.LandingError, match="dedicated branch"):
        _create_plan(root, patch, supplier, tmp_path / "plan-main", "main")
    _git(root, "branch", "-m", "landing/test")
    with pytest.raises(landing.LandingError, match="outside the repository"):
        _create_plan(root, patch, supplier, root / ".landing-plan", "inside")
    with pytest.raises(landing.LandingError, match="requires --baseline-root"):
        landing.create_plan(
            root=root,
            patch=patch,
            output=tmp_path / "missing-baseline",
            protocol_arg=PROTOCOL_DIR / "landing.json",
            protocol_schema_arg=PROTOCOL_DIR / "landing.schema.json",
            ack_schema_arg=PROTOCOL_DIR / "landing_ack.schema.json",
            baseline_root=None,
            landing_id="missing-baseline",
        )


def test_planned_git_state_or_snapshot_change_is_rejected(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    plan_path = _create_plan(root, patch, supplier, tmp_path / "plan", "state-change")
    with (root / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("concurrent tracked edit\n")
    with pytest.raises(landing.LandingError, match="state changed"):
        landing.apply_base(root=root, plan_path=plan_path)

    root2, patch2, supplier2 = _fixture_repository(tmp_path / "second")
    plan2 = _create_plan(root2, patch2, supplier2, tmp_path / "plan2", "snapshot-change")
    plan_value = json.loads(plan2.read_text(encoding="utf-8"))
    snapshot = plan2.parent / plan_value["drift_records"][0]["snapshot_path"]
    snapshot.write_bytes(b"tampered\n")
    with pytest.raises(landing.LandingError, match="drift snapshot changed"):
        landing.apply_base(root=root2, plan_path=plan2)


def test_confirm_base_requires_one_exact_commit(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    plan_path = _create_plan(root, patch, supplier, tmp_path / "plan", "confirm")
    landing.apply_base(root=root, plan_path=plan_path)
    with pytest.raises(landing.LandingError, match="exactly one immediate commit"):
        landing.confirm_base(root=root, plan_path=plan_path)
    _write(root, "extra.txt", "extra\n")
    _commit(root, "base plus extra", "README.md", "extra.txt")
    with pytest.raises(landing.LandingError, match="path set differs"):
        landing.confirm_base(root=root, plan_path=plan_path)


def test_append_only_rewrite_is_rejected(tmp_path: Path) -> None:
    root, plan_path, plan_dir = _prepare_migration(tmp_path, "append-only")
    ack_path = _fill_ack(root, plan_dir)
    (root / "data/knowledge/decisions.jsonl").write_text("rewritten\n", encoding="utf-8")
    with pytest.raises(landing.LandingError, match="rewrote existing bytes"):
        landing.verify_migration(root=root, plan_path=plan_path, ack_path=ack_path)


def test_ack_strings_must_come_from_archive_and_share_jsonl_record(tmp_path: Path) -> None:
    root, plan_path, plan_dir = _prepare_migration(tmp_path, "ack-proof")
    ack_path = _fill_ack(root, plan_dir)
    ack = json.loads(ack_path.read_text(encoding="utf-8"))
    roadmap = next(record for record in ack["records"] if record["source_path"].endswith("00_master_roadmap.md"))
    decision = next(value for value in roadmap["obligations"] if value["id"] == "owner-decision-register")
    decision["required_strings"] = ["not present in archived source"]
    ack_path.write_text(json.dumps(ack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(landing.LandingError, match="not present in the archived source"):
        landing.verify_migration(root=root, plan_path=plan_path, ack_path=ack_path)

    decision["required_strings"] = ["owner decision drift"]
    ack_path.write_text(json.dumps(ack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = (root / "data/knowledge/decisions.jsonl").read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    record.pop("archive")
    lines[-1] = json.dumps(record, ensure_ascii=False)
    with (root / "data/knowledge/decisions.jsonl").open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.write(json.dumps({"id": "other", "archive": roadmap["archive_path"]}, ensure_ascii=False) + "\n")
    with pytest.raises(landing.LandingError, match="JSONL record .* lacks marker"):
        landing.verify_migration(root=root, plan_path=plan_path, ack_path=ack_path)


def test_finalize_prevalidates_sealed_successors_before_replacing_any_source(tmp_path: Path) -> None:
    root, plan_path, plan_dir = _prepare_migration(tmp_path, "prevalidate-successors")
    ack_path = _fill_ack(root, plan_dir)
    landing.verify_migration(root=root, plan_path=plan_path, ack_path=ack_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    dashboard = next(
        record for record in plan["successor_records"]
        if record["path"] == "docs/项目说明/27_status_dashboard.md"
    )
    (plan_dir / dashboard["snapshot_path"]).unlink()
    roadmap = root / "docs/项目说明/00_master_roadmap.md"
    original_roadmap = roadmap.read_bytes()
    with pytest.raises(landing.LandingError, match="package successor snapshot is missing"):
        landing.finalize_migration(root=root, plan_path=plan_path, ack_path=ack_path)
    assert roadmap.read_bytes() == original_roadmap


def test_begin_refuses_uncommitted_or_mismatched_installed_protocol(tmp_path: Path) -> None:
    root, patch, supplier = _fixture_repository(tmp_path)
    plan_path = _create_plan(root, patch, supplier, tmp_path / "plan", "protocol-commit")
    _commit_base_and_confirm(root, plan_path)
    for name in ("landing.json", "landing.schema.json", "landing_ack.schema.json"):
        target = root / "data/repository_governance/document_system" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROTOCOL_DIR / name, target)
    with pytest.raises(landing.LandingError, match="not Git-tracked"):
        landing.begin_migration(root=root, plan_path=plan_path, landing_date="2026-08-14")
