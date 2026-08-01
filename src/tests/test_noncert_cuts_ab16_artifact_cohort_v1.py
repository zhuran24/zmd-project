from __future__ import annotations

import ast
import copy
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
import re
from typing import cast

import pytest

from docs.research.noncert_cuts_ab16_20260724 import ab16_artifact_cohort_v1 as cohort


ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "docs/research/noncert_cuts_ab16_20260724"
BOOTSTRAP_PATH = RESEARCH_DIR / "ab16_campaign_bootstrap_v2.py"
AUTHORITY_PATH = RESEARCH_DIR / "ab16_authority_v2.py"
SCHEMA_LITERAL_RE = re.compile(r"noncert-cuts-(?:ab16|gate1)-[a-z0-9-]+-v[0-9]+\Z")

SchemaLocation = tuple[str, str]


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_bytes(), filename=str(path))


def _top_level_assignments(path: Path) -> dict[str, list[ast.expr]]:
    assignments: dict[str, list[ast.expr]] = defaultdict(list)
    for statement in _tree(path).body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id].append(statement.value)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
        ):
            assignments[statement.target.id].append(statement.value)
    return dict(assignments)


def _one_assignment(path: Path, name: str) -> ast.expr:
    values = _top_level_assignments(path).get(name, [])
    assert len(values) == 1, f"{path.relative_to(ROOT)} must assign {name} exactly once; found {len(values)}"
    return values[0]


def _literal_dict(path: Path, name: str) -> dict[str, str]:
    expression = _one_assignment(path, name)
    assert isinstance(expression, ast.Dict), (
        f"{path.relative_to(ROOT)}:{name} must remain one literal dictionary"
    )
    pairs: list[tuple[str, str]] = []
    for key, member in zip(expression.keys, expression.values, strict=True):
        assert (
            isinstance(key, ast.Constant)
            and type(key.value) is str
            and isinstance(member, ast.Constant)
            and type(member.value) is str
        ), f"{path.relative_to(ROOT)}:{name} has a non-literal entry"
        pairs.append((key.value, member.value))
    result = dict(pairs)
    assert len(result) == len(pairs), f"{path.relative_to(ROOT)}:{name} repeats a logical role"
    assert len(set(result.values())) == len(result), (
        f"{path.relative_to(ROOT)}:{name} aliases two roles to one package member"
    )
    return result


def _literal_frozenset(path: Path, name: str) -> frozenset[str]:
    expression = _one_assignment(path, name)
    assert (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "frozenset"
        and len(expression.args) == 1
        and not expression.keywords
    ), f"{path.relative_to(ROOT)}:{name} must remain one literal frozenset"
    members = expression.args[0]
    assert isinstance(members, ast.Set)
    values: list[str] = []
    for member in members.elts:
        assert isinstance(member, ast.Constant) and type(member.value) is str
        values.append(member.value)
    result = frozenset(values)
    assert len(result) == len(values), f"{path.relative_to(ROOT)}:{name} repeats a package role"
    return result


def _role_path(role: str) -> Path:
    assert role.startswith("tool.") and role.endswith(".py"), f"not one package tool role: {role!r}"
    path = RESEARCH_DIR / role.removeprefix("tool.")
    assert path.is_file(), f"package role source is absent: {role}"
    return path


def _schema_assignment_locations(paths: Iterable[Path]) -> dict[str, set[SchemaLocation]]:
    result: dict[str, set[SchemaLocation]] = defaultdict(set)
    for path in sorted(set(paths)):
        role = f"tool.{path.name}"
        for name, expressions in _top_level_assignments(path).items():
            for expression in expressions:
                if (
                    isinstance(expression, ast.Constant)
                    and type(expression.value) is str
                    and SCHEMA_LITERAL_RE.fullmatch(expression.value) is not None
                ):
                    result[expression.value].add((role, name))
    return dict(result)


