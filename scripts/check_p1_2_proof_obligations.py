#!/usr/bin/env python3
"""Check the P1.2 proof-obligation consolidation manifest.

This is a small structural gate, not a theorem prover.  It makes the P1.2
postmortems concrete enough that future reviews cannot silently drift back to
local, duplicated proof checks.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "proof_obligations" / "p1_2_proof_obligations.json"
PHASE_GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"
PHASE_GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_phase_review_gate.py"
LIFECYCLE_PATH = PROJECT_ROOT / "src" / "cuts" / "lifecycle.py"
CANDIDATE_PLACEMENTS_PATH = PROJECT_ROOT / "src" / "cuts" / "helpers" / "candidate_placements.py"
CUT_MANAGER_PATH = PROJECT_ROOT / "src" / "models" / "cut_manager.py"
EXACT_CAMPAIGN_PATH = PROJECT_ROOT / "src" / "search" / "exact_campaign.py"
OUTER_SEARCH_PATH = PROJECT_ROOT / "src" / "search" / "outer_search.py"
BENDERS_LOOP_PATH = PROJECT_ROOT / "src" / "search" / "benders_loop.py"
DELIVERY_MANIFEST_PATH = PROJECT_ROOT / "src" / "io" / "delivery_manifest.py"
MASTER_MODEL_PATH = PROJECT_ROOT / "src" / "models" / "master_model.py"
EXACT_COORDINATE_MASTER_PATH = PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py"
POSE_BOOL_EXACT_MASTER_PATH = PROJECT_ROOT / "src" / "models" / "pose_bool_exact_master.py"
TEST_ROOT = PROJECT_ROOT / "src" / "tests"

REQUIRED_OBLIGATION_IDS = frozenset(
    {
        "PO-STEP7-ATTACH-MIRROR",
        "PO-SOURCE-DIGEST-COVERAGE",
        "PO-RUNTIME-CACHE-NON-AUTHORITY",
        "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS",
        "PO-PHASE-GATE-PROVENANCE",
    }
)
REQUIRED_TESTS_BY_OBLIGATION_ID = {
    "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS": frozenset(
        {
            "test_benders_cut_from_dict_rejects_string_exact_safe_flag",
            "test_collect_certification_blockers_rejects_non_bool_exact_safe_object",
            "test_benders_cut_from_dict_rejects_string_conflict_pose_index",
            "test_benders_cut_from_dict_rejects_bool_conflict_pose_index",
            "test_benders_cut_from_dict_rejects_bool_condition_anchor_index",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_without_condition_set",
            "test_benders_cut_to_dict_rejects_condition_required_power_cut_without_condition_set",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_with_unknown_condition_key",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_metadata_mismatch",
            "test_benders_cut_from_dict_rejects_condition_required_power_cut_rect_idx_mismatch",
            "test_benders_cut_from_dict_rejects_noncanonical_ghost_anchor_condition_keys",
            "test_collect_certification_blockers_rejects_bool_conflict_pose_index",
            "test_exact_campaign_resume_rejects_malformed_exact_safe_cut",
            "test_exact_campaign_resume_rejects_bool_conflict_pose_index",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_without_condition_set",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_with_unknown_condition_key",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_metadata_mismatch",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_rect_idx_not_resolver_supported",
            "test_exact_campaign_resume_accepts_condition_required_power_cut_with_resolver_supported_anchor",
            "test_exact_campaign_resume_rejects_condition_required_power_cut_anchor_outside_domain",
            "test_cut_manager_load_rejects_duplicate_exact_safe_key",
            "test_exact_campaign_resume_rejects_duplicate_json_key",
            "test_exact_campaign_resume_rejects_json_nan_constant",
            "test_cut_manager_load_rejects_json_nan_constant",
            "test_persisted_cut_replay_fails_closed_on_unresolved_conflict_member",
            "test_whole_layout_cut_dilution_fails_closed_when_synthetic_pole_loses_literal",
            "test_whole_layout_nogood_propagates_master_rejection_for_unresolved_member",
            "test_routing_front_blocked_unencodable_optional_conflict_fails_closed",
            "test_coordinate_replay_alias_collision_fails_closed_instead_of_one_literal_ban",
            "test_pose_bool_replay_alias_collision_fails_closed",
            "test_legacy_benders_cut_alias_collision_fails_closed",
            "test_resolver_fails_closed_on_malformed_ghost_anchor_key",
            "test_exact_campaign_state_persists_full_master_domain_contract",
            "test_exact_campaign_resume_rejects_filtered_master_domain_contract",
            "test_exact_campaign_resume_rejects_float_state_schema_version",
            "test_exact_campaign_resume_rejects_float_proof_summary_schema_version",
            "test_exact_campaign_resume_rejects_bool_generated_cut_count",
            "test_exact_campaign_resume_rejects_best_effort_final_result",
            "test_exact_campaign_resume_rejects_missing_declare_mode",
            "test_delivery_manifest_rejects_best_effort_final_result",
            "test_certified_exact_blocks_ghost_anchor_filter_env_before_candidate_terminal_status",
            "test_certified_exact_blocks_pose_bool_master_env_before_session",
            "test_certified_exact_blocks_power_pole_slot_override_before_session",
            "test_certified_outer_search_blocks_skip_unknown_env_before_fake_certified",
        }
    ),
    "PO-PHASE-GATE-PROVENANCE": frozenset(
        {
            "test_phase_review_gate_manifest_is_consistent",
            "test_require_ready_fails_while_manual_gate_blocked",
            "test_manual_gate_rejects_auto_counter_fields",
            "test_manual_gate_rejects_next_phase_allowed_without_owner_decision",
            "test_manual_gate_rejects_closed_status_without_owner_decision",
            "test_manual_gate_requires_step_8_fail_closed_when_blocked",
            "test_manual_gate_accepts_owner_decision_authority_fixture",
            "test_manual_gate_receipts_are_informational_only",
        }
    ),
}


class CheckError(RuntimeError):
    pass


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise CheckError(f"invalid JSON constant {value!r}; proof-obligation JSON must be strict JSON")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except Exception as exc:  # noqa: BLE001
        raise CheckError(f"cannot read {_rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise CheckError(f"{_rel(path)} must contain a JSON object")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CheckError(f"{label} must be a non-empty string")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CheckError(f"{label} must be a list")
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CheckError(f"{label} must be an integer")
    return value


def _parse_python(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise CheckError(f"cannot parse {_rel(path)}: {exc}") from exc


def _parse_lifecycle() -> ast.Module:
    return _parse_python(LIFECYCLE_PATH)


def _function_def(tree: ast.Module, name: str, *, path: Path = LIFECYCLE_PATH) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise CheckError(f"function not found in {_rel(path)}: {name}")


def _class_def(tree: ast.Module, name: str, *, path: Path) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise CheckError(f"class not found in {_rel(path)}: {name}")


def _method_def(class_node: ast.ClassDef, name: str, *, path: Path) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise CheckError(f"method not found in {_rel(path)}: {class_node.name}.{name}")


def _calls_function(node: ast.AST, name: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name:
            return True
    return False


def _calls_attr(node: ast.AST, attr: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == attr:
            return True
    return False


def _returns_constant(node: ast.AST, value: object) -> bool:
    return any(isinstance(child, ast.Return) and isinstance(child.value, ast.Constant) and child.value.value is value for child in ast.walk(node))


def _raises_value_error(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Raise):
            continue
        exc = child.exc
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "ValueError":
            return True
        if isinstance(exc, ast.Name) and exc.id == "ValueError":
            return True
    return False


def _source_text(path: Path, node: ast.AST) -> str:
    source = path.read_text(encoding="utf-8")
    return ast.get_source_segment(source, node) or ""


def _uses_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _uses_constant(node: ast.AST, value: str) -> bool:
    return any(isinstance(child, ast.Constant) and child.value == value for child in ast.walk(node))


def _imports_lifecycle_constants() -> tuple[int, tuple[str, ...], tuple[str, ...], dict[str, tuple[str, ...]]]:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.cuts.lifecycle import (  # pylint: disable=import-outside-toplevel
        SOURCE_DIGEST_FIELD_NAMES,
        SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH,
        SOURCE_DIGEST_SCHEMA_VERSION,
        STEP_7_EVALUATION_GUARD_OBLIGATIONS,
    )

    runtime_cache_keys = {
        ".".join(path): tuple(sorted(keys)) for path, keys in SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH.items()
    }
    return (
        SOURCE_DIGEST_SCHEMA_VERSION,
        tuple(SOURCE_DIGEST_FIELD_NAMES),
        tuple(STEP_7_EVALUATION_GUARD_OBLIGATIONS),
        runtime_cache_keys,
    )


def _test_symbols() -> set[str]:
    symbols: set[str] = set()
    for path in TEST_ROOT.rglob("test_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            raise CheckError(f"cannot parse test file {_rel(path)}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                symbols.add(node.name)
    return symbols


def _check_step7_contract(manifest: dict[str, Any], tree: ast.Module) -> list[str]:
    errors: list[str] = []
    contract = manifest.get("step_7_contract")
    if not isinstance(contract, dict):
        return ["step_7_contract must be an object"]

    decision_name = _require_str(contract.get("decision_function"), "step_7_contract.decision_function")
    canonical_name = _require_str(
        contract.get("canonical_transition_function"),
        "step_7_contract.canonical_transition_function",
    )
    bool_guard_name = _require_str(
        contract.get("boolean_guard_function"),
        "step_7_contract.boolean_guard_function",
    )

    decision_fn = _function_def(tree, decision_name)
    bool_guard_fn = _function_def(tree, bool_guard_name)
    step7_fn = _function_def(tree, "step_7_evaluate_cut")
    literal_fn = _function_def(tree, "evaluate_literal_multiset")

    if not _calls_function(decision_fn, canonical_name):
        errors.append(f"{decision_name} must call {canonical_name}")
    if not _calls_function(bool_guard_fn, decision_name):
        errors.append(f"{bool_guard_name} must delegate to {decision_name}")
    if not _calls_function(step7_fn, bool_guard_name):
        errors.append(f"step_7_evaluate_cut must call {bool_guard_name}")
    if not _calls_function(literal_fn, bool_guard_name):
        errors.append(f"evaluate_literal_multiset must call {bool_guard_name}")
    return errors


def _uses_dunder_prefix_skip(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not isinstance(func, ast.Attribute) or func.attr != "startswith":
            continue
        if not child.args:
            continue
        arg = child.args[0]
        if isinstance(arg, ast.Constant) and arg.value == "__":
            return True
    return False


def _assigns_name(tree: ast.Module, name: str) -> bool:
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return True
    return False


def _calls_id_on_candidate_placements(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Name) or child.func.id != "id":
            continue
        if child.args and isinstance(child.args[0], ast.Name) and child.args[0].id in {"cp", "candidate_placements"}:
            return True
    return False


def _check_runtime_cache_policy(manifest: dict[str, Any], lifecycle_tree: ast.Module) -> list[str]:
    errors: list[str] = []
    source_contract = manifest.get("source_digest_contract")
    if not isinstance(source_contract, dict):
        return ["source_digest_contract must be an object"]

    _, _, _, code_cache_keys = _imports_lifecycle_constants()
    manifest_cache_raw = source_contract.get("runtime_cache_keys_by_path")
    if not isinstance(manifest_cache_raw, dict):
        errors.append("source_digest_contract.runtime_cache_keys_by_path must be an object")
    else:
        manifest_cache_keys: dict[str, tuple[str, ...]] = {}
        for raw_path, raw_keys in manifest_cache_raw.items():
            path = _require_str(raw_path, "source_digest_contract.runtime_cache_keys_by_path key")
            keys = tuple(sorted(str(key) for key in _require_list(raw_keys, f"runtime cache keys for {path}")))
            manifest_cache_keys[path] = keys
        if manifest_cache_keys != code_cache_keys:
            errors.append(
                "source_digest_contract.runtime_cache_keys_by_path disagrees with "
                "SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH: "
                f"manifest={manifest_cache_keys!r}, code={code_cache_keys!r}"
            )

    source_jsonable_fn = _function_def(lifecycle_tree, "_source_jsonable")
    if _uses_dunder_prefix_skip(source_jsonable_fn):
        errors.append("_source_jsonable must not ignore every key with startswith('__')")

    candidate_tree = _parse_python(CANDIDATE_PLACEMENTS_PATH)
    cache_jsonable_fn = _function_def(
        candidate_tree,
        "_cache_jsonable",
        path=CANDIDATE_PLACEMENTS_PATH,
    )
    if _uses_dunder_prefix_skip(cache_jsonable_fn):
        errors.append("_cache_jsonable must not ignore schema-valid facility pool keys with startswith('__')")

    find_pose_fn = _function_def(
        candidate_tree,
        "find_pose",
        path=CANDIDATE_PLACEMENTS_PATH,
    )
    if _assigns_name(candidate_tree, "_POSE_CACHE_BY_CP_ID"):
        errors.append("candidate placement runtime cache must not be keyed by candidate_placements object id")
    if _calls_id_on_candidate_placements(find_pose_fn):
        errors.append("find_pose must not key runtime cache by id(candidate_placements)")
    return errors


def _check_source_digest_contract(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_contract = manifest.get("source_digest_contract")
    if not isinstance(source_contract, dict):
        return ["source_digest_contract must be an object"]

    schema_version, field_names, guard_obligations, _ = _imports_lifecycle_constants()
    manifest_schema = source_contract.get("schema_version")
    if manifest_schema != schema_version:
        errors.append(
            "source_digest_contract.schema_version disagrees with "
            f"SOURCE_DIGEST_SCHEMA_VERSION: manifest={manifest_schema!r}, code={schema_version!r}"
        )
    manifest_fields = tuple(
        str(item) for item in _require_list(source_contract.get("fields"), "source_digest_contract.fields")
    )
    if manifest_fields != field_names:
        errors.append(
            "source_digest_contract.fields disagree with SOURCE_DIGEST_FIELD_NAMES: "
            f"manifest={manifest_fields!r}, code={field_names!r}"
        )

    contract = manifest.get("step_7_contract")
    if isinstance(contract, dict):
        manifest_obligations = tuple(
            str(item) for item in _require_list(contract.get("guard_obligations"), "step_7_contract.guard_obligations")
        )
        if manifest_obligations != guard_obligations:
            errors.append(
                "step_7_contract.guard_obligations disagree with "
                "STEP_7_EVALUATION_GUARD_OBLIGATIONS: "
                f"manifest={manifest_obligations!r}, code={guard_obligations!r}"
            )
    return errors


def _check_source_digest_uses_contract(tree: ast.Module) -> list[str]:
    errors: list[str] = []
    _function_def(tree, "source_digest_payload")
    compute_fn = _function_def(tree, "compute_source_digest")
    if not _calls_function(compute_fn, "source_digest_payload"):
        errors.append("compute_source_digest must hash source_digest_payload(state)")
    return errors


def _check_evidence_and_tests(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    test_symbols = _test_symbols()
    obligations = _require_list(manifest.get("obligations"), "obligations")
    if not obligations:
        errors.append("obligations must not be empty")
        return errors

    seen_ids: set[str] = set()
    listed_tests_by_obligation: dict[str, set[str]] = {}
    for index, raw_obligation in enumerate(obligations):
        if not isinstance(raw_obligation, dict):
            errors.append(f"obligations[{index}] must be an object")
            continue
        obligation_id = _require_str(raw_obligation.get("id"), f"obligations[{index}].id")
        if obligation_id in seen_ids:
            errors.append(f"duplicate obligation id: {obligation_id}")
        seen_ids.add(obligation_id)
        for raw_path in _require_list(raw_obligation.get("evidence_paths"), f"{obligation_id}.evidence_paths"):
            rel_path = _require_str(raw_path, f"{obligation_id}.evidence_paths[]")
            if not (PROJECT_ROOT / rel_path).exists():
                errors.append(f"{obligation_id} missing evidence path: {rel_path}")
        listed_tests: set[str] = set()
        for raw_test in _require_list(raw_obligation.get("required_tests"), f"{obligation_id}.required_tests"):
            test_name = _require_str(raw_test, f"{obligation_id}.required_tests[]")
            listed_tests.add(test_name)
            if test_name not in test_symbols:
                errors.append(f"{obligation_id} missing required test symbol: {test_name}")
        listed_tests_by_obligation[obligation_id] = listed_tests

    missing_obligation_ids = REQUIRED_OBLIGATION_IDS - seen_ids
    for obligation_id in sorted(missing_obligation_ids):
        errors.append(f"missing required obligation id: {obligation_id}")

    for obligation_id, required_tests in sorted(REQUIRED_TESTS_BY_OBLIGATION_ID.items()):
        if obligation_id not in seen_ids:
            continue
        missing_tests = required_tests - listed_tests_by_obligation.get(obligation_id, set())
        for test_name in sorted(missing_tests):
            errors.append(f"{obligation_id} omits required regression test: {test_name}")
    return errors


def _check_phase_gate_provenance_contract() -> list[str]:
    """Check that the phase gate is now a small manual fail-closed gate.

    V37-V50 showed that parsing receipts, prose reports, package metadata, and
    Git authority had become a separate security protocol.  The proof-obligation
    gate now anchors the opposite contract: P1.3B can only be opened by an owner
    manual decision; receipts are informational and the repository does not
    derive clean-review count.
    """
    errors: list[str] = []
    tree = _parse_python(PHASE_GATE_SCRIPT_PATH)

    for required_symbol in (
        "_check_manual_review_standard",
        "_check_owner_manual_state",
        "_check_owner_manual_decision",
        "_step_8_apply_to_master_is_fail_closed",
        "_check_step_8_boundary",
        "check_gate",
    ):
        _function_def(tree, required_symbol, path=PHASE_GATE_SCRIPT_PATH)

    check_gate_fn = _function_def(tree, "check_gate", path=PHASE_GATE_SCRIPT_PATH)
    for required_call in (
        "_check_manual_review_standard",
        "_check_owner_manual_state",
        "_check_owner_manual_decision",
        "_check_step_8_boundary",
    ):
        if not _calls_function(check_gate_fn, required_call):
            errors.append(f"manual phase gate check_gate must call {required_call}")

    manual_standard_fn = _function_def(tree, "_check_manual_review_standard", path=PHASE_GATE_SCRIPT_PATH)
    if not (_uses_constant(manual_standard_fn, "owner_manual_count_outside_repo") or _uses_name(manual_standard_fn, "COUNTING_AUTHORITY")):
        errors.append("manual review standard must require owner_manual_count_outside_repo")
    if not (_uses_constant(manual_standard_fn, "informational_record_only") or _uses_name(manual_standard_fn, "RECEIPT_ROLE")):
        errors.append("manual review standard must require informational receipt role")

    step8_boundary_fn = _function_def(tree, "_check_step_8_boundary", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(step8_boundary_fn, "_step_8_apply_to_master_is_fail_closed"):
        errors.append("manual phase gate must verify step_8 remains fail-closed while blocked")

    forbidden_symbols = (
        "_validate_clean_review_receipt",
        "_validate_current_review_package",
        "_extract_evidence_metadata",
        "_project_git_head",
    )
    for symbol in forbidden_symbols:
        try:
            _function_def(tree, symbol, path=PHASE_GATE_SCRIPT_PATH)
        except CheckError:
            continue
        errors.append(f"manual phase gate should not retain automatic authority parser: {symbol}")
    return errors


def _check_certified_cut_replay_contract(manifest: dict[str, Any]) -> list[str]:
    """Anchor the V53-V56 certified-cut replay faithful-encoding contract.

    This is intentionally structural.  V53-V56 showed that a persisted
    exact-safe Benders cut is only safe if every handoff in the replay chain is
    fail-closed: strict payload parsing, resume validation, all-or-nothing
    conflict member resolution, one-to-one member-to-literal encoding, and
    register/count only after master application succeeds.
    """

    errors: list[str] = []
    contract = manifest.get("certified_cut_replay_contract")
    if not isinstance(contract, dict):
        return ["certified_cut_replay_contract must be an object"]

    for raw_path in _require_list(contract.get("backend_scope"), "certified_cut_replay_contract.backend_scope"):
        rel_path = _require_str(raw_path, "certified_cut_replay_contract.backend_scope[]")
        if not (PROJECT_ROOT / rel_path).exists():
            errors.append(f"certified replay backend scope path missing: {rel_path}")

    cut_manager_tree = _parse_python(CUT_MANAGER_PATH)
    benders_cut_class = _class_def(cut_manager_tree, "BendersCut", path=CUT_MANAGER_PATH)
    from_dict_fn = _method_def(benders_cut_class, "from_dict", path=CUT_MANAGER_PATH)
    to_dict_fn = _method_def(benders_cut_class, "to_dict", path=CUT_MANAGER_PATH)
    cut_manager_class = _class_def(cut_manager_tree, "CutManager", path=CUT_MANAGER_PATH)
    load_fn = _method_def(cut_manager_class, "load", path=CUT_MANAGER_PATH)

    for helper_name in (
        "_strict_int",
        "_strict_bool",
        "_strict_int_mapping",
        "_loads_strict_json_object",
        "_reject_json_constant",
        "_cut_requires_condition_set",
        "_parse_canonical_nonnegative_coord",
        "_parse_ghost_anchor_condition_key",
        "_validate_certified_condition_shape",
        "_validate_condition_required_power_metadata",
        "_validate_certified_condition_requirement",
    ):
        _function_def(cut_manager_tree, helper_name, path=CUT_MANAGER_PATH)
    strict_int_fn = _function_def(cut_manager_tree, "_strict_int", path=CUT_MANAGER_PATH)
    strict_bool_fn = _function_def(cut_manager_tree, "_strict_bool", path=CUT_MANAGER_PATH)
    strict_json_fn = _function_def(cut_manager_tree, "_loads_strict_json_object", path=CUT_MANAGER_PATH)
    parse_coord_fn = _function_def(
        cut_manager_tree,
        "_parse_canonical_nonnegative_coord",
        path=CUT_MANAGER_PATH,
    )
    parse_condition_key_fn = _function_def(
        cut_manager_tree,
        "_parse_ghost_anchor_condition_key",
        path=CUT_MANAGER_PATH,
    )
    condition_shape_fn = _function_def(
        cut_manager_tree,
        "_validate_certified_condition_shape",
        path=CUT_MANAGER_PATH,
    )
    condition_metadata_fn = _function_def(
        cut_manager_tree,
        "_validate_condition_required_power_metadata",
        path=CUT_MANAGER_PATH,
    )
    if not (_uses_name(strict_int_fn, "bool") and _raises_value_error(strict_int_fn)):
        errors.append("_strict_int must reject bool-as-int certified replay payloads")
    if not (_uses_name(strict_bool_fn, "bool") and _raises_value_error(strict_bool_fn)):
        errors.append("_strict_bool must reject truthy/falsy non-bool exact_safe payloads")
    if "parse_constant" not in _source_text(CUT_MANAGER_PATH, strict_json_fn):
        errors.append("CutManager strict JSON loader must reject NaN/Infinity constants")
    parse_coord_source = _source_text(CUT_MANAGER_PATH, parse_coord_fn)
    for needle in (
        'startswith("0")',
        '"0" <= char <= "9"',
        "MAX_GHOST_ANCHOR_CONDITION_COORD",
    ):
        if needle not in parse_coord_source:
            errors.append(f"condition_set coordinate parser must enforce canonical non-negative decimal token: {needle}")
    parse_condition_key_source = _source_text(CUT_MANAGER_PATH, parse_condition_key_fn)
    if "GHOST_ANCHOR_CONDITION_PREFIX" not in parse_condition_key_source or "len(parts) != 2" not in parse_condition_key_source:
        errors.append("condition_set ghost anchors must use a strict ghost_anchor::(x,y) parser")
    if "_parse_canonical_nonnegative_coord" not in parse_condition_key_source:
        errors.append("condition_set ghost anchors must reject whitespace, sign, underscore, negative, and overflow-like coordinates")
    if ".strip" in parse_condition_key_source or "int(parts" in parse_condition_key_source:
        errors.append("condition_set ghost anchor parser must not normalize malformed coordinate keys")
    condition_shape_source = _source_text(CUT_MANAGER_PATH, condition_shape_fn)
    if "_parse_ghost_anchor_condition_key" not in condition_shape_source or "rect_idx" not in condition_shape_source:
        errors.append("certified condition_set payloads must reject unsupported or malformed condition anchors")
    condition_metadata_source = _source_text(CUT_MANAGER_PATH, condition_metadata_fn)
    for needle in (
        "len(condition_set) != 1",
        "metadata.ghost_rect_idx",
        "metadata.ghost_anchor",
        "_parse_ghost_anchor_condition_key",
    ):
        if needle not in condition_metadata_source:
            errors.append(f"condition-required power cuts must validate {needle}")
    for fn_name, fn in (("BendersCut.from_dict", from_dict_fn), ("BendersCut.to_dict", to_dict_fn)):
        for helper_name in ("_strict_bool", "_strict_int", "_strict_int_mapping"):
            if not _calls_function(fn, helper_name):
                errors.append(f"{fn_name} must call {helper_name}")
        if not _calls_function(fn, "_validate_certified_condition_requirement"):
            errors.append(f"{fn_name} must enforce certified condition requirements")
    if not _calls_function(load_fn, "_loads_strict_json_object"):
        errors.append("CutManager.load must use strict JSON duplicate-key rejection")

    exact_campaign_tree = _parse_python(EXACT_CAMPAIGN_PATH)
    exact_campaign_strict_json_fn = _function_def(exact_campaign_tree, "_loads_strict_json_object", path=EXACT_CAMPAIGN_PATH)
    _function_def(exact_campaign_tree, "_reject_json_constant", path=EXACT_CAMPAIGN_PATH)
    if "parse_constant" not in _source_text(EXACT_CAMPAIGN_PATH, exact_campaign_strict_json_fn):
        errors.append("ExactCampaign strict JSON loader must reject NaN/Infinity constants")
    for helper_name in (
        "_load_exact_grid_dimensions",
        "_strict_candidate_ghost_rect",
        "_expected_unfiltered_ghost_anchor_index",
        "_validate_cut_condition_domain",
        "_default_master_domain_contract",
        "_validate_master_domain_contract",
    ):
        _function_def(exact_campaign_tree, helper_name, path=EXACT_CAMPAIGN_PATH)
    validate_record_fn = _function_def(exact_campaign_tree, "_validate_candidate_record", path=EXACT_CAMPAIGN_PATH)
    validate_source = _source_text(EXACT_CAMPAIGN_PATH, validate_record_fn)
    if "BendersCut.from_dict" not in validate_source:
        errors.append("ExactCampaign resume validation must parse every exact_safe_cut with BendersCut.from_dict")
    if "cut.exact_safe is not True" not in validate_source:
        errors.append("ExactCampaign resume validation must require cut.exact_safe is True, not truthy")
    if "_validate_cut_condition_domain" not in validate_source:
        errors.append("ExactCampaign resume validation must reject condition_set keys that cannot resolve in the candidate ghost domain")
    resume_fn = _function_def(exact_campaign_tree, "_validate_resume_state", path=EXACT_CAMPAIGN_PATH)
    resume_source = _source_text(EXACT_CAMPAIGN_PATH, resume_fn)
    if "_load_exact_grid_dimensions" not in resume_source or "project_root" not in resume_source:
        errors.append("ExactCampaign resume validation must load current grid dimensions for condition resolver support checks")
    if "_validate_master_domain_contract" not in resume_source:
        errors.append("ExactCampaign resume validation must reject restricted or missing master domain contracts")
    exact_campaign_source = EXACT_CAMPAIGN_PATH.read_text(encoding="utf-8")
    if "master_domain_contract" not in exact_campaign_source:
        errors.append("ExactCampaign state must persist an explicit full master-domain contract")
    for needle in (
        '_strict_resume_int(state.get("schema_version")',
        'state.get("proof_summary_schema_version")',
        "declare_mode",
        "final_result_declare_mode_not_strict",
        "final_result_requires_strict_declare_mode",
    ):
        if needle not in exact_campaign_source:
            errors.append(f"ExactCampaign resume/final evidence contract must fail closed on non-strict or non-strictly-typed state: {needle}")

    outer_tree = _parse_python(OUTER_SEARCH_PATH)
    run_outer_fn = _function_def(outer_tree, "run_outer_search", path=OUTER_SEARCH_PATH)
    run_outer_source = _source_text(OUTER_SEARCH_PATH, run_outer_fn)
    outer_source = OUTER_SEARCH_PATH.read_text(encoding="utf-8")
    for needle in (
        "EXACT_OUTER_SKIP_UNKNOWN_ENV",
        "outer_skip_unknown_not_certified",
        "_certified_outer_skip_unknown_blocker",
    ):
        if needle not in outer_source:
            errors.append(
                "certified outer search must define a fail-closed UNKNOWN-skip blocker: "
                f"{needle}"
            )
    for needle in (
        "_outer_skip_unknown_enabled()",
        "_certified_outer_skip_unknown_blocker",
        "mark_campaign_stopped",
        "RUN_STATUS_UNPROVEN",
    ):
        if needle not in run_outer_source:
            errors.append(
                "certified outer search must fail closed before candidate subset/best-effort evidence: "
                f"{needle}"
            )

    delivery_manifest_tree = _parse_python(DELIVERY_MANIFEST_PATH)
    build_manifest_fn = _function_def(
        delivery_manifest_tree,
        "build_certified_delivery_manifest",
        path=DELIVERY_MANIFEST_PATH,
    )
    build_manifest_source = _source_text(DELIVERY_MANIFEST_PATH, build_manifest_fn)
    for needle in ("declare_mode", "strict", "certified delivery manifest requires strict declare_mode"):
        if needle not in build_manifest_source:
            errors.append(
                "certified delivery manifest must reject non-strict final_result inheritance: "
                f"{needle}"
            )

    benders_tree = _parse_python(BENDERS_LOOP_PATH)
    run_benders_fn = _function_def(
        benders_tree,
        "run_benders_for_ghost_rect",
        path=BENDERS_LOOP_PATH,
    )
    run_benders_source = _source_text(BENDERS_LOOP_PATH, run_benders_fn)
    for needle in (
        "EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV",
        "ghost_anchor_filter_not_certified",
        "_collect_forbidden_certified_master_domain_env_overrides",
        "unsafe_certified_exact_master_domain_env",
        "_publish_last_run_metadata",
        "RUN_STATUS_UNPROVEN",
    ):
        if needle not in run_benders_source:
            errors.append(
                "certified exact run entrypoint must fail closed when the "
                f"ghost-anchor domain is env-filtered: {needle}"
            )
    forbidden_env_fn = _function_def(
        benders_tree,
        "_collect_forbidden_certified_master_domain_env_overrides",
        path=BENDERS_LOOP_PATH,
    )
    forbidden_env_source = _source_text(BENDERS_LOOP_PATH, forbidden_env_fn)
    benders_loop_source = BENDERS_LOOP_PATH.read_text(encoding="utf-8")
    for needle in (
        "EXACT_USE_POSE_BOOL_MASTER_ENV",
        "pose_bool_master_not_certified",
        "EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE_ENV",
        "power_pole_slot_upper_bound_override_not_certified",
    ):
        if needle not in forbidden_env_source and needle not in benders_loop_source:
            errors.append(
                "certified exact master-domain env blocker must reject sibling-domain overrides: "
                f"{needle}"
            )
    resolve_condition_fn = _function_def(
        benders_tree,
        "_resolve_condition_lits_from_condition_set",
        path=BENDERS_LOOP_PATH,
    )
    resolve_condition_source = _source_text(BENDERS_LOOP_PATH, resolve_condition_fn)
    if "_parse_ghost_anchor_condition_key" not in resolve_condition_source:
        errors.append("condition_set replay resolver must share the strict ghost_anchor parser")

    controller_class = _class_def(benders_tree, "LBBDController", path=BENDERS_LOOP_PATH)
    persisted_fn = _method_def(controller_class, "_add_exact_persisted_nogood", path=BENDERS_LOOP_PATH)
    persisted_source = _source_text(BENDERS_LOOP_PATH, persisted_fn)
    if "BendersCut.from_dict(cut.to_dict())" not in persisted_source:
        errors.append("generated certified cuts must round-trip through BendersCut validation before master apply")
    required_order = (
        "self.master.add_benders_cut",
        "self.cut_manager.register_structured_cut",
        "self.generated_exact_safe_cuts.append",
    )
    positions = [persisted_source.find(needle) for needle in required_order]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append(
            "_add_exact_persisted_nogood must apply to master, then register, then count generated exact-safe cuts"
        )

    master_tree = _parse_python(MASTER_MODEL_PATH)
    master_class = _class_def(master_tree, "MasterPlacementModel", path=MASTER_MODEL_PATH)
    master_add_fn = _method_def(master_class, "add_benders_cut", path=MASTER_MODEL_PATH)
    master_source = _source_text(MASTER_MODEL_PATH, master_add_fn)
    if "seen_names" not in master_source or not _returns_constant(master_add_fn, False):
        errors.append("MasterPlacementModel.add_benders_cut must fail closed on missing or aliasing literals")

    coordinate_tree = _parse_python(EXACT_COORDINATE_MASTER_PATH)
    coordinate_class = _class_def(coordinate_tree, "CoordinateExactMasterDelegate", path=EXACT_COORDINATE_MASTER_PATH)
    entries_fn = _method_def(coordinate_class, "_conflict_pose_entries", path=EXACT_COORDINATE_MASTER_PATH)
    coordinate_add_fn = _method_def(coordinate_class, "add_benders_cut", path=EXACT_COORDINATE_MASTER_PATH)
    entries_source = _source_text(EXACT_COORDINATE_MASTER_PATH, entries_fn)
    if "seen" not in entries_source or "return []" not in entries_source:
        errors.append("CoordinateExactMasterDelegate._conflict_pose_entries must reject missing or aliasing members")
    if not _calls_attr(coordinate_add_fn, "_conflict_pose_entries") or not _returns_constant(coordinate_add_fn, False):
        errors.append("CoordinateExactMasterDelegate.add_benders_cut must fail closed when entries/literals are unresolved")

    pose_bool_tree = _parse_python(POSE_BOOL_EXACT_MASTER_PATH)
    pose_bool_class = _class_def(pose_bool_tree, "PoseBoolExactMasterDelegate", path=POSE_BOOL_EXACT_MASTER_PATH)
    pose_bool_add_fn = _method_def(pose_bool_class, "add_benders_cut", path=POSE_BOOL_EXACT_MASTER_PATH)
    pose_bool_source = _source_text(POSE_BOOL_EXACT_MASTER_PATH, pose_bool_add_fn)
    if "seen_lit_names" not in pose_bool_source or not _returns_constant(pose_bool_add_fn, False):
        errors.append("PoseBoolExactMasterDelegate.add_benders_cut must fail closed on missing or aliasing literals")

    return errors


def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_anchor = _require_str(
        manifest.get("phase_gate_required_anchor"),
        "phase_gate_required_anchor",
    )
    phase_gate = _load_json(PHASE_GATE_PATH)
    current_anchor = phase_gate.get("current_review_anchor")
    owner_state = phase_gate.get("owner_manual_state")
    owner_anchor = owner_state.get("current_review_anchor") if isinstance(owner_state, dict) else None
    next_phase_entry = phase_gate.get("next_phase_entry")
    next_allowed = next_phase_entry.get("allowed") if isinstance(next_phase_entry, dict) else None
    receipt_policy = phase_gate.get("receipt_policy")
    receipt_can_open = receipt_policy.get("can_open_p1_3b") if isinstance(receipt_policy, dict) else None
    if current_anchor != required_anchor:
        errors.append(f"phase gate current_review_anchor {current_anchor!r} != required {required_anchor!r}")
    if owner_anchor != required_anchor:
        errors.append(f"phase gate owner_manual_state.current_review_anchor {owner_anchor!r} != required {required_anchor!r}")
    if next_allowed is not False:
        errors.append("phase gate must remain blocked unless owner manual decision opens P1.3B")
    if receipt_can_open is not False:
        errors.append("phase gate receipt_policy.can_open_p1_3b must remain false")
    return errors


def main() -> int:
    try:
        manifest = _load_json(MANIFEST_PATH)
        errors: list[str] = []
        try:
            schema_version = _require_int(manifest.get("schema_version"), "schema_version")
        except CheckError as exc:
            errors.append(str(exc))
        else:
            if schema_version != 1:
                errors.append("schema_version must be 1")
        if manifest.get("gate_id") != "p1_2_proof_obligation_consolidation":
            errors.append("gate_id must be p1_2_proof_obligation_consolidation")
        lifecycle_tree = _parse_lifecycle()
        errors.extend(_check_step7_contract(manifest, lifecycle_tree))
        errors.extend(_check_source_digest_contract(manifest))
        errors.extend(_check_source_digest_uses_contract(lifecycle_tree))
        errors.extend(_check_runtime_cache_policy(manifest, lifecycle_tree))
        errors.extend(_check_certified_cut_replay_contract(manifest))
        errors.extend(_check_evidence_and_tests(manifest))
        errors.extend(_check_phase_gate_provenance_contract())
        errors.extend(_check_phase_anchor(manifest))
    except CheckError as exc:
        print(f"P1.2 proof obligation check failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"P1.2 proof obligation check failed: {len(errors)} issue(s)")
        for error in errors[:50]:
            print(f"  - {error}")
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more")
        return 1

    obligations = len(manifest.get("obligations", []))
    print(f"P1.2 proof obligation check passed: {obligations} obligations anchored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
