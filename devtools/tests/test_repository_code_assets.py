from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import jsonschema
import pytest

from devtools import artifact_evidence
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
EXPECTED_ARTIFACT_BOUNDARY_DESCRIPTOR = {
    "manifest": "data/artifact_boundaries.json",
    "schema": "data/repository_governance/artifact_boundaries.schema.json",
    "inputs": "data/repository_governance/artifact_evidence_inputs.json",
    "inputs_schema": "data/repository_governance/artifact_evidence_inputs.schema.json",
    "content_treatment": "non_code_asset",
    "mutation_expectation": "read_only_preserve_in_place",
}


def _historical_baseline_available() -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{BASELINE}^{{commit}}"],
        cwd=assets.ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _current_exact_source_digest() -> str:
    module = assets.importlib.import_module(assets.SOURCE_DISCOVERY_MODULES[0])
    digest_function = getattr(module, "compute_certified_exact_source_digest")
    return str(digest_function())


def _current_exact_source_matches_frozen_receipt() -> bool:
    manifest = assets.load_manifest()
    expected = manifest["measurement"]["certified_exact_source_baseline"][
        "source_digest"
    ]
    return _current_exact_source_digest() == expected


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
    if not _historical_baseline_available():
        pytest.skip("supplier snapshot omits the historical code-asset baseline object")
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


def test_git_untracked_paths_reports_only_nonignored_workspace_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=root, check=True)
    (root / "workspace 空格.txt").write_text("workspace\n", encoding="utf-8")
    (root / "ignored.txt").write_text("ignored\n", encoding="utf-8")

    assert artifact_evidence.git_untracked_paths(root) == ("workspace 空格.txt",)


def test_document_system_bootstrap_files_are_explicit_enforcement_controls() -> None:
    measured = assets.inventory(include_assets=True)
    by_path = {record["path"]: record for record in measured["assets"]}

    for path in (".docsystem/manifest.json", "DOC_POLICY.json"):
        record = by_path[path]
        assert record["primary_class"] == "enforcement_control"
        assert record["rule_id"] == "document_system_bootstrap_controls"
        assert record["authority_role"] == "non_authorizing_document_governance_control"
        assert record["certified_admission"] == "non_authorizing"


def test_current_inventory_has_only_declared_g1_and_conditional_assets() -> None:
    manifest = assets.load_manifest()
    measured = assets.inventory(include_assets=True)
    expected = dict(manifest["measurement"]["expected_current_class_counts"])
    visible = set(assets.git_visible_paths())
    for conditional in manifest["measurement"]["conditional_current_assets"]:
        if conditional["path"] in visible:
            expected[conditional["primary_class"]] += 1
    assert measured["class_counts"] == expected
    assert measured["code_asset_count"] == sum(expected.values())
    assert measured["git_visible_count"] == len(visible)
    assert not any(record["path"].startswith(".artifacts/") for record in measured["assets"])


def test_commit_inventory_never_exempts_registered_root_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked_path = ".artifacts/ab16_arms_20260802/tracked.py"
    monkeypatch.setattr(
        assets,
        "_commit_blobs",
        lambda _commit: {tracked_path: b"raise AssertionError\n"},
    )
    monkeypatch.setattr(
        assets,
        "_run_git",
        lambda _args, **_kwargs: b"1" * 40 + b"\n",
    )
    measured = assets.inventory(commit="synthetic", include_assets=True)
    assert measured["revision"] == "1" * 40
    assert measured["git_visible_count"] == 1
    assert measured["code_asset_count"] == 1
    assert measured["class_counts"]["historical_evidence"] == 1
    assert measured["assets"][0]["path"] == tracked_path
    assert measured["assets"][0]["rule_id"] == "artifact_history"


