#!/usr/bin/env python3
"""Check the P1.2 proof-obligation consolidation manifest.

This is a small structural gate, not a theorem prover.  It makes the v29-v31
postmortem concrete enough that future reviews cannot silently drift back to
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
TEST_ROOT = PROJECT_ROOT / "src" / "tests"

REQUIRED_OBLIGATION_IDS = frozenset(
    {
        "PO-STEP7-ATTACH-MIRROR",
        "PO-SOURCE-DIGEST-COVERAGE",
        "PO-RUNTIME-CACHE-NON-AUTHORITY",
        "PO-PHASE-GATE-PROVENANCE",
    }
)
REQUIRED_TESTS_BY_OBLIGATION_ID = {
    "PO-PHASE-GATE-PROVENANCE": frozenset(
        {
            "test_validator_rejects_stale_last_reset_when_later_reset_history_exists",
            "test_validator_rejects_fake_closed_gate_without_post_reset_clean_reviews",
            "test_validator_rejects_fake_clean_reviews_without_evidence",
            "test_validator_rejects_fake_clean_reviews_with_nonreview_evidence",
            "test_validator_rejects_reused_clean_review_evidence",
            "test_validator_rejects_reused_clean_review_evidence_path_aliases",
            "test_validator_rejects_directory_evidence_even_when_path_matches_package",
            "test_validator_rejects_clean_reviews_reusing_reset_evidence_and_package",
            "test_require_ready_rejects_duplicate_gate_ids",
            "test_validator_rejects_hardlinked_clean_review_evidence",
            "test_validator_rejects_copied_clean_review_evidence_content",
            "test_validator_rejects_clean_review_evidence_bound_only_by_filename",
            "test_validator_rejects_package_token_only_clean_review_evidence",
            "test_phase_gate_json_loader_rejects_duplicate_keys",
            "test_validator_rejects_hidden_major_outcome_without_reset_even_with_later_clean_reviews",
            "test_validator_rejects_misclassified_major_soundness_outcome_as_infrastructure_after_clean_reviews",
            "test_validator_rejects_certified_false_negative_domain_without_algorithmic_reset_after_clean_reviews",
            "test_validator_rejects_negative_major_or_soundness_findings_count",
            "test_validator_rejects_clean_reviews_without_current_package_identity",
            "test_validator_rejects_clean_review_package_that_differs_from_current_package",
            "test_validator_rejects_body_only_current_package_binding",
            "test_phase_gate_json_loader_rejects_duplicate_current_package_keys",
            "test_validator_rejects_major_outcome_alias_without_reset",
            "test_validator_rejects_unknown_review_history_outcome",
            "test_validator_rejects_review_history_major_findings_alias_key",
            "test_validator_rejects_conflicting_current_package_metadata_after_read_prefix",
            "test_validator_rejects_archive_sha256_hyphen_alias_conflict",
            "test_validator_rejects_current_package_archive_name_package_canonical_collision",
            "test_validator_rejects_clean_review_history_package_canonical_collision",
            "test_validator_rejects_placeholder_source_list_identity",
            "test_validator_rejects_current_package_source_head_mismatch_with_git_head",
            "test_validator_rejects_missing_resets_counter_on_clean_review",
            "test_validator_rejects_current_package_archive_name_trailing_space",
            "test_validator_rejects_current_package_path_like_archive_name",
            "test_validator_rejects_current_package_unicode_archive_name",
            "test_validator_rejects_fullwidth_colon_metadata_conflict",
            "test_validator_rejects_semantic_placeholder_source_list_identity",
            "test_validator_rejects_omitted_source_list_identity_placeholder",
            "test_validator_rejects_current_package_json_alias_key_conflict",
            "test_validator_rejects_windows_reserved_archive_name",
            "test_validator_rejects_unicode_colon_metadata_conflict",
            "test_validator_rejects_unicode_normalized_metadata_key_conflict",
            "test_validator_rejects_confusable_metadata_key_conflict",
            "test_validator_rejects_confusable_key_with_confusable_delimiter",
            "test_validator_rejects_markdown_table_package_metadata_conflict",
            "test_validator_rejects_confusable_placeholder_source_list_identity",
            "test_validator_rejects_multilingual_placeholder_source_list_identity",
            "test_validator_uses_project_git_head_despite_git_dir_environment",
            "test_validator_uses_trusted_git_command_despite_path_environment",
            "test_validator_rejects_git_head_that_is_not_a_commit_object",
            "test_validator_rejects_latin_extended_metadata_key_conflict",
            "test_validator_rejects_html_table_package_metadata_conflict",
            "test_validator_rejects_fullwidth_pipe_table_package_metadata_conflict",
            "test_validator_rejects_markup_wrapped_package_metadata_conflict",
            "test_validator_rejects_latin_extended_placeholder_source_list_identity",
            "test_validator_rejects_git_replace_ref_backed_non_commit_head",
            "test_project_git_command_ignores_relative_defpath_entries",
            "test_windows_project_git_command_uses_standard_git_paths_before_os_defpath",
            "test_validator_rejects_gitdir_file_indirection_to_sibling_repo",
            "test_validator_rejects_git_objects_alternates_for_source_head_authority",
            "test_validator_rejects_bare_gitdir_source_head_authority",
            "test_validator_rejects_git_config_include_indirection_for_source_head_authority",
            "test_validator_rejects_git_config_worktree_include_indirection_for_source_head_authority",
            "test_validator_rejects_broken_git_authority_control_file_symlink_for_source_head_authority",
            "test_validator_rejects_git_promisor_remote_for_source_head_authority",
            "test_validator_rejects_git_promisor_pack_marker_for_source_head_authority",
            "test_project_git_env_disables_lazy_fetch",
            "test_validator_rejects_git_authority_symlink_escape_for_source_head_authority",
            "test_validator_rejects_broken_git_authority_symlink_escape_for_source_head_authority",
            "test_validator_rejects_git_root_symlink_even_when_broken",
            "test_validator_rejects_escaped_and_wrapped_metadata_conflicts",
            "test_validator_rejects_xml_payload_and_attribute_wrapped_metadata_conflicts",
            "test_validator_accepts_closed_gate_with_three_post_reset_clean_reviews",
            "test_validator_rejects_clean_review_receipt_source_tree_identity_mismatch",
            "test_validator_rejects_clean_review_receipt_report_sha_mismatch",
            "test_validator_rejects_clean_review_receipt_report_reuse_hidden_by_dummy_evidence",
            "test_validator_rejects_non_standard_json_constant_in_clean_review_receipt",
            "test_validator_rejects_boolean_schema_version_in_clean_review_receipt",
            "test_validator_rejects_boolean_schema_version_in_phase_gate_manifest",
            "test_validator_rejects_clean_review_with_algorithmic_reset_finding_domain",
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


def _calls_function(node: ast.AST, name: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name:
            return True
    return False


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
    errors: list[str] = []
    tree = _parse_python(PHASE_GATE_SCRIPT_PATH)

    current_package_fn = _function_def(
        tree,
        "_validate_current_review_package",
        path=PHASE_GATE_SCRIPT_PATH,
    )
    for required_call in (
        "_check_current_review_package_keys",
        "require_unpadded_str",
        "_is_safe_archive_name",
        "_project_git_head",
        "_is_placeholder_metadata_value",
    ):
        if not _calls_function(current_package_fn, required_call):
            errors.append(f"_validate_current_review_package must call {required_call}")

    security_skeleton_fn = _function_def(tree, "_ascii_security_skeleton", path=PHASE_GATE_SCRIPT_PATH)
    if not _uses_name(security_skeleton_fn, "unicodedata"):
        errors.append("_ascii_security_skeleton must Unicode-normalize metadata keys and placeholder text")

    metadata_key_fn = _function_def(tree, "_evidence_metadata_key", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(metadata_key_fn, "_ascii_security_skeleton"):
        errors.append("_evidence_metadata_key must use the review-gate ASCII security skeleton")

    normalized_match_fn = _function_def(tree, "_normalized_match_text", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(normalized_match_fn, "_ascii_security_skeleton"):
        errors.append("_normalized_match_text must use the review-gate ASCII security skeleton")

    evidence_metadata_fn = _function_def(tree, "_extract_evidence_metadata", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(evidence_metadata_fn, "_confusable_metadata_delimiter_error"):
        errors.append("_extract_evidence_metadata must reject confusable metadata delimiters")
    if not _calls_function(evidence_metadata_fn, "_markdown_table_metadata_error"):
        errors.append("_extract_evidence_metadata must reject table-form package metadata")
    if not _calls_function(evidence_metadata_fn, "_html_table_metadata_error"):
        errors.append("_extract_evidence_metadata must reject HTML table-form package metadata")
    if not _calls_function(evidence_metadata_fn, "_xml_payload_metadata_error"):
        errors.append("_extract_evidence_metadata must reject XML/SVG/MathML payload metadata wrappers")
    if not _calls_function(evidence_metadata_fn, "_markup_attribute_metadata_error"):
        errors.append("_extract_evidence_metadata must reject markup attribute metadata wrappers")

    placeholder_fn = _function_def(tree, "_is_placeholder_metadata_value", path=PHASE_GATE_SCRIPT_PATH)
    if not _uses_name(placeholder_fn, "PLACEHOLDER_METADATA_SUBSTRINGS"):
        errors.append("_is_placeholder_metadata_value must check semantic placeholder substrings")

    safe_name_fn = _function_def(tree, "_is_safe_archive_name", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(safe_name_fn, "_is_windows_reserved_archive_name"):
        errors.append("_is_safe_archive_name must reject Windows reserved archive basenames")

    project_git_head_fn = _function_def(tree, "_project_git_head", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(project_git_head_fn, "_validate_project_git_authority_root"):
        errors.append("_project_git_head must reject sibling/bare/alternate Git authority roots")
    if not _calls_function(project_git_head_fn, "_project_git_env"):
        errors.append("_project_git_head must use a sanitized Git authority environment")
    if not _calls_function(project_git_head_fn, "_project_git_command"):
        errors.append("_project_git_head must use the trusted Git command resolver")

    project_git_env_fn = _function_def(tree, "_project_git_env", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(project_git_env_fn, "_trusted_git_search_dirs"):
        errors.append("_project_git_env must build PATH only from trusted Git search dirs")
    if not _uses_constant(project_git_env_fn, "GIT_NO_REPLACE_OBJECTS"):
        errors.append("_project_git_env must disable Git replacement refs while checking source_head")
    if not _uses_constant(project_git_env_fn, "GIT_NO_LAZY_FETCH"):
        errors.append("_project_git_env must disable Git lazy fetch while checking source_head")
    if not _uses_constant(project_git_env_fn, "GIT_CONFIG_NOSYSTEM"):
        errors.append("_project_git_env must ignore system Git config while checking source_head")

    authority_root_fn = _function_def(tree, "_validate_project_git_authority_root", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(authority_root_fn, "_reject_git_config_external_authority"):
        errors.append("_validate_project_git_authority_root must reject include and promisor config authority")
    if not _calls_function(authority_root_fn, "_reject_git_promisor_pack_authority"):
        errors.append("_validate_project_git_authority_root must reject promisor pack authority")

    project_git_command_fn = _function_def(tree, "_project_git_command", path=PHASE_GATE_SCRIPT_PATH)
    if not _calls_function(project_git_command_fn, "_trusted_git_search_dirs"):
        errors.append("_project_git_command must not search caller/os.defpath directly")

    for required_symbol in (
        "_check_current_review_package_keys",
        "_check_review_history_entry_keys",
        "_confusable_metadata_delimiter_error",
        "_markdown_table_metadata_error",
        "_project_git_env",
        "_project_git_command",
        "_trusted_git_search_dirs",
        "_validate_project_git_authority_root",
        "_validate_clean_review_receipt",
        "_source_tree_identity_from_package",
        "_reject_git_config_external_authority",
        "_reject_git_promisor_pack_authority",
        "_ascii_security_skeleton",
        "_deep_html_unescape",
        "_html_table_metadata_error",
        "_xml_payload_metadata_error",
        "_markup_attribute_metadata_error",
        "_delimited_metadata_error",
    ):
        _function_def(tree, required_symbol, path=PHASE_GATE_SCRIPT_PATH)
    return errors


def _check_phase_anchor(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_anchor = _require_str(
        manifest.get("phase_gate_required_anchor"),
        "phase_gate_required_anchor",
    )
    required_reset_anchor = _require_str(
        manifest.get("phase_gate_required_algorithmic_reset_anchor", required_anchor),
        "phase_gate_required_algorithmic_reset_anchor",
    )
    phase_gate = _load_json(PHASE_GATE_PATH)
    current_anchor = phase_gate.get("current_review_anchor")
    last_reset = phase_gate.get("last_reset")
    last_reset_package = last_reset.get("review_package") if isinstance(last_reset, dict) else None
    counter_domains = phase_gate.get("counter_domains")
    algorithmic_domain = counter_domains.get("algorithmic_soundness") if isinstance(counter_domains, dict) else None
    algorithmic_last_reset = (
        algorithmic_domain.get("last_reset_package") if isinstance(algorithmic_domain, dict) else None
    )
    if current_anchor != required_anchor:
        errors.append(f"phase gate current_review_anchor {current_anchor!r} != required {required_anchor!r}")
    if last_reset_package != required_reset_anchor:
        errors.append(
            f"phase gate last_reset.review_package {last_reset_package!r} != required algorithmic reset "
            f"{required_reset_anchor!r}"
        )
    if algorithmic_last_reset != required_reset_anchor:
        errors.append(
            "phase gate counter_domains.algorithmic_soundness.last_reset_package "
            f"{algorithmic_last_reset!r} != required {required_reset_anchor!r}"
        )
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
