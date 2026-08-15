from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from devtools import document_governance_gate as gate


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_outer_governance_scratch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nested gate tests must not inherit the caller gate's scratch root."""

    monkeypatch.delenv("ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT", raising=False)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.DEVNULL)


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / ".gitignore").write_text(".ignored/\n", encoding="utf-8")
    (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "tracked.txt")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Document Gate Test",
            "-c",
            "user.email=document-gate@example.invalid",
            "commit",
            "-q",
            "-m",
            "baseline",
        ],
        cwd=root,
        check=True,
    )
    return root


def _lane(
    lane_id: str,
    command: list[str],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    return {
        "id": lane_id,
        "description": f"fixture lane {lane_id}",
        "command": command,
        "timeout_seconds": timeout_seconds,
        "base_argument": None,
        "required_paths": [],
        "environment": {},
        "isolation": "process_tempdir",
        "mutation_policy": "read_only",
    }


def _config(*lanes: dict[str, Any], max_parallel_lanes: int = 2) -> dict[str, Any]:
    return {
        "schema_version": "zmd_document_governance_gate_v2",
        "system_version": "2.6.0",
        "fingerprint": {
            "version": "git_declared_state_v2",
            "hash_algorithm": "sha256",
            "index": "included",
            "tracked_worktree": "modified_deleted_and_mode_state",
            "workspace_inputs": "manifest_declared_overlays_only",
            "arbitrary_untracked": "excluded",
            "ignored": "excluded",
        },
        "runner": {
            "default_profile": "changed",
            "max_parallel_lanes": max_parallel_lanes,
            "lane_isolation": "process_plus_unique_external_tempdir",
            "mutation_policy": "git_visible_state_must_be_identical",
        },
        "profiles": {
            "changed": {
                "description": "fixture profile",
                "requires_base": False,
                "lane_ids": [str(lane["id"]) for lane in lanes],
            }
        },
        "lanes": list(lanes),
    }


def test_real_gate_registry_validates_and_separates_current_from_history() -> None:
    manifest, config = gate.load_gate_configuration(PROJECT_ROOT)

    assert manifest["schema_version"] == "zmd_document_system_manifest_v7"
    assert manifest["system_version"] == "2.6.0"
    assert config["system_version"] == "2.6.0"
    assert config["runner"]["default_profile"] == "changed"
    assert config["runner"]["max_parallel_lanes"] == 4
    landing_lane = next(
        lane for lane in config["lanes"] if lane["id"] == "document_landing_regressions"
    )
    assert landing_lane["timeout_seconds"] == 300

    changed = set(config["profiles"]["changed"]["lane_ids"])
    full = set(config["profiles"]["full"]["lane_ids"])
    weekly = set(config["profiles"]["weekly"]["lane_ids"])
    framework = set(config["profiles"]["framework"]["lane_ids"])
    historical = set(config["profiles"]["historical_replay"]["lane_ids"])
    assert "code_assets_current" in changed
    for selected in (changed, full, weekly, framework):
        assert "code_assets_history" not in selected
    assert historical == {"code_assets_history"}
    assert "docsystem_changed" in changed
    assert "docsystem_changed" not in weekly
    assert "document_intake" in changed
    assert "document_intake" in full
    assert "document_intake" not in weekly
    for selected in (changed, full, weekly):
        assert "maintenance_audit" in selected
    for selected in (changed, full, weekly, framework):
        assert "document_landing_regressions" in selected
    assert "maintenance_audit" not in framework
    for selected in (changed, full, weekly, framework):
        assert "document_intake_regressions" in selected
        assert "maintenance_audit_regressions" in selected


def test_gate_loader_rejects_manifest_selected_schema_path(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = root / ".docsystem/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"manifest_schema": "data/relaxed.schema.json"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(gate.GovernanceGateError, match="code-pinned schema path"):
        gate.load_gate_configuration(root)


def test_gate_semantics_rejects_a_registered_write_mode() -> None:
    manifest, config = gate.load_gate_configuration(PROJECT_ROOT)
    invalid = copy.deepcopy(config)
    invalid["lanes"][0]["command"].append("--write")

    with pytest.raises(gate.GovernanceGateError, match="write-capable token"):
        gate._validate_gate_semantics(PROJECT_ROOT, manifest, invalid)


def test_gate_semantics_rejects_runner_environment_override() -> None:
    manifest, config = gate.load_gate_configuration(PROJECT_ROOT)
    invalid = copy.deepcopy(config)
    invalid["lanes"][0]["environment"]["TMPDIR"] = "{repo}/.tmp"

    with pytest.raises(gate.GovernanceGateError, match="runner-owned environment: TMPDIR"):
        gate._validate_gate_semantics(PROJECT_ROOT, manifest, invalid)


def test_git_visible_fingerprint_is_stable_and_excludes_ignored_paths(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    before = gate.capture_git_visible_state(root)

    ignored = root / ".ignored/cache.bin"
    ignored.parent.mkdir()
    ignored.write_bytes(b"cache")
    after = gate.capture_git_visible_state(root)

    assert before == after
    assert gate.compare_git_visible_states(before, after) == ()


@pytest.mark.parametrize("mutation", ["worktree", "index", "delete"])
def test_git_visible_fingerprint_detects_every_repository_visible_mutation(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _repository(tmp_path)
    before = gate.capture_git_visible_state(root)

    if mutation == "worktree":
        (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
    elif mutation == "index":
        (root / "tracked.txt").write_text("staged\n", encoding="utf-8")
        _git(root, "add", "tracked.txt")
    elif mutation == "delete":
        (root / "tracked.txt").unlink()
    else:  # pragma: no cover - parameter list is closed above
        raise AssertionError(mutation)

    after = gate.capture_git_visible_state(root)
    changes = gate.compare_git_visible_states(before, after)

    assert before.digest != after.digest
    assert changes


def test_git_visible_fingerprint_excludes_arbitrary_untracked_paths(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    before = gate.capture_git_visible_state(root)

    (root / "new.txt").write_text("concurrent workspace output\n", encoding="utf-8")
    after = gate.capture_git_visible_state(root)

    assert before == after
    assert gate.compare_git_visible_states(before, after) == ()


def test_git_visible_fingerprint_includes_declared_workspace_overlay(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    manifest = root / ".docsystem/manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "workspace_overlays": {
                    "records": [
                        {
                            "id": "agent_overlay",
                            "path": "AGENTS.md",
                        }
                    ]
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("before\n", encoding="utf-8")
    before = gate.capture_git_visible_state(root)
    (root / "AGENTS.md").write_text("after\n", encoding="utf-8")
    after = gate.capture_git_visible_state(root)

    assert before.digest != after.digest
    assert any("AGENTS.md" in change for change in gate.compare_git_visible_states(before, after))


def test_gate_blocks_a_lane_that_mutates_the_input_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    mutator = _lane(
        "mutator",
        [
            "{python}",
            "-c",
            (
                "from pathlib import Path; "
                "Path(r'{repo}/tracked.txt').write_text('mutated\\n', encoding='utf-8')"
            ),
        ],
    )
    config = _config(mutator)
    monkeypatch.setattr(gate, "load_gate_configuration", lambda _root: ({}, config))

    report = gate.run_gate(root=root, profile="changed")

    assert report.passed is False
    assert report.lane_results[0].passed is True
    assert any("tracked.txt" in change or "Git status changed" in change for change in report.state_changes)


def test_parallel_lanes_receive_distinct_external_temp_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    command = [
        "{python}",
        "-c",
        "import os; print(os.environ['TMPDIR']); print(os.environ['PYTHONPYCACHEPREFIX'])",
    ]
    config = _config(_lane("left", command), _lane("right", command))
    monkeypatch.setattr(gate, "load_gate_configuration", lambda _root: ({}, config))

    report = gate.run_gate(root=root, profile="changed")

    assert report.passed is True
    temp_roots = [result.output.splitlines()[0] for result in report.lane_results]
    assert len(set(temp_roots)) == 2
    assert all(not Path(value).exists() for value in temp_roots)
    assert all(not value.startswith(str(root)) for value in temp_roots)


def test_external_scratch_root_is_configurable_and_must_stay_outside_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT", str(scratch))
    assert gate._external_temp_parent(root) == scratch.resolve()

    # A system scratch ancestor is safe because each lane receives a sibling
    # TemporaryDirectory rather than a path inside the repository.
    monkeypatch.setenv("ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT", str(tmp_path))
    assert gate._external_temp_parent(root) == tmp_path.resolve()

    monkeypatch.setenv("ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT", str(root / "inside"))
    (root / "inside").mkdir()
    with pytest.raises(gate.GovernanceGateError, match="outside the repository"):
        gate._external_temp_parent(root)


def test_gate_cli_list_is_machine_readable() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "devtools/document_governance_gate.py"),
            "list",
            "--repo-root",
            str(PROJECT_ROOT),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["default_profile"] == "changed"
    assert {"changed", "full", "weekly", "historical_replay"} <= set(payload["profiles"])
    assert {lane["id"] for lane in payload["lanes"]} >= {
        "docsystem_doctor",
        "code_assets_current",
        "code_assets_history",
    }