def test_artifact_evidence_boundary_is_dossier_derived_and_not_git_ignored() -> None:
    manifest = assets.load_manifest()
    assert manifest["artifact_evidence_boundary"] == EXPECTED_ARTIFACT_BOUNDARY_DESCRIPTOR

    # This supplier snapshot intentionally has the wrong Git topology: it
    # tracks local workspace evidence.  Load the semantic model without
    # pretending that the snapshot itself is a valid real-repository census.
    boundary = assets._artifact_evidence_boundary(manifest)
    representative_roots = {
        ".artifacts/ab16_arms_20260802/",
        ".artifacts/gpt_pro_review_batch_20260807/",
        ".artifacts/w0_front_aware_20260803/",
    }
    assert representative_roots <= set(boundary.registered_roots)
    assert ".artifacts/README.md" in boundary.tracked_root_files

    for root in representative_roots:
        completed = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "-q",
                f"{root}__repository_governance_probe__.py",
            ],
            cwd=assets.ROOT,
            check=False,
        )
        assert completed.returncode == 1, root


def test_registered_artifact_evidence_is_non_code_asset_without_prefix_bleed() -> None:
    manifest = assets.load_manifest()
    registered = ".artifacts/ab16_arms_20260802/"
    measured = assets._measurement(
        {
            f"{registered}probe.py": b"raise AssertionError\n",
            f"{registered}opaque.bin": b"#!/bin/sh\nexit 1\n",
            ".artifacts/_v28_dist.py": b"raise AssertionError\n",
            ".artifacts/ab16_arms_20260802-copy/probe.py": b"raise AssertionError\n",
            ".artifacts/future_campaign/probe.py": b"raise AssertionError\n",
        },
        manifest,
        include_assets=True,
    )
    assert measured["git_visible_count"] == 5
    assert measured["code_asset_count"] == 2
    assert measured["class_counts"]["historical_evidence"] == 2
    assert {record["path"] for record in measured["assets"]} == {
        ".artifacts/ab16_arms_20260802-copy/probe.py",
        ".artifacts/future_campaign/probe.py",
    }


def test_inventory_does_not_read_registered_artifact_evidence_contents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered = ".artifacts/h20_row_power_oracle_20260803/opaque.bin"
    root_file = ".artifacts/_v28_dist.py"
    unregistered = ".artifacts/future_campaign/probe.py"
    reads: list[str] = []

    monkeypatch.setattr(assets, "git_visible_paths", lambda: (registered, root_file, unregistered))

    def read_current(path: str) -> bytes:
        reads.append(path)
        return b"#!/usr/bin/env python3\n"

    monkeypatch.setattr(assets, "_current_bytes", read_current)
    measured = assets.inventory(include_assets=True)
    assert reads == [unregistered]
    assert measured["git_visible_count"] == 3
    assert measured["class_counts"]["historical_evidence"] == 1
    assert [record["path"] for record in measured["assets"]] == [unregistered]


def test_artifact_evidence_descriptor_rejects_parallel_fields_and_relaxation() -> None:
    parallel = copy.deepcopy(assets.load_manifest())
    parallel["artifact_evidence_boundary"]["parallel_registry"] = "other.json"
    with pytest.raises(assets.GovernanceError, match="invalid fields"):
        assets._artifact_evidence_boundary(parallel)

    relaxed = copy.deepcopy(assets.load_manifest())
    relaxed["artifact_evidence_boundary"]["content_treatment"] = "historical_code_asset"
    with pytest.raises(assets.GovernanceError, match="must remain non_code_asset"):
        assets._artifact_evidence_boundary(relaxed)


def test_artifact_evidence_validation_rejects_undeclared_tracked_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = assets.load_manifest()
    tracked = b".artifacts/future_campaign/probe.py\0"
    def fake_git(args: list[str], **_kwargs: object) -> bytes:
        if "--cached" in args:
            return tracked
        return b""

    monkeypatch.setattr(assets, "_run_git", fake_git)

    with pytest.raises(assets.GovernanceError, match="lacks git_tracked declaration"):
        assets._validate_artifact_evidence_boundary(manifest)