def _schema_literal_occurrences(
    paths: Iterable[Path],
) -> dict[str, set[str]]:
    """Return every schema-shaped literal, including inline parser comparisons."""

    occurrences: dict[str, set[str]] = defaultdict(set)
    for path in sorted(set(paths)):
        tree = _tree(path)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and type(node.value) is str
                and SCHEMA_LITERAL_RE.fullmatch(node.value) is not None
            ):
                location = f"{path.relative_to(ROOT)}:{node.lineno}"
                occurrences[node.value].add(location)
    return dict(occurrences)


def _bootstrap_tool_files() -> frozenset[str]:
    return frozenset(_literal_dict(BOOTSTRAP_PATH, "AB16_SCRIPT_TOOL_FILES").values())


def _authority_ab16_tool_files() -> frozenset[str]:
    roles = _literal_frozenset(AUTHORITY_PATH, "REQUIRED_PACKAGE_ROLES")
    tool_files = {
        role.removeprefix("tool.")
        for role in roles
        if role.startswith("tool.")
    }
    inherited_v4 = set(_literal_dict(BOOTSTRAP_PATH, "V4_SCRIPT_TOOL_FILES").values())
    return frozenset(tool_files - inherited_v4)


def _prospective_source_paths() -> frozenset[Path]:
    roles = {
        cast(tuple[str, str], binding["producer"])[0]
        for binding in cohort.PROSPECTIVE_SCHEMA_BINDINGS.values()
    }
    roles.update(
        role
        for binding in cohort.PROSPECTIVE_SCHEMA_BINDINGS.values()
        for role, _constant in cast(tuple[SchemaLocation, ...], binding["consumers"])
    )
    roles.update(
        f"tool.{name}" for name in cohort.PROSPECTIVE_REQUIRED_PACKAGE_TOOL_FILES
    )
    roles.update(f"tool.{name}" for name in _bootstrap_tool_files())
    return frozenset(_role_path(role) for role in roles)


def _binding_with_consumers(
    key: str,
) -> dict[str, object]:
    binding = cohort.PROSPECTIVE_SCHEMA_BINDINGS[key]
    return {
        "schema": cast(str, binding["schema"]),
        "producer": cast(SchemaLocation, binding["producer"]),
        "consumers": list(cast(tuple[SchemaLocation, ...], binding["consumers"])),
    }


def test_prospective_cohort_expands_to_the_exact_launch_blocked_matrix() -> None:
    document = cohort.expanded_prospective_cohort()

    assert document["schema_version"] == "noncert-cuts-ab16-artifact-cohort-v1"
    assert document["cohort_id"] == "noncert-cuts-ab16-resource-budget-authority-readiness-v1"
    assert document["authority_scope"] == "AB16_RESEARCH_ONLY"
    assert document["launch_ready"] is False
    assert document["historical_replay_only"] is False
    assert document["a039_in_scope"] is False
    assert document["package_roles"] == {
        "final_release_actor": "tool.ab16_final_release_actor_v1.py",
        "independent_verifier": "tool.package_independent_verifier_v1.py",
        "native_helper_binary": "system.native_budget_helper.bin",
        "native_helper_wrapper": "tool.ab16_native_budget_helper_v1.py",
    }
    assert document["schemas"] == dict(cohort.PROSPECTIVE_SCHEMAS)
    assert document["schemas"]["calibration_package"].endswith("-v2")
    assert document["schemas"]["resource_execution_surface"].endswith("-v3")
    assert document["schemas"]["calibration_fd_loader"].endswith("-v2")
    assert document["schemas"]["formal_selection"].endswith("-v3")
    assert document["schemas"]["stage_resource_admission"].endswith("-v3")
    assert document["schemas"]["formal_root_budget_terminal"].endswith("-v2")
    assert document["schemas"]["closure_formal_manifest"].endswith("-v2")
    assert document["schemas"]["closure_result"].endswith("-v2")
    assert document["schemas"]["formal_launch_owner_broker_handoff_schema"] == (
        "noncert-cuts-ab16-formal-launch-owner-broker-handoff-v1"
    )
    assert document["schemas"]["manager_openfile_selection_binding_schema"] == (
        "noncert-cuts-ab16-budget-broker-manager-openfile-selection-binding-v1"
    )
    assert document["schemas"]["formal_closeout_owner_broker_handoff_schema"] == (
        "noncert-cuts-ab16-formal-closeout-owner-broker-handoff-v1"
    )
    assert {
        key: document["schemas"][key]
        for key in (
            "bootstrap_retained_directory_handoff",
            "bootstrap_staging_handoff",
            "bootstrap_budget_account_handoff",
            "bootstrap_structural_handoff",
        )
    } == {
        "bootstrap_retained_directory_handoff": (
            "noncert-cuts-ab16-bootstrap-retained-directory-handoff-v1"
        ),
        "bootstrap_staging_handoff": (
            "noncert-cuts-ab16-bootstrap-staging-handoff-v1"
        ),
        "bootstrap_budget_account_handoff": (
            "noncert-cuts-ab16-bootstrap-budget-account-handoff-v1"
        ),
        "bootstrap_structural_handoff": (
            "noncert-cuts-ab16-bootstrap-structural-handoff-v1"
        ),
    }
    assert cohort.validate_prospective_cohort(document) is document


