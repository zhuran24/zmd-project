from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import jsonschema
import pytest

from devtools import check_repository_code_assets as assets


BASELINE = "201c1988243951e16473af15f5d670ab11edf964"
BASELINE_COUNTS = {
    "active_implementation": 386,
    "test": 646,
    "common_infrastructure": 475,
    "authoritative_input": 4,
    "enforcement_control": 7,
    "historical_evidence": 464,
    "retirement_candidate": 19,
}
CURRENT_BASE_COUNTS = {
    "active_implementation": 386,
    "test": 656,
    "common_infrastructure": 477,
    "authoritative_input": 4,
    "enforcement_control": 9,
    "historical_evidence": 477,
    "retirement_candidate": 19,
}


def test_manifest_validates_against_durable_json_schema() -> None:
    manifest = assets.load_manifest()
    schema = json.loads(assets.SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)


def test_checker_rejects_manifest_additional_property() -> None:
    manifest = copy.deepcopy(assets.load_manifest())
    schema = json.loads(assets.SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest["unexpected_parallel_authority"] = True
    with pytest.raises(assets.GovernanceError, match="schema validation failed"):
        assets._validate_against_schema(schema, manifest)


def test_checker_rejects_invalid_schema() -> None:
    manifest = assets.load_manifest()
    schema = json.loads(assets.SCHEMA_PATH.read_text(encoding="utf-8"))
    schema["type"] = "not-a-json-schema-type"
    with pytest.raises(assets.GovernanceError, match="schema is invalid"):
        assets._validate_against_schema(schema, manifest)


def test_baseline_inventory_is_reproducible_from_git_objects() -> None:
    measured = assets.inventory(commit=BASELINE, include_assets=False)
    assert measured == {
        "revision": BASELINE,
        "git_visible_count": 3249,
        "code_asset_count": 2001,
        "raw_bytes": 36_483_677,
        "lf_count": 912_444,
        "class_counts": BASELINE_COUNTS,
    }


def test_nul_path_parsers_preserve_unicode_spaces_and_newlines() -> None:
    paths = ("docs/中文 名称.md", "docs/line\nbreak.py")
    raw_paths = b"\0".join(path.encode("utf-8") for path in paths) + b"\0"
    assert assets._parse_nul_paths(raw_paths) == paths

    object_ids = ("1" * 40, "2" * 40)
    raw_tree = b"".join(
        object_id.encode("ascii") + b"\t" + path.encode("utf-8") + b"\0"
        for object_id, path in zip(object_ids, paths, strict=True)
    )
    assert assets._parse_ls_tree_records(raw_tree) == tuple(zip(object_ids, paths, strict=True))


def test_current_inventory_has_only_declared_g1_and_conditional_assets() -> None:
    manifest = assets.load_manifest()
    measured = assets.inventory(include_assets=True)
    expected = dict(CURRENT_BASE_COUNTS)
    visible = set(assets.git_visible_paths())
    for conditional in manifest["measurement"]["conditional_current_assets"]:
        if conditional["path"] in visible:
            expected[conditional["primary_class"]] += 1
    assert measured["class_counts"] == expected
    assert measured["code_asset_count"] == sum(expected.values())


def test_pose_bool_backend_is_active_guarded_and_default_visible() -> None:
    manifest = assets.load_manifest()
    rule = assets._classification_for("src/models/pose_bool_exact_master.py", manifest)
    assert rule["primary_class"] == "active_implementation"
    assert rule["lifecycle"] == "active_env_gated"
    assert rule["certified_admission"] == "blocked_pose_bool_master_not_certified"
    assert "developer" in rule["workflow_membership"]
    search_patterns = manifest["logical_isolation"]["search"]["excluded_rules"]
    assert not any(
        assets._matches_glob("src/models/pose_bool_exact_master.py", pattern)
        for pattern in search_patterns
    )


def test_retirement_candidate_set_is_exactly_the_nineteen_review_builders() -> None:
    measured = assets.inventory(include_assets=True)
    actual = {
        record["path"]
        for record in measured["assets"]
        if record["primary_class"] == "retirement_candidate"
    }
    expected = (
        {f"scripts/build_phase1_1_gpt_pro_review_v{version}.py" for version in range(2, 9)}
        | {f"scripts/build_phase1_2_entry_review_v{version}.py" for version in range(9, 12)}
        | {f"scripts/build_phase1_2_spike_review_v{version}.py" for version in range(14, 23)}
    )
    assert actual == expected


def test_authority_inputs_controls_and_current_specs_are_not_historical_evidence() -> None:
    manifest = assets.load_manifest()
    paths = [
        "rules/canonical_rules.json",
        "rules/preprocess_plan.json",
        "data/preprocessed/generic_io_requirements.json",
        "data/preprocessed/mandatory_exact_instances.json",
        "data/proof_obligations/p1_2_proof_obligations.json",
        "data/review_gates/phase_1_2_spike_close.json",
        "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
        "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
        "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
    ]
    for path in paths:
        role = assets._asset_role_for(path, manifest)
        assert role["asset_role"] != "historical_evidence", path
    f8 = assets._asset_role_for(
        "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
        manifest,
    )
    assert f8["lifecycle"] == "retired_retained"


def test_capability_index_paths_and_symbols_are_live_without_crossing_frozen_boundaries() -> None:
    manifest = assets.load_manifest()
    assets._validate_capability_index(manifest)

    stale = copy.deepcopy(manifest)
    stale["capability_index"][0]["implementations"][0]["symbol"] = "__missing_symbol__"
    with pytest.raises(assets.GovernanceError, match="symbol is stale"):
        assets._validate_capability_index(stale)


def test_capability_index_has_exactly_one_preferred_active_for_each_shared_authority() -> None:
    manifest = assets.load_manifest()
    assets._validate_capability_index(manifest)

    shared = copy.deepcopy(manifest)
    shared["capability_index"][0]["implementations"][1]["role"] = "preferred_active"
    with pytest.raises(assets.GovernanceError, match="unique preferred_active"):
        assets._validate_capability_index(shared)

    unshared = copy.deepcopy(manifest)
    retained = next(
        capability
        for capability in unshared["capability_index"]
        if capability["capability"] == "retained_same_fd"
    )
    retained["implementations"][0]["role"] = "preferred_active"
    with pytest.raises(assets.GovernanceError, match="without shared authority"):
        assets._validate_capability_index(unshared)


def test_research_run_root_is_declared_and_ignored_without_hiding_historical_evidence() -> None:
    boundary = json.loads(
        (assets.ROOT / "data" / "artifact_boundaries.json").read_text(encoding="utf-8")
    )
    assert ".artifacts/research_runs/" in boundary["ignored_runtime_artifact_prefixes"]
    completed = subprocess.run(
        ["git", "check-ignore", "-q", ".artifacts/research_runs/probe/result.json"],
        cwd=assets.ROOT,
        check=False,
    )
    assert completed.returncode == 0
    tracked_prefixes = {
        record["path_prefix"] for record in boundary["tracked_historical_evidence"]
    }
    assert ".artifacts/research_runs/" not in tracked_prefixes


def test_g1_disabled_projection_mode_has_no_g2_file_dependency() -> None:
    manifest = copy.deepcopy(assets.load_manifest())
    for name in ("search", "lint", "pytest"):
        manifest["logical_isolation"][name]["enabled"] = False
    assets._validate_enabled_projections(manifest)


def test_g2_search_pytest_and_lint_projections_are_enabled() -> None:
    manifest = assets.load_manifest()
    assert {
        name: manifest["logical_isolation"][name]["enabled"]
        for name in ("search", "lint", "pytest")
    } == {"search": True, "lint": True, "pytest": True}

    developer = assets._projected_lint_paths("developer")
    full = assets._projected_lint_paths("full")
    assert developer["projection_enabled"] is True
    assert "src/models/pose_bool_exact_master.py" in developer["paths"]
    assert "scripts/phase3b/checkpoint_free/signature_bucket/build_s53_fail_closed_hardening.py" not in developer["paths"]
    assert "scripts/build_phase1_2_spike_review_v22.py" not in developer["paths"]
    assert "scripts/phase3b/checkpoint_free/signature_bucket/build_s53_fail_closed_hardening.py" in full["paths"]
    assert "scripts/build_phase1_2_spike_review_v22.py" in full["paths"]


def test_search_projection_is_exact_and_does_not_hide_future_retirement_names() -> None:
    manifest = assets.load_manifest()
    expected = manifest["logical_isolation"]["search"]["excluded_rules"]
    actual = [
        line
        for raw_line in (assets.ROOT / ".rgignore").read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    ]
    assert actual == expected
    assert "scripts/build_phase1_2_spike_review_v22.py" in actual
    assert "scripts/build_phase1_2_spike_review_v23.py" not in actual
    assert not any(
        assets._matches_glob("src/models/pose_bool_exact_master.py", pattern)
        for pattern in actual
    )
    assert not any(
        assets._matches_glob("rules/canonical_rules.json", pattern)
        for pattern in actual
    )


def test_phase3b_replay_wrappers_are_outside_the_developer_import_surface() -> None:
    manifest = assets.load_manifest()
    wrappers = (
        "scripts/run_phase3b_checkpoint_free_evaluator.py",
        "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
        "scripts/run_phase3b_local_tuning_profile.py",
    )
    for path in wrappers:
        classification = assets._classification_for(path, manifest)
        assert classification["lifecycle"] == "historical_executable_replay"
        assert "developer" not in classification["workflow_membership"]
    assets._validate_developer_import_boundary(manifest)


def test_lint_projection_has_a_nul_safe_python_path_channel() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(assets.ROOT / "devtools" / "check_repository_code_assets.py"),
            "lint",
            "--profile",
            "developer",
            "--format",
            "nul",
        ],
        cwd=assets.ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    paths = tuple(
        part.decode("utf-8")
        for part in completed.stdout.split(b"\0")
        if part
    )
    assert paths
    assert all(Path(path).suffix in {".py", ".pyi"} for path in paths)
    assert "src/models/pose_bool_exact_master.py" in paths
    assert "scripts/phase3b/checkpoint_free/signature_bucket/build_s53_fail_closed_hardening.py" not in paths