def test_unregistered_artifact_code_asset_still_fails_the_current_count_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = assets.load_manifest()
    synthetic = assets._measurement(
        {".artifacts/future_campaign/probe.py": b"raise AssertionError\n"},
        manifest,
        include_assets=True,
    )
    assert synthetic["class_counts"]["historical_evidence"] == 1
    assert synthetic["assets"][0]["rule_id"] == "artifact_history"

    actual_counts = dict(manifest["measurement"]["expected_current_class_counts"])
    actual_counts["enforcement_control"] += 1
    actual_counts["historical_evidence"] += 1
    monkeypatch.setattr(assets, "inventory", lambda **_kwargs: {"class_counts": actual_counts})
    monkeypatch.setattr(assets, "git_visible_paths", lambda: (".rgignore",))
    with pytest.raises(assets.GovernanceError, match="current class counts drifted"):
        assets._validate_current(manifest)


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


def test_artifact_boundary_separates_git_workspace_and_external_evidence() -> None:
    boundary = artifact_evidence.load_boundary(assets.ROOT)
    supplier_tracked = artifact_evidence.git_tracked_paths(
        assets.ROOT, boundary.root_prefix.rstrip("/"),
    )

    assert boundary.dossier_registry == "data/knowledge/dossiers.json"
    assert len(boundary.registered_roots) == 55
    assert len(boundary.tracked_root_files) == 7
    assert len(boundary.tracked_prefixes) == 9
    assert len(boundary.tracked_files) == 1
    assert len(boundary.workspace_root_files) == 24
    assert boundary.external_registry == "data/external_artifacts.json"
    assert boundary.expected_tracked_path_count == 117
    assert len(supplier_tracked) >= boundary.expected_tracked_path_count
    assert ".artifacts/research_runs/" in boundary.ignored_runtime_prefixes
    assert ".artifacts/research_runs/" not in boundary.registered_roots
    workspace_paths = artifact_evidence.validate_workspace_paths(
        boundary,
        artifact_evidence.git_untracked_paths(
            assets.ROOT, boundary.root_prefix.rstrip("/"),
        ),
    )
    assert all(boundary.covers_workspace(path) for path in workspace_paths)

    # Build a deterministic real-topology fixture from the supplier bytes.  The
    # supplier tar tracks local evidence, but the real repository has exactly
    # 117 tracked artifact paths after the two governance files are added.
    candidates = [path for path in supplier_tracked if boundary.covers_tracked(path)]
    required = sorted(set(boundary.tracked_root_files) | set(boundary.tracked_files))
    if len(supplier_tracked) == boundary.expected_tracked_path_count:
        simulated_real = supplier_tracked
    else:
        remaining = [path for path in candidates if path not in required]
        simulated_real = tuple(
            sorted(required + remaining[: boundary.expected_tracked_path_count - len(required)])
        )
    assert len(simulated_real) == boundary.expected_tracked_path_count
    assert artifact_evidence.validate_tracked_paths(boundary, simulated_real) == simulated_real

    workspace_probe = ".artifacts/ab16_arms_20260802/result.json"
    assert boundary.storage_class_for(workspace_probe) == "workspace_untracked"
    assert boundary.covers_tracked(workspace_probe) is False

    completed = subprocess.run(
        ["git", "check-ignore", "-q", ".artifacts/research_runs/probe/result.json"],
        cwd=assets.ROOT,
        check=False,
    )
    assert completed.returncode == 0