def test_current_matrix_is_separate_replay_only_and_does_not_authorize_a039() -> None:
    historical = cohort.expanded_historical_cohort()
    prospective = cohort.expanded_prospective_cohort()

    assert historical["cohort_id"] == "noncert-cuts-ab16-current-authority-cohort-v1"
    assert historical["launch_ready"] is False
    assert historical["historical_replay_only"] is True
    assert historical["immutable_roots_are_bound_to_own_pinned_bytes"] is True
    assert historical["immutable_roots"] == [
        "A031",
        "A032",
        "A033",
        "A034",
        "A035",
        "A036",
        "A037",
        "A038",
    ]
    assert historical["schemas"] is not prospective["schemas"]
    assert historical["schemas"]["gate_b_approval"].endswith("-v5")
    assert prospective["schemas"]["gate_b_approval"].endswith("-v7")
    assert historical["schemas"]["markerless_incomplete"] == (
        "noncert-cuts-ab16-formal-markerless-incomplete-v1"
    )
    assert prospective["schemas"]["formal_markerless_incomplete"] == (
        "noncert-cuts-ab16-formal-markerless-incomplete-v2"
    )
    assert "A039" not in historical["immutable_roots"]


@pytest.mark.parametrize(
    "mutation",
    (
        "omit",
        "unknown",
        "legacy_mix",
        "role_mix",
        "launch_ready",
    ),
)
def test_prospective_cohort_rejects_any_omission_addition_or_mix(mutation: str) -> None:
    document = cohort.expanded_prospective_cohort()

    if mutation == "omit":
        del document["schemas"]["arm_attempt_root_replay"]
    elif mutation == "unknown":
        document["schemas"]["auxiliary_unversioned_escape"] = "noncert-cuts-ab16-unknown-v1"
    elif mutation == "legacy_mix":
        document["schemas"]["gate_b_approval"] = cohort.HISTORICAL_ACCEPTED_SCHEMAS["gate_b_approval"]
    elif mutation == "role_mix":
        document["package_roles"]["independent_verifier"] = "ambient_repository_verifier"
    else:
        document["launch_ready"] = True

    with pytest.raises(cohort.CohortContractError):
        cohort.validate_no_cross_cohort_mix(document)