def test_pytest_lane_rules_are_ordered_replay_evidence_then_developer() -> None:
    rules = assets.load_manifest()["logical_isolation"]["pytest"]["lane_rules"]

    def lane(path: str) -> str:
        return next(rule["lane"] for rule in rules if assets._matches_glob(path, rule["glob"]))

    assert lane("src/tests/cuts/test_replay.py") == "replay"
    assert lane("src/tests/phase3b/test_campaign_replay.py") == "replay"
    assert lane("src/tests/test_noncert_cuts_ab16_contract_v1.py") == "evidence"
    assert lane("src/tests/test_r1_upper_bound_pb_v1.py") == "evidence"
    assert lane("src/tests/test_routing.py") == "developer"
    assets._validate_pytest_lanes(assets.load_manifest())


def test_focused_workflow_refuses_marker_deselection() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:randomly",
            "--repository-workflow=focused-full",
            "--basetemp=.pytest_tmp/governance-focused",
            "-k",
            "__repository_governance_selects_nothing__",
            "src/tests/test_routing.py",
            "--collect-only",
            "-q",
        ],
        cwd=assets.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert completed.returncode == pytest.ExitCode.USAGE_ERROR
    assert "focused-full forbids -m/-k selection" in completed.stdout


def test_affected_selector_cannot_reintroduce_an_evidence_target() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:randomly",
            "--basetemp=.pytest_tmp/selected",
            "-m",
            "not slow",
            "src/tests/test_routing.py",
            "src/tests/test_noncert_cuts_ab16_contract_v1.py",
            "--collect-only",
            "-q",
        ],
        cwd=assets.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert completed.returncode == pytest.ExitCode.USAGE_ERROR
    assert "developer workflow refuses explicit targets from another lane" in completed.stdout