def test_artifact_boundary_projection_is_exact_and_supports_frozen_git_quoting() -> None:
    projection = assets.ROOT / artifact_evidence.DEFAULT_MANIFEST
    assert projection.read_text(encoding="utf-8") == artifact_evidence.render_projection(
        assets.ROOT
    )

    payload = json.loads(projection.read_text(encoding="utf-8"))
    prefixes = {record["path_prefix"] for record in payload["tracked_historical_evidence"]}
    semantic = ".artifacts/v28_gpt_review/"
    assert semantic in prefixes
    assert f'"{semantic}' in prefixes

    boundary = artifact_evidence.load_boundary(assets.ROOT)
    actual_tracked = artifact_evidence.git_tracked_paths(
        assets.ROOT, boundary.root_prefix.rstrip("/"),
    )
    if len(actual_tracked) == boundary.expected_tracked_path_count:
        completed = subprocess.run(
            [sys.executable, str(assets.ROOT / "scripts/check_artifact_boundaries.py")],
            cwd=assets.ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout
        assert "artifact boundary check passed" in completed.stdout
    else:
        pytest.skip("supplier snapshot tracks workspace evidence; real-topology replay is separate")


def test_artifact_boundary_rejects_manually_stale_projection(tmp_path: Path) -> None:
    root = _copy_artifact_boundary_fixture(tmp_path)
    projection = root / "data/artifact_boundaries.json"
    payload = json.loads(projection.read_text(encoding="utf-8"))
    payload["tracked_root_files"] = payload["tracked_root_files"][:-1]
    projection.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(
        artifact_evidence.ArtifactEvidenceError,
        match="tracked_root_files is stale",
    ):
        artifact_evidence.load_boundary(root)


def test_artifact_boundary_rejects_undeclared_or_ignored_tracked_paths() -> None:
    boundary = artifact_evidence.ArtifactEvidenceBoundary(
        root_prefix=".artifacts/",
        dossier_registry="data/knowledge/dossiers.json",
        registered_roots=(),
        tracked_root_files=(".artifacts/README.md",),
        ignored_runtime_prefixes=(".artifacts/runtime/",),
        tracked_prefixes=(".artifacts/known/", ".artifacts/runtime/"),
    )

    with pytest.raises(
        artifact_evidence.ArtifactEvidenceError,
        match="lacks git_tracked declaration",
    ):
        artifact_evidence.validate_tracked_paths(
            boundary,
            (".artifacts/README.md", ".artifacts/unknown/payload.json"),
        )

    with pytest.raises(
        artifact_evidence.ArtifactEvidenceError,
        match="ignored runtime artifact prefix",
    ):
        artifact_evidence.validate_tracked_paths(
            boundary,
            (
                ".artifacts/README.md",
                ".artifacts/known/payload.json",
                ".artifacts/runtime/result.json",
            ),
        )


def test_artifact_boundary_has_exact_prefix_semantics_without_sibling_bleed() -> None:
    boundary = artifact_evidence.ArtifactEvidenceBoundary(
        root_prefix=".artifacts/",
        dossier_registry="data/knowledge/dossiers.json",
        registered_roots=(".artifacts/known/",),
        tracked_root_files=(".artifacts/README.md",),
        ignored_runtime_prefixes=(),
    )

    assert boundary.covers(".artifacts/known/payload.json") is True
    assert boundary.covers(".artifacts/README.md") is True
    assert boundary.covers(".artifacts/known-copy/payload.json") is False


def _copy_artifact_boundary_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relpath in (
        "data/artifact_boundaries.json",
        "data/repository_governance/artifact_boundaries.schema.json",
        "data/repository_governance/artifact_evidence_inputs.json",
        "data/repository_governance/artifact_evidence_inputs.schema.json",
        "data/knowledge/dossiers.json",
        "data/external_artifacts.json",
    ):
        source = assets.ROOT / relpath
        destination = root / relpath
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return root


def test_artifact_boundary_rejects_stale_root_file_declaration(tmp_path: Path) -> None:
    root = _copy_artifact_boundary_fixture(tmp_path)
    boundary = artifact_evidence.load_boundary(root)
    tracked = tuple(
        path for path in boundary.tracked_root_files if path != ".artifacts/_v28_dist.py"
    )
    with pytest.raises(
        artifact_evidence.ArtifactEvidenceError,
        match="declared .artifacts root file is not tracked",
    ):
        artifact_evidence.validate_tracked_paths(boundary, tracked)


def test_artifact_boundary_rejects_runtime_overlap(tmp_path: Path) -> None:
    root = _copy_artifact_boundary_fixture(tmp_path)
    inputs_path = (
        root / "data/repository_governance/artifact_evidence_inputs.json"
    )
    payload = json.loads(inputs_path.read_text(encoding="utf-8"))
    payload["ignored_runtime_artifact_prefixes"].append(
        ".artifacts/ab16_arms_20260802/runtime/"
    )
    payload["ignored_runtime_artifact_prefixes"].sort()
    inputs_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(
        artifact_evidence.ArtifactEvidenceError,
        match="overlaps registered evidence root",
    ):
        artifact_evidence.write_projection(root)


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


def test_production_devtools_reference_exception_is_exact_and_literal_only() -> None:
    manifest = assets.load_manifest()
    assert assets._production_devtools_reference_exceptions(manifest) == (
        (
            "scripts/preflight_gate.py",
            "MEMORY_PLATE_TOOL",
            "devtools/memory_plate_tool.py",
        ),
    )
    assets._validate_no_production_devtools_import(manifest)

    missing = copy.deepcopy(manifest)
    missing["production_devtools_reference_exceptions"] = []
    with pytest.raises(assets.GovernanceError, match="production source references"):
        assets._validate_no_production_devtools_import(missing)

    stale = copy.deepcopy(manifest)
    stale["production_devtools_reference_exceptions"][0]["symbol"] = "OTHER_TOOL"
    with pytest.raises(assets.GovernanceError, match="production source references"):
        assets._validate_no_production_devtools_import(stale)


def test_source_discovery_implementations_agree_and_exclude_devtools() -> None:
    baseline_commit = assets.load_manifest()["measurement"][
        "certified_exact_source_baseline"
    ]["commit"]
    available = subprocess.run(
        ["git", "cat-file", "-e", f"{baseline_commit}^{{commit}}"],
        cwd=assets.ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if available.returncode != 0:
        with pytest.raises(assets.GovernanceError, match="source identity drifted"):
            assets._source_discovery_receipt()

        modules = [
            assets.importlib.import_module(name)
            for name in assets.SOURCE_DISCOVERY_MODULES
        ]
        paths = [tuple(module._discover_certified_exact_source_hash_files()) for module in modules]
        digests = [str(module.compute_certified_exact_source_digest()) for module in modules]
        assert paths[0] == paths[1]
        assert digests[0] == digests[1]
        assert len(paths[0]) == 804
        assert not any(path.startswith("devtools/") for path in paths[0])
        return

    receipt = assets._source_discovery_receipt()
    assert receipt["path_count"] == 804
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
    if not _current_exact_source_matches_frozen_receipt():
        pytest.skip(
            "supplier snapshot exact source differs from the frozen receipt; "
            "the checker remains fail-closed in a complete certified tree"
        )
    assets._validate_no_production_devtools_import(assets.load_manifest())


def test_current_check_is_explicitly_scoped_and_does_not_claim_history() -> None:
    receipt = assets.check_current()

    assert receipt["status"] == "PASS"
    assert receipt["scope"] == "current_worktree_only"
    assert receipt["current"]["class_counts"]["retirement_candidate"] == 19
    assert receipt["not_checked"] == [
        "frozen_code_asset_baseline_commit",
        "certified_exact_source_baseline_receipt",
    ]


def test_cli_current_check_json_is_machine_readable() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(assets.ROOT / "devtools" / "check_repository_code_assets.py"),
            "check-current",
            "--format",
            "json",
        ],
        cwd=assets.ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["scope"] == "current_worktree_only"
    assert "frozen_code_asset_baseline_commit" in payload["not_checked"]


def test_check_command_passes_or_fails_only_on_missing_supplier_baseline() -> None:
    if not _historical_baseline_available():
        with pytest.raises(assets.GovernanceError, match=r"git .*ls-tree .* failed"):
            assets.check()
        return

    receipt = assets.check()
    assert receipt["status"] == "PASS"
    assert receipt["baseline"]["code_asset_count"] == 2001
    assert receipt["current"]["class_counts"]["retirement_candidate"] == 19


def test_cli_inventory_json_is_machine_readable_when_baseline_is_available() -> None:
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
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not _historical_baseline_available():
        assert completed.returncode != 0
        assert "ls-tree" in completed.stdout
        return

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["revision"] == BASELINE
    assert payload["class_counts"] == BASELINE_COUNTS