def test_every_changed_historical_discriminator_fails_when_substituted() -> None:
    shared_keys = set(cohort.HISTORICAL_ACCEPTED_SCHEMAS) & set(cohort.PROSPECTIVE_SCHEMAS)
    changed_keys = {
        key
        for key in shared_keys
        if cohort.HISTORICAL_ACCEPTED_SCHEMAS[key] != cohort.PROSPECTIVE_SCHEMAS[key]
    }
    assert changed_keys

    for key in changed_keys:
        document = cohort.expanded_prospective_cohort()
        document["schemas"][key] = cohort.HISTORICAL_ACCEPTED_SCHEMAS[key]
        with pytest.raises(cohort.CohortContractError, match=rf"\.schemas\.{key}: value drifted"):
            cohort.validate_prospective_cohort(document)


@pytest.mark.parametrize(
    ("key", "incompatible_schema"),
    (
        (
            "stage_resource_admission",
            "noncert-cuts-ab16-stage-resource-admission-v2",
        ),
        (
            "formal_root_budget_terminal",
            "noncert-cuts-ab16-formal-root-budget-terminal-v1",
        ),
        (
            "closure_formal_manifest",
            "noncert-cuts-ab16-formal-manifest-v1",
        ),
        (
            "closure_result",
            "noncert-cuts-ab16-closure-result-v1",
        ),
        (
            "formal_launch_owner_broker_handoff_schema",
            "noncert-cuts-ab16-formal-launch-owner-broker-handoff-v0",
        ),
        (
            "manager_openfile_selection_binding_schema",
            "noncert-cuts-ab16-budget-broker-manager-openfile-selection-binding-v0",
        ),
        (
            "formal_closeout_owner_broker_handoff_schema",
            "noncert-cuts-ab16-formal-closeout-owner-broker-handoff-v0",
        ),
    ),
)
def test_prospective_resource_and_handoff_cohort_rejects_cross_version_mix(
    key: str,
    incompatible_schema: str,
) -> None:
    document = cohort.expanded_prospective_cohort()
    document["schemas"][key] = incompatible_schema

    with pytest.raises(
        cohort.CohortContractError,
        match=rf"\.schemas\.{key}: value drifted",
    ):
        cohort.validate_prospective_cohort(document)


def test_schema_bindings_match_actual_named_producer_and_consumer_constants() -> None:
    assert len(set(cohort.PROSPECTIVE_SCHEMAS.values())) == len(
        cohort.PROSPECTIVE_SCHEMAS
    ), "each prospective discriminator must have exactly one cohort key"
    assert set(cohort.PROSPECTIVE_SCHEMA_BINDINGS) == set(cohort.PROSPECTIVE_SCHEMAS)
    assert set(cohort.PROSPECTIVE_SCHEMA_PRODUCERS) == set(cohort.PROSPECTIVE_SCHEMAS)
    assert set(cohort.PROSPECTIVE_SCHEMA_CONSUMERS) <= set(cohort.PROSPECTIVE_SCHEMAS)

    source_paths = _prospective_source_paths()
    assignment_locations = _schema_assignment_locations(source_paths)
    failures: list[str] = []
    expanded: dict[str, dict[str, object]] = {}
    declared_by_schema: dict[str, set[SchemaLocation]] = defaultdict(set)
    for key, schema in cohort.PROSPECTIVE_SCHEMAS.items():
        binding = cohort.PROSPECTIVE_SCHEMA_BINDINGS[key]
        if set(binding) != {"schema", "producer", "consumers"}:
            failures.append(f"{key}: binding keys are {sorted(binding)}")
            continue
        if binding["schema"] != schema:
            failures.append(f"{key}: binding schema is {binding['schema']!r}, expected {schema!r}")
            continue
        producer = cast(SchemaLocation, binding["producer"])
        consumers = cast(tuple[SchemaLocation, ...], binding["consumers"])
        if producer in consumers or len(set(consumers)) != len(consumers):
            failures.append(f"{key}: producer/consumer locations are not disjoint and unique")
            continue
        actual = assignment_locations.get(schema, set())
        declared = {producer, *consumers}
        missing = sorted(declared - actual)
        if missing:
            failures.append(
                f"{key}: bound constants are absent or do not equal {schema}: {missing}"
            )
        declared_by_schema[schema].update(declared)
        expanded[key] = _binding_with_consumers(key)

    for schema, actual in sorted(assignment_locations.items()):
        if schema not in set(cohort.PROSPECTIVE_SCHEMAS.values()):
            continue
        undeclared = sorted(actual - declared_by_schema[schema])
        if undeclared:
            failures.append(f"{schema}: undeclared producer/consumer constants: {undeclared}")

    assert not failures, "\n".join(failures)
    assert set(expanded) == set(cohort.PROSPECTIVE_SCHEMAS)
    assert all(
        cast(dict[str, object], binding)["producer"]
        not in cast(list[SchemaLocation], binding["consumers"])
        for binding in expanded.values()
    )