def test_source_discovery_implementations_agree_and_exclude_devtools() -> None:
    receipt = assets._source_discovery_receipt()
    assert receipt["path_count"] == 800
    assert receipt["devtools_paths"] == []
    assert len(receipt["sha256"]) == 64


def test_source_discovery_rejects_two_implementations_drifting_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = SimpleNamespace(
        _discover_certified_exact_source_hash_files=lambda: ("main.py",),
        compute_certified_exact_source_digest=lambda: "0" * 64,
    )
    monkeypatch.setattr(assets.importlib, "import_module", lambda _name: fake_module)
    with pytest.raises(assets.GovernanceError, match="identity drifted"):
        assets._source_discovery_receipt()


def test_production_source_does_not_import_or_literal_reference_devtools() -> None:
    assets._validate_no_production_devtools_import()


def test_check_command_passes_as_a_single_g1_gate() -> None:
    receipt = assets.check()
    assert receipt["status"] == "PASS"
    assert receipt["baseline"]["code_asset_count"] == 2001
    assert receipt["current"]["class_counts"]["retirement_candidate"] == 19


def test_cli_inventory_json_is_machine_readable() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(assets.ROOT / "devtools" / "check_repository_code_assets.py"),
            "inventory",
            "--commit",
            BASELINE,
            "--format",
            "json",
        ],
        cwd=assets.ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["revision"] == BASELINE
    assert payload["class_counts"] == BASELINE_COUNTS