def test_reverse_schema_scan_has_only_registered_prospective_or_explicit_historical_literals() -> None:
    source_paths = _prospective_source_paths()
    occurrences = _schema_literal_occurrences(source_paths)
    prospective = set(cohort.PROSPECTIVE_SCHEMAS.values())
    allowed = (
        prospective
        | set(cohort.HISTORICAL_SCHEMA_LITERAL_ALLOWLIST)
        | set(cohort.COHORT_METADATA_LITERAL_ALLOWLIST)
    )

    unknown = {
        schema: sorted(locations)
        for schema, locations in occurrences.items()
        if schema not in allowed
    }
    assert not unknown, f"unregistered AB16 package schema literals: {unknown}"


def test_bootstrap_authority_and_cohort_package_roles_are_exactly_joined() -> None:
    bootstrap = _bootstrap_tool_files()
    authority = _authority_ab16_tool_files()
    source_paths = _prospective_source_paths()
    assignment_locations = _schema_assignment_locations(source_paths)

    required = set(cohort.PROSPECTIVE_REQUIRED_PACKAGE_TOOL_FILES)
    required.update(
        role.removeprefix("tool.")
        for binding in cohort.PROSPECTIVE_SCHEMA_BINDINGS.values()
        for role in (cast(SchemaLocation, binding["producer"])[0],)
    )
    required.update(
        role.removeprefix("tool.")
        for binding in cohort.PROSPECTIVE_SCHEMA_BINDINGS.values()
        for role, _constant in cast(tuple[SchemaLocation, ...], binding["consumers"])
    )
    required.update(
        role.removeprefix("tool.")
        for locations in assignment_locations.values()
        for role, _constant in locations
    )

    missing_bootstrap = sorted(required - bootstrap)
    missing_authority = sorted(required - authority)
    bootstrap_only = sorted(bootstrap - authority)
    authority_only = sorted(authority - bootstrap)
    failures = [
        message
        for members, message in (
            (
                missing_bootstrap,
                f"AB16_SCRIPT_TOOL_FILES missing prospective roles: {missing_bootstrap}",
            ),
            (
                missing_authority,
                f"REQUIRED_PACKAGE_ROLES missing prospective roles: {missing_authority}",
            ),
            (bootstrap_only, f"bootstrap-only AB16 tool roles: {bootstrap_only}"),
            (authority_only, f"authority-only AB16 tool roles: {authority_only}"),
        )
        if members
    ]
    assert not failures, "\n".join(failures)


def test_root_and_outside_replay_closure_are_non_self_referential_and_closed() -> None:
    document = cohort.expanded_prospective_cohort()
    root = document["root_closure"]
    outside = document["outside_replay_closure"]

    assert root == {
        "fixed_terminal_member_kind": "manifest",
        "exact_member_formula": (
            "manifest_entry_paths UNION {fixed_manifest_path} == complete_root_descendant_paths"
        ),
        "manifest_path_excluded_from_entries": True,
        "manifest_contains_own_sha256": False,
        "manifest_contains_own_size": False,
        "entries_bind_node_type": True,
        "regular_entries_bind_mode_size_sha256": True,
        "directory_entries_bind_mode": True,
        "symlinks_allowed": False,
        "special_nodes_allowed": False,
        "writes_after_manifest": False,
    }
    assert outside == {
        "fixed_terminal_member_kind": "receipt",
        "exact_member_formula": (
            "receipt_manifest_entry_paths UNION {fixed_receipt_path} "
            "== complete_replay_root_descendant_paths"
        ),
        "receipt_path_excluded_from_entries": True,
        "receipt_contains_own_sha256": False,
        "receipt_contains_own_size": False,
        "entries_bind_node_type": True,
        "regular_entries_bind_mode_size_sha256": True,
        "directory_entries_bind_mode": True,
        "symlinks_allowed": False,
        "special_nodes_allowed": False,
        "writes_after_receipt": False,
    }

    for field in ("root_closure", "outside_replay_closure"):
        tampered = copy.deepcopy(document)
        tampered[field]["writes_after_manifest" if field == "root_closure" else "writes_after_receipt"] = True
        with pytest.raises(cohort.CohortContractError):
            cohort.validate_prospective_cohort(tampered)


def test_all_authority_expansion_flags_remain_false() -> None:
    document = cohort.expanded_prospective_cohort()

    assert document["authority_flags"] == {
        "changes_upper_bound": False,
        "changes_lower_bound": False,
        "cut_authority": False,
        "whole_witness_authority": False,
        "production_authority": False,
        "certified_authority": False,
        "stage_b_promotion_authority": False,
    }
    assert all(value is False for value in document["authority_flags"].values())


def test_project_lock_registers_every_prospective_schema_without_auxiliary_escape() -> None:
    lock_text = (ROOT / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    section = lock_text.split(
        "The prospective resource-budget authority-readiness cohort is exactly",
        maxsplit=1,
    )[1].split(
        "The terminal-reference history freeze remains",
        maxsplit=1,
    )[0]
    normalized_section = " ".join(section.split())
    registered = {
        token
        for token in re.findall(r"`([^`]+)`", section)
        if SCHEMA_LITERAL_RE.fullmatch(token) is not None
    }
    registered.difference_update(cohort.COHORT_METADATA_LITERAL_ALLOWLIST)
    expected = set(cohort.PROSPECTIVE_SCHEMAS.values())
    missing = sorted(expected - registered)
    unexpected = sorted(registered - expected)

    assert "`noncert-cuts-ab16-resource-budget-authority-readiness-v1`" in section
    assert "`launch_ready=false`" in section
    assert "There is no auxiliary-schema escape" in normalized_section
    assert "`tool.package_independent_verifier_v1.py`" in section
    assert "`tool.ab16_native_budget_helper_v1.py`" in section
    assert "`tool.ab16_final_release_actor_v1.py`" in section
    assert "`system.native_budget_helper.bin`" in section
    assert not missing and not unexpected, (
        "PROJECT_LOCK prospective schema matrix drifted: "
        f"missing={missing}, unexpected={unexpected}"
    )


def test_project_lock_fixes_the_post_raw_release_refunit_order() -> None:
    section = (ROOT / "PROJECT_LOCK.md").read_text(
        encoding="utf-8"
    ).split(
        "The formal supervisor retains all three locks",
        maxsplit=1,
    )[1].split(
        "Gate A remains non-authorizing for Gate B",
        maxsplit=1,
    )[0]
    normalized = " ".join(section.split())
    sequence = (
        "same persistent manager connection",
        "supervisor raw-lock-release receipt",
        "exact-once `UnrefUnit`",
        "post-Unref cgroup/PID absence",
        "manager-owner and client unique names",
        "connection-close receipt",
        "`dual-lock-release` or incomplete",
    )
    offsets = [normalized.index(marker) for marker in sequence]

    assert offsets == sorted(offsets)
    assert "Any reply, connection-close, or receipt uncertainty is `INCOMPLETE`" in normalized
