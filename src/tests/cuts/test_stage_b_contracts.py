"""RFC-001 Stage B0 contract shells.

The AST guard is effective immediately.  Runtime contracts for the Stage-B
types are strict xfails until the implementation batch named in each reason
lands; imports intentionally stay inside those tests.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import inspect
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
TESTS_ROOT = SRC_ROOT / "tests"

_BSTATE_STATIC_ARTIFACT_FIELDS = frozenset(
    {
        "canonical_rules",
        "candidate_placements",
        "facility_templates",
        "instance_to_facility_type",
    }
)
_FORBIDDEN_PRODUCTION_SYMBOLS = frozenset({"_SNAPSHOT_CONSTRUCTION_TOKEN"})
_PRIVATE_SYMBOL_OWNER_FILES = {
    "_SNAPSHOT_CONSTRUCTION_TOKEN": "src/cuts/state_snapshot.py",
}
_PRIVATE_SYMBOL_OWNER_SCOPES = {
    "_SNAPSHOT_CONSTRUCTION_TOKEN": frozenset(
        {
            ("ValidatedStateSnapshot", "__init__"),
            (None, "build_validated_state_snapshot"),
        }
    ),
}
# Deliberately field-name based instead of attempting static BState type
# resolution.  A same-named attribute on another type may be a false positive;
# the conservative breadth is intentional at this trust boundary.
_MUTATION_METHODS = frozenset(
    {
        "__delitem__",
        "__iand__",
        "__ior__",
        "__isub__",
        "__ixor__",
        "__setitem__",
        "add",
        "append",
        "clear",
        "difference_update",
        "discard",
        "extend",
        "insert",
        "intersection_update",
        "pop",
        "popitem",
        "remove",
        "reverse",
        "setdefault",
        "sort",
        "symmetric_difference_update",
        "update",
    }
)


def _stage_b_missing(module_path: str, symbol: str | None = None) -> bool:
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError:
        return True
    if spec is None:
        return True
    if symbol is None:
        return False
    module = importlib.import_module(module_path)
    return not hasattr(module, symbol)


def _stage_b5_apply_missing() -> bool:
    # Coarse B5 beacon: once the resolver lands, every B5 assertion executes.
    # Do not use the exact step_8 signature as the condition, or a bad signature
    # would remain xfailed forever instead of turning red.
    return _stage_b_missing("src.cuts.lifecycle", "_resolve_model_scope_binding")


def _stage_b5b_atomic_lowering_missing() -> bool:
    # B5b beacon (split from the coarse B5 beacon in the functional-rewire
    # sub-batch): the failed-apply atomicity contract (§4.11 precheck 前移)
    # cannot hold while the only delegate lowering path is the legacy,
    # non-atomic add_region_capacity_cut — a rejected cut still mutates the
    # master proto until B5b lands the atomic _lower_region_capacity_cut.
    try:
        from src.models.exact_coordinate_master import CoordinateExactMasterDelegate
    except ModuleNotFoundError:
        return True
    return not hasattr(CoordinateExactMasterDelegate, "_lower_region_capacity_cut")


def _literal_artifact_field(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in _BSTATE_STATIC_ARTIFACT_FIELDS:
            return node.value
    return None


def _references_static_artifact_target(
    node: ast.AST,
    aliases: frozenset[str] = frozenset(),
) -> bool:
    """Follow only the assigned/updated value path, never subscript keys."""

    if isinstance(node, ast.Name):
        return node.id in aliases
    if isinstance(node, ast.Attribute):
        return node.attr in _BSTATE_STATIC_ARTIFACT_FIELDS or _references_static_artifact_target(node.value, aliases)
    if isinstance(node, ast.Subscript):
        return _references_static_artifact_target(node.value, aliases)
    if isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and _literal_artifact_field(node.args[1]) is not None
        ):
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "setdefault"}:
            return _references_static_artifact_target(node.func.value, aliases)
    if isinstance(node, ast.Starred):
        return _references_static_artifact_target(node.value, aliases)
    if isinstance(node, (ast.List, ast.Tuple)):
        return any(_references_static_artifact_target(item, aliases) for item in node.elts)
    return False


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.List, ast.Tuple)):
        return set().union(*(_assigned_names(item) for item in target.elts))
    if isinstance(target, ast.Starred):
        return _assigned_names(target.value)
    return set()


class _ArtifactMutationAnalyzer(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[str] = []
        self._alias_scopes: list[set[str]] = [set()]
        self._function_scopes: list[str | None] = [None]
        self._class_scopes: list[str | None] = [None]

    @property
    def _aliases(self) -> set[str]:
        return self._alias_scopes[-1]

    def _record(self, node: ast.AST, kind: str) -> None:
        self.violations.append(f"{self.filename}:{node.lineno}: {kind}: {ast.unparse(node)}")

    def _record_forbidden_symbol(self, node: ast.AST, symbol: str) -> None:
        if (
            self.filename == _PRIVATE_SYMBOL_OWNER_FILES[symbol]
            and (self._class_scopes[-1], self._function_scopes[-1]) in _PRIVATE_SYMBOL_OWNER_SCOPES[symbol]
        ):
            return
        self._record(node, f"ForbiddenSymbol.{symbol}")

    def _target_is_artifact(self, target: ast.AST, *, allow_bare_alias: bool = False) -> bool:
        if isinstance(target, ast.Name):
            return allow_bare_alias and target.id in self._aliases
        if isinstance(target, ast.Starred):
            return self._target_is_artifact(target.value, allow_bare_alias=allow_bare_alias)
        if isinstance(target, (ast.List, ast.Tuple)):
            return any(self._target_is_artifact(item, allow_bare_alias=allow_bare_alias) for item in target.elts)
        return _references_static_artifact_target(target, frozenset(self._aliases))

    def _refresh_aliases(self, targets: list[ast.AST], value: ast.AST) -> None:
        # One-hop only: aliases of aliases are deliberately not propagated.
        aliases_artifact = _references_static_artifact_target(value)
        for target in targets:
            for name in _assigned_names(target):
                if aliases_artifact:
                    self._aliases.add(name)
                else:
                    self._aliases.discard(name)

    def _visit_definition_header(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        for field_name, value in ast.iter_fields(node):
            if field_name == "body":
                continue
            if isinstance(value, ast.AST):
                self.visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)

    def _visit_function_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._alias_scopes.append(set())
        self._function_scopes.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self._function_scopes.pop()
        self._alias_scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition_header(node)
        self._visit_function_body(node)
        self._aliases.discard(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition_header(node)
        self._visit_function_body(node)
        self._aliases.discard(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Defaults execute in the enclosing scope; the body is a deferred
        # callable and must not inherit a private-symbol owner exemption.
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        lambda_aliases = set(self._aliases)
        parameter_names = {
            argument.arg
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            )
        }
        if node.args.vararg is not None:
            parameter_names.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            parameter_names.add(node.args.kwarg.arg)
        lambda_aliases.difference_update(parameter_names)
        self._alias_scopes.append(lambda_aliases)
        self._function_scopes.append("<lambda>")
        self.visit(node.body)
        self._function_scopes.pop()
        self._alias_scopes.pop()

    def _visit_comprehension_scope(
        self,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
        *,
        scope_name: str,
        result_nodes: tuple[ast.AST, ...],
    ) -> None:
        generators = list(node.generators)
        if not generators:
            return
        # Python evaluates the outermost iterable in the enclosing scope.
        self.visit(generators[0].iter)
        self._alias_scopes.append(set(self._aliases))
        self._function_scopes.append(scope_name)
        self._aliases.difference_update(_assigned_names(generators[0].target))
        for condition in generators[0].ifs:
            self.visit(condition)
        for generator in generators[1:]:
            self.visit(generator.iter)
            self._aliases.difference_update(_assigned_names(generator.target))
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)
        self._function_scopes.pop()
        self._alias_scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<listcomp>", result_nodes=(node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<setcomp>", result_nodes=(node.elt,))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(node, scope_name="<genexpr>", result_nodes=(node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<dictcomp>", result_nodes=(node.key, node.value))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition_header(node)
        self._alias_scopes.append(set())
        self._class_scopes.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self._class_scopes.pop()
        self._alias_scopes.pop()
        self._aliases.discard(node.name)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if self._target_is_artifact(target):
                self._record(node, "Assign")
        self.visit(node.value)
        self._refresh_aliases(list(node.targets), node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        if self._target_is_artifact(node.target):
            self._record(node, "AnnAssign")
        if node.value is not None:
            self.visit(node.value)
            self._refresh_aliases([node.target], node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if self._target_is_artifact(node.target, allow_bare_alias=True):
            self._record(node, "AugAssign")
        self.visit(node.value)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            if self._target_is_artifact(target):
                self._record(node, "Delete")
            self._aliases.difference_update(_assigned_names(target))

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self._aliases.difference_update(_assigned_names(node.target))
        for statement in (*node.body, *node.orelse):
            self.visit(statement)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        aliases_before = set(self._aliases)
        self._alias_scopes[-1] = set(aliases_before)
        for statement in node.body:
            self.visit(statement)
        aliases_body = set(self._aliases)
        self._alias_scopes[-1] = set(aliases_before)
        for statement in node.orelse:
            self.visit(statement)
        aliases_else = set(self._aliases)
        self._alias_scopes[-1] = aliases_body | aliases_else

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in _FORBIDDEN_PRODUCTION_SYMBOLS:
            self._record_forbidden_symbol(node, node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load) and node.attr in _FORBIDDEN_PRODUCTION_SYMBOLS:
            self._record_forbidden_symbol(node, node.attr)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for imported in node.names:
            if imported.name in _FORBIDDEN_PRODUCTION_SYMBOLS:
                self._record_forbidden_symbol(node, imported.name)

    def visit_Call(self, node: ast.Call) -> None:
        aliases = frozenset(self._aliases)
        func = node.func
        if (
            isinstance(func, ast.Name)
            and func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in _FORBIDDEN_PRODUCTION_SYMBOLS
        ):
            self._record_forbidden_symbol(node, node.args[1].value)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in _MUTATION_METHODS
            and _references_static_artifact_target(func.value, aliases)
        ):
            self._record(node, f"Call.{func.attr}")
        elif (
            isinstance(func, ast.Name)
            and func.id in {"setattr", "delattr"}
            and len(node.args) >= 2
            and _literal_artifact_field(node.args[1]) is not None
        ):
            self._record(node, f"Call.{func.id}")
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in {"__setattr__", "__delattr__"}
            and node.args
            and _literal_artifact_field(node.args[0]) is not None
        ):
            self._record(node, f"Call.{func.attr}")
        elif (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "operator"
            and func.attr in {"setitem", "delitem"}
            and node.args
            and _references_static_artifact_target(node.args[0], aliases)
        ):
            self._record(node, f"Call.operator.{func.attr}")
        self.generic_visit(node)


def _artifact_mutation_violations(source: str, *, filename: str) -> list[str]:
    analyzer = _ArtifactMutationAnalyzer(filename)
    analyzer.visit(ast.parse(source, filename=filename))
    return analyzer.violations


def _production_python_files() -> list[Path]:
    return [path for path in sorted(SRC_ROOT.rglob("*.py")) if path != TESTS_ROOT and TESTS_ROOT not in path.parents]


def test_bstate_static_artifacts_and_snapshot_token_have_no_production_escapes() -> None:
    """B0 immediately effective; production was clean when scanned 2026-07-11."""

    # B0 立即生效，生产现状为净（2026-07-11 已扫描验证）。
    violations: list[str] = []
    production_files = _production_python_files()

    for path in production_files:
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        violations.extend(_artifact_mutation_violations(path.read_text(encoding="utf-8"), filename=relative_path))

    assert production_files, "production AST scan unexpectedly covered no Python files"
    assert SRC_ROOT / "cuts" / "lifecycle.py" in production_files
    assert not violations, "Stage-B production AST violation(s) found:\n" + "\n".join(violations)


def test_static_artifact_analyzer_catches_alias_and_reflection_escapes() -> None:
    attacks = """
import operator

def attack(state):
    cp = state.candidate_placements
    cp["pool"] = {}
    cp.update({"x": 1})
    del cp["pool"]
    def nested(value=cp.pop("default-time")):
        return value
    cp = {}
    cp.update({"local_only": 1})
    setattr(state, "canonical_rules", {})
    delattr(state, "facility_templates")
    state.__setattr__("instance_to_facility_type", {})
    state.__delattr__("canonical_rules")
    getattr(state, "candidate_placements")["pool"] = []
    getattr(state, "facility_templates").clear()
    operator.setitem(state.canonical_rules, "x", 1)
    operator.delitem(state.instance_to_facility_type, "x")
"""
    violations = _artifact_mutation_violations(attacks, filename="attacks.py")
    rendered = "\n".join(violations)
    assert len(violations) == 12, rendered
    for escape in (
        "cp['pool'] = {}",
        "cp.update",
        "del cp",
        "default-time",
        "setattr(state",
        "delattr(state",
        "state.__setattr__",
        "state.__delattr__",
        "getattr(state",
        "operator.setitem",
        "operator.delitem",
    ):
        assert escape in rendered

    legitimate_reads = """
def inspect_artifacts(state, container):
    cp = state.candidate_placements
    first = cp.get("facility_pools")
    cp = {}
    cp.update({"local_only": 1})
    container[state.canonical_rules] = first
    return state.facility_templates, first
"""
    assert _artifact_mutation_violations(legitimate_reads, filename="legitimate_reads.py") == []

    token_attacks = """
from src.cuts.state_snapshot import _SNAPSHOT_CONSTRUCTION_TOKEN as leaked_token
import src.cuts.state_snapshot as snapshot_module

direct = _SNAPSHOT_CONSTRUCTION_TOKEN
via_module = snapshot_module._SNAPSHOT_CONSTRUCTION_TOKEN
via_getattr = getattr(snapshot_module, "_SNAPSHOT_CONSTRUCTION_TOKEN")
"""
    token_violations = _artifact_mutation_violations(token_attacks, filename="src/cuts/token_attack.py")
    rendered_tokens = "\n".join(token_violations)
    assert len(token_violations) == 4, rendered_tokens
    assert "from src.cuts.state_snapshot import _SNAPSHOT_CONSTRUCTION_TOKEN" in rendered_tokens
    assert "token_attack.py:5: ForbiddenSymbol._SNAPSHOT_CONSTRUCTION_TOKEN" in rendered_tokens
    assert "snapshot_module._SNAPSHOT_CONSTRUCTION_TOKEN" in rendered_tokens
    assert "getattr(snapshot_module, '_SNAPSHOT_CONSTRUCTION_TOKEN')" in rendered_tokens

    owner_source = """
_SNAPSHOT_CONSTRUCTION_TOKEN = object()

class ValidatedStateSnapshot:
    def __init__(self):
        return _SNAPSHOT_CONSTRUCTION_TOKEN

def build_validated_state_snapshot():
    return _SNAPSHOT_CONSTRUCTION_TOKEN
"""
    assert (
        _artifact_mutation_violations(
            owner_source,
            filename="src/cuts/state_snapshot.py",
        )
        == []
    )

    owner_leak = """
class OtherSnapshot:
    def __init__(self):
        return _SNAPSHOT_CONSTRUCTION_TOKEN
"""
    owner_violations = _artifact_mutation_violations(
        owner_leak,
        filename="src/cuts/state_snapshot.py",
    )
    assert len(owner_violations) == 1, owner_violations


# ---------------------------------------------------------------------------
# B5b §4.10 / §7 拍板 4: _coordinate_delegate acquisition lockdown.
#
# After the master framework-cut API is privatised to ``_lower_*``, the sole
# sanctioned mutation path is: typed_apply → facade ``_lower_*`` → getattr on
# ``self._coordinate_delegate`` → backend ``_lower_*``.  Acquiring the delegate
# handle anywhere else lets code call the private backend ``_lower_*`` directly,
# bypassing both the facade guard and the typed chain.  This guard pins EVERY
# current delegate acquisition (both ``x._coordinate_delegate`` attribute reads
# and ``getattr(x, "_coordinate_delegate")`` reflection) across all production
# files; any NEW acquisition — the only way to reach the private backend outside
# the facade — turns this test red until it is reviewed and allowlisted.  This
# batch grandfathers the existing surface (本批不清理既有面,只封新增); the three
# facade ``_lower_*`` methods are the owner scope and are exempt (照
# ``_PRIVATE_SYMBOL_OWNER_SCOPES``).  Assigning to ``self._coordinate_delegate``
# (Store) is the delegate's birth site, not an acquisition, and is not counted.
# ---------------------------------------------------------------------------

_COORDINATE_DELEGATE_ATTR = "_coordinate_delegate"

_COORDINATE_DELEGATE_OWNER_EXEMPT = frozenset(
    {
        ("src/models/master_model.py", "MasterPlacementModel", "_lower_region_capacity_cut"),
        ("src/models/master_model.py", "MasterPlacementModel", "_lower_baseline_packing_cut"),
        ("src/models/master_model.py", "MasterPlacementModel", "_lower_power_pose_exclusion_cut"),
    }
)

_COORDINATE_DELEGATE_ACQUISITION_ALLOWLIST: "Counter[tuple[str, str | None, str | None]]" = Counter(
    {
        ("src/cuts/lifecycle.py", None, "_live_master_domain_projection"): 1,
        ("src/models/master_model.py", "MasterPlacementModel", "_validate_coordinate_forced_hint"): 2,
        ("src/models/master_model.py", "MasterPlacementModel", "add_benders_cut"): 2,
        ("src/models/master_model.py", "MasterPlacementModel", "apply_master_hints"): 2,
        ("src/models/master_model.py", "MasterPlacementModel", "build"): 7,
        ("src/models/master_model.py", "MasterPlacementModel", "build_exact_candidate_warm_start"): 3,
        ("src/models/master_model.py", "MasterPlacementModel", "build_exact_core"): 2,
        ("src/models/master_model.py", "MasterPlacementModel", "extract_master_hints"): 2,
        ("src/models/master_model.py", "MasterPlacementModel", "extract_solution"): 2,
        ("src/models/master_model.py", "MasterPlacementModel", "from_exact_core"): 10,
        ("src/models/master_model.py", "MasterPlacementModel", "solve"): 2,
        ("src/models/master_model.py", None, "evaluate_ghost_overlap_forced_domain_conflict"): 1,
        ("src/models/master_model.py", None, "evaluate_ghost_y_overlap_forced_label_conflict"): 1,
        ("src/models/master_model.py", None, "evaluate_same_x_strip_fixed_ghost_capacity_conflict"): 1,
        ("src/models/master_model.py", None, "evaluate_signature_monotonic_forced_label_conflict"): 1,
        ("src/search/benders_loop.py", "LBBDController", "_run_certified_exact"): 2,
        ("src/search/benders_loop.py", "LBBDController", "_run_exact_binding_and_routing"): 9,
        ("src/search/benders_loop.py", None, "run_benders_for_ghost_rect"): 1,
        (
            "src/search/phase3b/active_guard/proto_shape_audit.py",
            None,
            "build_phase3b_active_guard_proto_shape_audit",
        ): 1,
        ("src/search/phase3b/anchor119/mixed_lane_tiling_verifier.py", None, "_build_model"): 1,
        ("src/search/phase3b/anchor_inventory/domain_inventory.py", None, "_mandatory_group_domain_entry"): 3,
        ("src/search/phase3b/anchor_inventory/domain_inventory.py", None, "_optional_domain_entries"): 1,
        ("src/search/phase3b/anchor_inventory/dynamic_coupling_audit.py", None, "_anchor_dynamic_profile"): 1,
        ("src/search/phase3b/anchor_inventory/dynamic_coupling_audit.py", None, "_model_profile"): 1,
        ("src/search/phase3b/anchor_inventory/packable_pole_audit.py", None, "_anchor_packable_profile"): 1,
        (
            "src/search/phase3b/coordinate_validation/capacity_cut_design.py",
            None,
            "build_phase3b_coordinate_validation_capacity_cut_design",
        ): 1,
        (
            "src/search/phase3b/coordinate_validation/global_family_delta.py",
            None,
            "build_phase3b_coordinate_validation_global_family_delta",
        ): 1,
        (
            "src/search/phase3b/coordinate_validation/no_overlap_subset_delta.py",
            None,
            "build_phase3b_coordinate_validation_no_overlap_subset_delta",
        ): 1,
        (
            "src/search/phase3b/coordinate_validation/target_ghost_capacity_repro.py",
            None,
            "build_phase3b_coordinate_validation_target_ghost_capacity_repro",
        ): 1,
        (
            "src/search/phase3b/coordinate_validation/x_domain_order_audit.py",
            None,
            "build_phase3b_coordinate_validation_x_domain_order_audit",
        ): 1,
        ("src/search/phase3b/cover/literal_scale_estimate.py", None, "_anchor_scale_estimate"): 1,
        ("src/search/phase3b/family_bound/audit.py", None, "_audit_anchor_family"): 2,
        ("src/search/phase3b/family_bound/audit.py", None, "_blocked_family_counts"): 1,
        ("src/search/phase3b/family_bound/audit.py", None, "_family_global_upper_bound"): 1,
        ("src/search/phase3b/family_bound/audit.py", None, "_family_sizes"): 1,
        ("src/search/phase3b/family_bound/audit.py", None, "_proto_constraint_payload"): 1,
        (
            "src/search/phase3b/family_lookup/assignment_audit.py",
            None,
            "build_phase3b_family_lookup_assignment_audit",
        ): 1,
        (
            "src/search/phase3b/family_lookup/encoding_equivalence.py",
            None,
            "build_phase3b_family_lookup_encoding_equivalence",
        ): 1,
        ("src/search/phase3b/family_lookup/medium_repro.py", None, "_medium_repro_extraction"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_custom_variant_disabled_indices"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_power_capacity_gvi_coefficients"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_power_family_channeling_slots"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_power_family_count_var_indices"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_power_family_shell_pair_table_payload"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_target_power_family_count_var_index"): 1,
        ("src/search/phase3b/forced_anchor/model_slice.py", None, "_variant_constraints"): 1,
        (
            "src/search/phase3b/forced_anchor/proto_reduction.py",
            None,
            "_add_power_coverage_selected_coord_literal_replacement",
        ): 1,
        (
            "src/search/phase3b/forced_anchor/proto_reduction.py",
            None,
            "_add_power_coverage_template_index_active_prefix_guard",
        ): 1,
        (
            "src/search/phase3b/forced_anchor/proto_reduction.py",
            None,
            "_add_power_coverage_template_index_restriction",
        ): 1,
        ("src/search/phase3b/mandatory_core/mandatory_core_encoding.py", None, "_encoding_payload"): 1,
        ("src/search/phase3b/mandatory_core/mandatory_core_matrix.py", None, "_residual_active_indices"): 1,
        ("src/search/phase3b/pose_order/greedy_pose_order_comparison.py", None, "_target_pose_xy"): 1,
        ("src/search/phase3b/power_coverage/witness_domain.py", None, "_anchor_witness_domain"): 1,
        ("src/search/phase3b/protocol/protocol_witness_prefix_audit.py", None, "_family_prefix_capacity_summary"): 1,
        ("src/search/phase3b/protocol/protocol_witness_prefix_audit.py", None, "_overlay_summary"): 1,
        ("src/search/phase3b/residual_optional/residual_optional_encoding.py", None, "_encoding_payload"): 1,
        ("src/search/phase3b/selected_block/equivalence.py", None, "_build_case"): 1,
        (
            "src/search/phase3b/signature_monotonic/forced_label_audit.py",
            None,
            "build_phase3b_signature_monotonic_forced_label_audit",
        ): 1,
        (
            "src/search/phase3b/signature_region/equivalence_audit.py",
            None,
            "build_phase3b_signature_region_equivalence_audit",
        ): 1,
    }
)


class _CoordinateDelegateAcquisitionCollector(ast.NodeVisitor):
    """Records every ``_coordinate_delegate`` acquisition (attribute read or
    ``getattr`` reflection), bucketed by (file, enclosing class, enclosing
    function).  Owner-scope acquisitions are dropped (照 ``_record_forbidden_symbol``).

    Threat-model boundary (B5b dual-review, both positions LOW): this is a
    review TRIPWIRE against *naturally written* new call sites — it matches only
    ``x._coordinate_delegate`` attribute loads and ``getattr(x, "<literal>")``.
    Dynamic reflection (``operator.attrgetter``, string concatenation, variable
    attribute names, ``vars()``/``__dict__``) escapes it by construction; a green
    run is NOT proof of absence.  The hard stops remain the runtime layers:
    ``EXACT_CUT_FRAMEWORK_ATTACH`` in the certified unsafe-map and the facade
    structure itself.  Same boundary applies to the ``_lower_*``/``
    _build_model_scope_binding`` caller pins in test_stage_b_typed_platform.py."""

    def __init__(self, filename: str, owner_exempt: frozenset[tuple[str, str | None, str | None]]) -> None:
        self.filename = filename
        self.owner_exempt = owner_exempt
        self.class_stack: list[str | None] = [None]
        self.function_stack: list[str | None] = [None]
        self.acquisitions: list[tuple[str, str | None, str | None, int]] = []

    def _visit_definition_header(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        for field_name, value in ast.iter_fields(node):
            if field_name == "body":
                continue
            if isinstance(value, ast.AST):
                self.visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition_header(node)
        self.class_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.class_stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._visit_definition_header(node)
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        self.function_stack.append("<lambda>")
        self.visit(node.body)
        self.function_stack.pop()

    def _visit_comprehension_scope(
        self,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
        *,
        scope_name: str,
        result_nodes: tuple[ast.AST, ...],
    ) -> None:
        generators = list(node.generators)
        if not generators:
            return
        # The outermost iterable is evaluated immediately by the enclosing
        # method. The loop body and remaining clauses run in the implicit scope.
        self.visit(generators[0].iter)
        self.function_stack.append(scope_name)
        for condition in generators[0].ifs:
            self.visit(condition)
        for generator in generators[1:]:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)
        self.function_stack.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<listcomp>", result_nodes=(node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<setcomp>", result_nodes=(node.elt,))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(node, scope_name="<genexpr>", result_nodes=(node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<dictcomp>", result_nodes=(node.key, node.value))

    def _record(self, node: ast.AST) -> None:
        key = (self.filename, self.class_stack[-1], self.function_stack[-1])
        if key in self.owner_exempt:
            return
        self.acquisitions.append((key[0], key[1], key[2], node.lineno))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load) and node.attr == _COORDINATE_DELEGATE_ATTR:
            self._record(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Name)
            and func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == _COORDINATE_DELEGATE_ATTR
        ):
            self._record(node)
        self.generic_visit(node)


_COORDINATE_DELEGATE_ACQUISITION_USE_DIGEST = "b6e16c15b0c3e99b8d20814aeae467850bebf335b0e7a508272101c73ce86109"


def _coordinate_delegate_acquisition_use_digest() -> str:
    records: list[tuple[str, str]] = []
    for path in _production_python_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        acquisitions: list[ast.AST] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and node.attr == _COORDINATE_DELEGATE_ATTR
            ):
                acquisitions.append(node)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == _COORDINATE_DELEGATE_ATTR
            ):
                acquisitions.append(node)
        for acquisition in acquisitions:
            context = acquisition
            while context in parents and not isinstance(context, ast.stmt):
                context = parents[context]
            records.append((relative, ast.dump(context, include_attributes=False)))
    payload = json.dumps(sorted(records), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_coordinate_delegate_acquisition_use_context_is_sealed() -> None:
    # Bucket counts alone permit an equal-count semantic replacement, such as
    # swapping a diagnostic read for delegate.model.Add(...). Seal the nearest
    # statement AST for every acquisition so that repurposing also turns red.
    #
    # This digest seals the *statement shape at each acquisition site*.  A
    # single-statement rewrite `self._coordinate_delegate.model.Add(c)` changes
    # the acquisition statement AST and turns this red.  The one-hop alias forms
    # `d = self._coordinate_delegate; d.model.Add(c)` and the nested-RHS
    # `d = ..._coordinate_delegate if cond else None; d.model.Add(c)` are caught by
    # its companion ``test_coordinate_delegate_alias_dataflow_is_sealed`` (B6-prep,
    # α2 attack-review + design-review MEDIUM-1).  Transitive multi-hop chains
    # (`d = <acq>; e = d; e.model.Add(c)`) remain unsealed by both digests — a
    # pre-promotion tripwire boundary, not a soundness hole; see that companion's
    # COVERAGE BOUNDARY note and the F-05 hard-gate (B6) checklist.
    assert _coordinate_delegate_acquisition_use_digest() == _COORDINATE_DELEGATE_ACQUISITION_USE_DIGEST


_COORDINATE_DELEGATE_ALIAS_USE_DIGEST = "158fd3f04b640bba34a78afae1b28241aaf91dd94139b6dcd82986977fcba283"


def _coordinate_delegate_alias_use_digest() -> str:
    """Seal the AST of every statement that *uses* a coordinate-delegate alias.

    α2 attack review found a coverage boundary in the acquisition-site digest:
    binding the delegate to a local name (`d = self._coordinate_delegate`) and
    then mutating through the alias in a separate statement (`d.model.Add(c)`)
    leaves the acquisition statement byte-identical, so the alias-use statement
    slips past the acquisition seal.  This digest closes the one-hop case by
    dataflow: for every acquisition that binds one or more names — directly or
    nested in the binding's RHS expression (IfExp/BoolOp/Call/getattr-method/
    comprehension, e.g. `d = self.master._coordinate_delegate if cond else None`;
    B6-prep design review MEDIUM-1) — it folds the normalized AST of every
    statement in the enclosing scope that loads any of those names.

    Over-inclusion is safe (it only tightens the seal): a name reused for an
    unrelated value after rebinding is still tracked; the seal is conservative
    by design, matching the α2 disposition ("重绑定后继续追新值来源不豁免").

    COVERAGE BOUNDARY (still open, within F-05's tripwire threat model, NOT a
    soundness hole): this seals *one-hop* aliases (name bound from an acquisition).
    A pre-existing *transitive* chain — `d = <acq>; e = d;` already in the tree —
    followed by a newly injected `e.model.Add(c)` is not caught: `e` is a
    second-hop alias, not bound from an acquisition, so its downstream uses are
    unsealed.  (A newly added `e = d` *is* caught — it loads the tracked name
    `d`.)  This residual is acceptable here because F-05 is a pre-promotion
    tripwire, not a certified soundness gate: under certified mode the typed
    attach is disabled (env unsafe-map), acquisitions live in phase3b diagnostic
    modules off the certified solve path, and any injection is a review-visible
    source edit.  **Promoting F-05 to a hard gate (B6) still requires full
    transitive alias-dataflow tracking** — registered in the F-05 promotion
    checklist (batch D spec §5) and the B6-prep spec §3.3.
    """
    records: set[tuple[str, str]] = set()
    for path in _production_python_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        def _nearest_stmt(node: ast.AST) -> ast.AST:
            context = node
            while context in parents and not isinstance(context, ast.stmt):
                context = parents[context]
            return context

        def _enclosing_scope(node: ast.AST) -> ast.AST:
            context = node
            while context in parents:
                context = parents[context]
                if isinstance(
                    context, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)
                ):
                    return context
            return tree

        def _is_acquisition(node: ast.AST) -> bool:
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and node.attr == _COORDINATE_DELEGATE_ATTR
            ):
                return True
            return (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == _COORDINATE_DELEGATE_ATTR
            )

        def _binding_targets(node: ast.AST) -> list[ast.AST]:
            # Walk up from the acquisition to the nearest binding statement/expr
            # (Assign / AnnAssign / NamedExpr) and, if the acquisition lies on its
            # *value* side (not a target), return the bound targets.  Walking up
            # — rather than only inspecting the direct parent — covers acquisitions
            # nested one level inside the RHS expression (IfExp / BoolOp / Call /
            # getattr-method / comprehension), e.g.
            # ``d = self.master._coordinate_delegate if cond else None``, which a
            # ``parent.value is node`` check misses.  Over-inclusion is safe.
            child = node
            binder = parents.get(node)
            while binder is not None:
                if isinstance(binder, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    if getattr(binder, "value", None) is child:
                        if isinstance(binder, ast.Assign):
                            return list(binder.targets)
                        return [binder.target]
                    return []
                if isinstance(
                    binder, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module, ast.ClassDef)
                ):
                    return []
                child = binder
                binder = parents.get(binder)
            return []

        # Pass 1: collect alias names bound from an acquisition (directly or
        # nested in the binding's RHS), keyed by their enclosing scope node.
        scope_alias_names: dict[int, set[str]] = {}
        scope_nodes: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            if not _is_acquisition(node):
                continue
            targets = _binding_targets(node)
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if not names:
                continue
            scope = _enclosing_scope(node)
            scope_alias_names.setdefault(id(scope), set()).update(names)
            scope_nodes[id(scope)] = scope

        # Pass 2: within each scope, seal every statement that loads an alias.
        for scope_id, names in scope_alias_names.items():
            scope = scope_nodes[scope_id]
            for sub in ast.walk(scope):
                if (
                    isinstance(sub, ast.Name)
                    and isinstance(sub.ctx, ast.Load)
                    and sub.id in names
                ):
                    stmt = _nearest_stmt(sub)
                    records.add(
                        (relative, ast.dump(stmt, include_attributes=False))
                    )
    payload = json.dumps(sorted(records), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def test_coordinate_delegate_alias_dataflow_is_sealed() -> None:
    # B6-prep (α2 attack-review + design-review MEDIUM-1 gap closure): seal the
    # one-hop alias dataflow of every coordinate-delegate acquisition, not just
    # the acquisition statement shape.  Any new/changed statement that reads a
    # delegate alias name — including the two-statement
    # `d = self._coordinate_delegate; d.model.Add(c)` form and the nested-RHS
    # binding `d = self.master._coordinate_delegate if cond else None` form — turns
    # this red.  Transitive multi-hop chains remain out of scope (see the digest
    # docstring's COVERAGE BOUNDARY; B6 hard-gate needs full transitive tracking).
    assert _coordinate_delegate_alias_use_digest() == _COORDINATE_DELEGATE_ALIAS_USE_DIGEST


def test_coordinate_delegate_acquisition_is_allowlisted() -> None:
    acquisitions: list[tuple[str, str | None, str | None, int]] = []
    production_files = _production_python_files()
    for path in production_files:
        relative = path.relative_to(REPO_ROOT).as_posix()
        collector = _CoordinateDelegateAcquisitionCollector(relative, _COORDINATE_DELEGATE_OWNER_EXEMPT)
        collector.visit(ast.parse(path.read_text(encoding="utf-8"), filename=relative))
        acquisitions.extend(collector.acquisitions)

    assert production_files, "production AST scan unexpectedly covered no Python files"
    actual: "Counter[tuple[str, str | None, str | None]]" = Counter(
        (filename, class_name, function_name) for filename, class_name, function_name, _line in acquisitions
    )
    drift = sorted(set(actual) ^ set(_COORDINATE_DELEGATE_ACQUISITION_ALLOWLIST))
    assert actual == _COORDINATE_DELEGATE_ACQUISITION_ALLOWLIST, (
        "new/moved _coordinate_delegate acquisition (allowlist drift):\n"
        + "\n".join(
            f"  {key}: allow={_COORDINATE_DELEGATE_ACQUISITION_ALLOWLIST.get(key, 0)} actual={actual.get(key, 0)}"
            for key in drift
        )
    )


def test_coordinate_delegate_acquisition_analyzer_catches_attribute_and_reflection() -> None:
    source = """
class Owner:
    def sanctioned(self):
        return self._coordinate_delegate  # exempt owner scope

def reach_attr(model):
    return model._coordinate_delegate

def reach_getattr(model):
    return getattr(model, "_coordinate_delegate", None)

def nested_getattr(model):
    return getattr(getattr(model, "_coordinate_delegate", None), "mandatory_slots", {})

def not_an_acquisition(obj):
    obj._coordinate_delegate = 1  # Store — the delegate's birth site, not a read
    return obj._other_attr  # non-target attribute
"""
    exempt = frozenset({("attack.py", "Owner", "sanctioned")})
    collector = _CoordinateDelegateAcquisitionCollector("attack.py", exempt)
    collector.visit(ast.parse(source, filename="attack.py"))
    got = Counter(
        (filename, class_name, function_name) for filename, class_name, function_name, _line in collector.acquisitions
    )
    assert got == Counter(
        {
            ("attack.py", None, "reach_attr"): 1,
            ("attack.py", None, "reach_getattr"): 1,
            ("attack.py", None, "nested_getattr"): 1,
        }
    ), got


def test_coordinate_delegate_owner_exemption_stops_at_deferred_scopes() -> None:
    source = """
class MasterPlacementModel:
    def _lower_region_capacity_cut(self):
        direct = self._coordinate_delegate
        late = lambda: self._coordinate_delegate
        generated = (self._coordinate_delegate for _ in range(1))
        listed = [self._coordinate_delegate for _ in range(1)]
        def nested():
            return self._coordinate_delegate
        class Inner:
            leaked = self._coordinate_delegate
        return direct, late, generated, listed, nested, Inner
"""
    exempt = frozenset(
        {
            (
                "attack.py",
                "MasterPlacementModel",
                "_lower_region_capacity_cut",
            )
        }
    )
    collector = _CoordinateDelegateAcquisitionCollector("attack.py", exempt)
    collector.visit(ast.parse(source, filename="attack.py"))
    got = Counter((class_name, function_name) for _filename, class_name, function_name, _line in collector.acquisitions)
    assert got == Counter(
        {
            ("MasterPlacementModel", "<lambda>"): 1,
            ("MasterPlacementModel", "<genexpr>"): 1,
            ("MasterPlacementModel", "<listcomp>"): 1,
            ("MasterPlacementModel", "nested"): 1,
            ("Inner", "_lower_region_capacity_cut"): 1,
        }
    )


def test_artifact_owner_exemption_stops_at_lambda_scope() -> None:
    source = """
class ValidatedStateSnapshot:
    def __init__(self):
        direct = _SNAPSHOT_CONSTRUCTION_TOKEN
        delayed = lambda: _SNAPSHOT_CONSTRUCTION_TOKEN
        return direct, delayed
"""
    violations = _artifact_mutation_violations(source, filename="src/cuts/state_snapshot.py")
    assert len(violations) == 1
    assert "<lambda>" not in violations[0]  # message records source, not scope
    assert "_SNAPSHOT_CONSTRUCTION_TOKEN" in violations[0]


def _mutable_stage_b_sources(
    bstate_type: Any,
    group_state_type: Any,
    *,
    ghost_rect: tuple[int, int, int, int] = (11, 17, 2, 3),
) -> dict[str, Any]:
    facility_templates = {
        "boundary_storage_port": {
            "placement_rule": "left_or_bottom_boundary",
            "dimensions": {"w": 1, "h": 3},
            "needs_power": False,
        }
    }
    canonical_rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": facility_templates,
    }
    candidate_placements = {
        "facility_pools": {
            "boundary_storage_port": [
                {
                    "pose_id": "boundary_pose_0",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 1], [0, 2], [0, 3]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ]
        }
    }
    instance_to_facility_type = {"boundary_io": "boundary_storage_port"}
    artifact_hashes = {
        "canonical_rules.json": "1" * 64,
        "candidate_placements.json": "2" * 64,
        "mandatory_exact_instances.json": "3" * 64,
    }
    x, y, width, height = ghost_rect
    ghost_cells = frozenset((cell_x, cell_y) for cell_x in range(x, x + width) for cell_y in range(y, y + height))
    state = bstate_type(
        groups={
            "boundary_io": group_state_type(
                group_id="boundary_io",
                demand=2,
                pose_domain=frozenset({"boundary_pose_0"}),
                selected_poses=[],
            )
        },
        cell_owner={(4, 4): ("boundary_io", 0)},
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset({(7, 0)}),
        artifact_hashes=artifact_hashes,
        available_oracle_versions=frozenset({"binding_empty_domain_v1", "region_capacity_v1"}),
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
        source_digest="4" * 64,
    )
    return {
        "artifact_hashes": artifact_hashes,
        "candidate_placements": candidate_placements,
        "canonical_rules": canonical_rules,
        "facility_templates": facility_templates,
        "instance_to_facility_type": instance_to_facility_type,
        "state": state,
    }


def _build_bundle(build_frozen_artifact_bundle: Any, sources: dict[str, Any]) -> Any:
    return build_frozen_artifact_bundle(
        canonical_rules=sources["canonical_rules"],
        candidate_placements=sources["candidate_placements"],
        facility_templates=sources["facility_templates"],
        instance_to_facility_type=sources["instance_to_facility_type"],
        artifact_hashes=sources["artifact_hashes"],
    )


def _mutate_builder_sources(sources: dict[str, Any]) -> None:
    sources["facility_templates"]["boundary_storage_port"]["dimensions"]["w"] = 99
    sources["facility_templates"]["boundary_storage_port"]["placement_rule"] = "free"
    sources["candidate_placements"]["facility_pools"]["boundary_storage_port"][0]["occupied_cells"].append([69, 69])
    sources["instance_to_facility_type"]["boundary_io"] = "attacker_type"
    sources["artifact_hashes"]["canonical_rules.json"] = "f" * 64
    state = sources["state"]
    state.groups["boundary_io"].demand = 999
    state.groups["boundary_io"].selected_poses.append("attacker_pose")
    state.cell_owner[(69, 69)] = ("attacker_group", 0)


def _assert_sha256_hex(digest: str) -> None:
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)


def _make_region_capacity_cut(
    sources: dict[str, Any],
    *,
    cut_type: Any,
    scope_type: Any,
    cert_type: Any,
    canonicalize: Any,
    encode_region_bitset: Any,
    compute_blocked_cells_hash: Any,
    compute_exterior_blocks_hash: Any,
    ghost_agnostic: str,
    family: str = "cutset",
) -> Any:
    state = sources["state"]
    if family == "cutset":
        payload_dict = {
            "cert_kind": "menger_min_cut",
            "side_a_bitset_b64": encode_region_bitset([(0, 0)], grid_size=70),
            "side_b_bitset_b64": encode_region_bitset([(0, 1)], grid_size=70),
            "cut_edges": [[[0, 0], [0, 1]]],
            "cut_size": 1,
            "commodity_demand": 1,
            "contributing_commodities": ["probe"],
        }
        cert_kind = "menger_min_cut"
    elif family == "shape_packing_hall":
        payload_dict = {
            "cert_kind": "hall_interval_witness",
            "region_kind": "left_baseline",
            "region_total_length": 70,
            "partition_lens": [4, 5],
            "partition_offsets": [0, 5],
            "pose_length": 3,
            "pose_shape_canonical": "1x3_rigid",
            "max_packable": [1, 1],
            "total_packable": 2,
            "contributing_group": "boundary_io",
            "region_demand": 3,
            "group_demand": 2,
            "ghost_rect_repr": [0, 0, 1, 1],
            "exterior_blocks_digest": compute_exterior_blocks_hash(state),
        }
        cert_kind = "hall_interval_witness"
    else:  # pragma: no cover - test helper guard
        raise AssertionError(f"unsupported platform probe family {family!r}")
    payload = canonicalize(payload_dict)
    cert_hash = hashlib.sha256(payload).hexdigest()
    return cut_type(
        cut_id="b0-region-capacity",
        family=family,
        literals=None,
        geometric_payload=payload,
        scope=scope_type(
            ghost_rect_id=ghost_agnostic,
            blocked_cells_hash=compute_blocked_cells_hash(state),
            exterior_blocks_hash=compute_exterior_blocks_hash(state),
            source_digest=state.source_digest,
            artifact_hashes=dict(state.artifact_hashes),
            oracle_abstraction_version="region_capacity_v1",
        ),
        cert=cert_type(
            cert_kind=cert_kind,
            cert_payload=payload,
            cert_hash=cert_hash,
        ),
        oracle_name="region_capacity_v1",
    )


def _make_pattern_nogood_cut(
    sources: dict[str, Any],
    *,
    anonymous_slot_ref_type: Any,
    cut_literal_type: Any,
    cut_type: Any,
    scope_type: Any,
    cert_type: Any,
    canonicalize: Any,
    compute_blocked_cells_hash: Any,
    compute_exterior_blocks_hash: Any,
    compute_ghost_rect_id: Any,
) -> Any:
    pattern = (("boundary_io", 0, "boundary_pose_0"),)
    payload = canonicalize(
        {
            "cert_kind": "bounded_deletion_core",
            "sub_problem_oracle_name": "binding_empty_domain_v1",
            "sub_problem_oracle_version": "v1.0",
            "forbidden_pose_pattern": [list(item) for item in pattern],
            "core_minimization": {
                "size_before": 1,
                "size_after": 1,
                "calls": 1,
                "stopped_reason": "INFEASIBLE_VERIFIED",
                "is_verified_infeasible": True,
            },
        }
    )
    cert_hash = hashlib.sha256(payload).hexdigest()
    state = sources["state"]
    return cut_type(
        cut_id="b0-pattern-nogood",
        family="pattern_nogood",
        literals=tuple(
            cut_literal_type(
                slot_ref=anonymous_slot_ref_type(group_id=group, slot_index=slot),
                pose_id=pose,
            )
            for group, slot, pose in pattern
        ),
        geometric_payload=None,
        scope=scope_type(
            ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
            blocked_cells_hash=compute_blocked_cells_hash(state),
            exterior_blocks_hash=compute_exterior_blocks_hash(state),
            source_digest=state.source_digest,
            artifact_hashes=dict(state.artifact_hashes),
            oracle_abstraction_version="binding_empty_domain_v1",
        ),
        cert=cert_type(
            cert_kind="bounded_deletion_core",
            cert_payload=payload,
            cert_hash=cert_hash,
        ),
        oracle_name="pattern_nogood_v1",
    )


@dataclass(frozen=True)
class _DerivedProbeBody:
    group_id: str = "boundary_io"
    capacity: int = 1


class _RecordingPlugin:
    def __init__(self, plan: Any, proof: Any) -> None:
        self.plan = plan
        self.proof = proof
        self.body = _DerivedProbeBody()
        self.calls: dict[str, list[tuple[Any, ...]]] = {
            "compile": [],
            "derive_body": [],
            "parse_and_validate_proof": [],
            "validate_plan": [],
        }

    def parse_and_validate_proof(self, proof_payload: Any, snapshot: Any) -> Any:
        assert isinstance(proof_payload, bytes)
        self.calls["parse_and_validate_proof"].append((proof_payload, snapshot))
        return self.proof

    def derive_body(self, proof: Any) -> Any:
        # RFC-001 §3: body 是 proof 的纯投影,不吃 snapshot(§2.9 文本为准)。
        assert proof is self.proof
        self.calls["derive_body"].append((proof,))
        return self.body

    def compile(self, body: Any, proof: Any, snapshot: Any) -> Any:
        assert body is self.body
        assert proof is self.proof
        self.calls["compile"].append((body, proof, snapshot))
        return self.plan

    def validate_plan(self, plan: Any, proof: Any, snapshot: Any) -> None:
        assert plan is self.plan
        assert proof is self.proof
        self.calls["validate_plan"].append((plan, proof, snapshot))


def _assert_compilable_plugin_single_pass(plugin: _RecordingPlugin) -> None:
    assert {method_name: len(calls) for method_name, calls in plugin.calls.items()} == {
        "compile": 1,
        "derive_body": 1,
        "parse_and_validate_proof": 1,
        "validate_plan": 1,
    }


def _make_plan(
    typed_platform: Any,
    *,
    parameters: dict[str, Any] | None = None,
    family: str = "cutset",
) -> Any:
    if parameters is None:
        parameters = {
            "group_id": "boundary_io",
            "region_kind": "left_baseline",
            "capacity": 1,
        }
    return typed_platform.ConstraintPlan(
        family=family,
        schema_version=1,
        semantic_fingerprint="5" * 64,
        model_scope=typed_platform.ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint="6" * 64,
        ),
        operation="shape_packing_hall_le",
        parameters=parameters,
    )


def _make_probe_proof(typed_platform: Any, *, family: str) -> Any:
    return typed_platform.FrozenFamilyProof(family=family, schema_version=1)


def _trusted_test_envelope(
    typed_platform: Any,
    lifecycle: Any,
    raw_cut: Any,
    snapshot: Any,
) -> Any:
    """Build a full-identity envelope for platform contract tests.

    The committed v1 ``CutScope`` carries only 16-hex identities and the B1.5
    adapter must now reject it.  These tests exercise the generic typed
    pipeline, not that legacy limitation, so their fixture binds identities
    directly to the already-built immutable snapshot.
    """

    assert raw_cut.cert is not None
    assert raw_cut.scope is not None
    proof = lifecycle.validate_cert_payload(raw_cut.family, raw_cut.cert.cert_payload)
    proof_payload = typed_platform._proof_frame(  # noqa: SLF001 - contract fixture
        family=raw_cut.family,
        schema_version=1,
        proof=proof,
    )
    if raw_cut.scope.ghost_rect_id == lifecycle.GHOST_AGNOSTIC:
        ghost_policy = "agnostic"
        ghost_rect_digest = None
        blocked_cells_digest = None
    else:
        assert snapshot.ghost is not None
        ghost_policy = "bound"
        ghost_projection = [
            snapshot.ghost.x,
            snapshot.ghost.y,
            snapshot.ghost.width,
            snapshot.ghost.height,
        ]
        ghost_rect_digest = hashlib.sha256(
            b"zmd.ghost-rect.v1:"
            + json.dumps(
                ghost_projection,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        blocked_cells_digest = snapshot.blocked_cells_digest
    scope = typed_platform.ScopeManifest(
        scope_schema_version=1,
        family=raw_cut.family,
        ghost_policy=ghost_policy,
        ghost_rect_digest=ghost_rect_digest,
        blocked_cells_digest=blocked_cells_digest,
        exterior_blocks_digest=snapshot.exterior_blocks_digest,
        source_digest=snapshot.source_digest,
        dependency_hashes=tuple(
            typed_platform.DependencyHash(name=name, digest=digest)
            for name, digest in sorted(raw_cut.scope.artifact_hashes.items())
        ),
        oracle_abstraction_version=raw_cut.scope.oracle_abstraction_version,
        assumptions=tuple(
            typed_platform.ScopeAssumption(key=item.key, value=item.value) for item in raw_cut.scope.active_assumptions
        ),
    )
    return typed_platform.CutEnvelope(
        cut_id=raw_cut.cut_id,
        family=raw_cut.family,
        family_schema_version=1,
        proof_payload=proof_payload,
        proof_hash=hashlib.sha256(proof_payload).hexdigest(),
        scope=scope,
        provenance=typed_platform.CutProvenance(
            family_version=raw_cut.family_version,
            validator_version=raw_cut.validator_version,
            oracle_name=raw_cut.oracle_name,
            oracle_cert_hash=raw_cut.oracle_cert_hash,
            created_at=raw_cut.created_at,
            iter_index=raw_cut.iter_index,
        ),
    )


def _typed_execution_path(typed_platform: Any) -> Any:
    execution_path_type = getattr(typed_platform, "ExecutionPath", None)
    if execution_path_type is None:
        return "TYPED"
    return execution_path_type.TYPED


def _make_registry(
    typed_platform: Any,
    plugin: Any,
    *,
    family: str,
    mode: str,
    stage: Any,
    compiler_version: str | None,
    required_dependencies: frozenset[str],
) -> Any:
    capability = typed_platform.FamilyCapability(
        name=family,
        mode=mode,
        proof_schema_version=1,
        validator_version="b0-spy-v1",
        compiler_version=compiler_version,
        stage=stage,
        required_dependencies=required_dependencies,
        execution_path=_typed_execution_path(typed_platform),
    )
    return typed_platform.FamilyCapabilityRegistry(
        capabilities={family: capability},
        plugins={family: plugin},
    )


def _typed_probe_pipeline_inputs(
    frozen_artifacts: Any,
    state_snapshot: Any,
    typed_platform: Any,
    lifecycle: Any,
) -> tuple[dict[str, Any], Any, Any, Any]:
    sources = _mutable_stage_b_sources(lifecycle.BState, lifecycle.GroupState)
    sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
    bundle = _build_bundle(frozen_artifacts.build_frozen_artifact_bundle, sources)
    snapshot = state_snapshot.build_validated_state_snapshot(sources["state"], bundle)
    raw_cut = _make_region_capacity_cut(
        sources,
        cut_type=lifecycle.Cut,
        scope_type=lifecycle.CutScope,
        cert_type=lifecycle.OracleCert,
        canonicalize=lifecycle.step_0_canonicalize,
        encode_region_bitset=lifecycle._encode_region_bitset,
        compute_blocked_cells_hash=lifecycle.compute_blocked_cells_hash,
        compute_exterior_blocks_hash=lifecycle.compute_exterior_blocks_hash,
        ghost_agnostic=lifecycle.GHOST_AGNOSTIC,
        family="shape_packing_hall",
    )
    envelope = _trusted_test_envelope(typed_platform, lifecycle, raw_cut, snapshot)
    return sources, bundle, snapshot, envelope


@pytest.mark.xfail(
    condition=_stage_b_missing("src.cuts.frozen_artifacts", "build_frozen_artifact_bundle"),
    strict=True,
    reason="stage-B B1 待实现: §2.1 FrozenArtifactBundle 递归冻结与 digest",
)
def test_frozen_artifact_bundle_breaks_source_aliases() -> None:
    from src.cuts.frozen_artifacts import (
        FrozenArtifactBundle,
        build_frozen_artifact_bundle,
    )
    from src.cuts.lifecycle import BState, GroupState

    sources = _mutable_stage_b_sources(BState, GroupState)
    bundle = _build_bundle(build_frozen_artifact_bundle, sources)
    assert isinstance(bundle, FrozenArtifactBundle)
    digest_before = bundle.digest
    _assert_sha256_hex(digest_before)

    _mutate_builder_sources(sources)

    assert bundle.digest == digest_before
    assert bundle.facility_templates["boundary_storage_port"]["dimensions"] == {
        "w": 1,
        "h": 3,
    }
    assert bundle.canonical_rules["facility_templates"]["boundary_storage_port"]["dimensions"] == {"w": 1, "h": 3}
    assert bundle.candidate_placements["facility_pools"]["boundary_storage_port"][0]["occupied_cells"] == (
        (0, 1),
        (0, 2),
        (0, 3),
    )
    assert bundle.instance_to_facility_type["boundary_io"] == "boundary_storage_port"
    with pytest.raises(TypeError):
        bundle.facility_templates["boundary_storage_port"]["dimensions"]["w"] = 7
    with pytest.raises(AttributeError):
        bundle.candidate_placements["facility_pools"]["boundary_storage_port"][0]["occupied_cells"].append((7, 7))
    with pytest.raises(TypeError):
        bundle.instance_to_facility_type["boundary_io"] = "attacker_type"
    assert bundle.digest == digest_before
    attacked_bundle = _build_bundle(build_frozen_artifact_bundle, sources)
    assert attacked_bundle.digest != digest_before


@pytest.mark.xfail(
    condition=(
        _stage_b_missing("src.cuts.frozen_artifacts", "build_frozen_artifact_bundle")
        or _stage_b_missing("src.cuts.state_snapshot", "GhostRect")
    ),
    strict=True,
    reason="stage-B B1 待实现: §2.3 非方形 GhostRect 轴序 round-trip 自检",
)
def test_non_square_ghost_round_trips_without_axis_swap() -> None:
    from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
    from src.cuts.lifecycle import BState, GroupState
    from src.cuts.state_snapshot import GhostRect, build_validated_state_snapshot

    sources = _mutable_stage_b_sources(BState, GroupState, ghost_rect=(11, 17, 2, 3))
    bundle = _build_bundle(build_frozen_artifact_bundle, sources)
    snapshot = build_validated_state_snapshot(sources["state"], bundle)

    assert isinstance(snapshot.ghost, GhostRect)
    assert (
        snapshot.ghost.x,
        snapshot.ghost.y,
        snapshot.ghost.width,
        snapshot.ghost.height,
    ) == (11, 17, 2, 3)
    assert snapshot.ghost.width != snapshot.ghost.height
    _assert_sha256_hex(snapshot.digest)


@pytest.mark.xfail(
    condition=(
        _stage_b_missing("src.cuts.frozen_artifacts", "build_frozen_artifact_bundle")
        or _stage_b_missing("src.cuts.state_snapshot", "build_validated_state_snapshot")
    ),
    strict=True,
    reason="stage-B B1 待实现: §2.2/§6 钉② snapshot builder alias 隔离与 digest",
)
def test_snapshot_digest_survives_builder_input_mutation() -> None:
    from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
    from src.cuts.lifecycle import BState, GroupState, compute_source_digest
    from src.cuts.state_snapshot import build_validated_state_snapshot

    sources = _mutable_stage_b_sources(BState, GroupState)
    sources["state"].source_digest = compute_source_digest(sources["state"])
    bundle = _build_bundle(build_frozen_artifact_bundle, sources)
    snapshot = build_validated_state_snapshot(sources["state"], bundle)
    snapshot_digest_before = snapshot.digest
    _assert_sha256_hex(snapshot_digest_before)

    _mutate_builder_sources(sources)

    assert snapshot.digest == snapshot_digest_before
    assert snapshot.groups["boundary_io"].demand == 2
    assert snapshot.groups["boundary_io"].selected_poses == ()
    assert snapshot.cell_owner == {(4, 4): ("boundary_io", 0)}
    assert snapshot.artifact_hashes["canonical_rules.json"] == "1" * 64

    def assert_snapshot_digest_unchanged() -> None:
        assert snapshot.digest == snapshot_digest_before

    with pytest.raises((TypeError, AttributeError)):
        snapshot.groups["attacker"] = snapshot.groups["boundary_io"]
    assert_snapshot_digest_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        snapshot.groups["boundary_io"].demand = 999
    assert_snapshot_digest_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        snapshot.groups["boundary_io"].pose_domain.update({"attacker_pose"})
    assert_snapshot_digest_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        snapshot.groups["boundary_io"].selected_poses.append("attacker_pose")
    assert_snapshot_digest_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        snapshot.groups.update({"attacker": snapshot.groups["boundary_io"]})
    assert_snapshot_digest_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        snapshot.cell_owner[(69, 69)] = ("attacker", 0)
    assert_snapshot_digest_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        snapshot.cell_owner.update({(69, 69): ("attacker", 0)})
    assert_snapshot_digest_unchanged()


@pytest.mark.xfail(
    condition=_stage_b_missing("src.cuts.typed_platform", "validate_and_compile_cut"),
    strict=True,
    reason="stage-B B1.5 待实现: §6 钉② ConstraintPlan/CompiledCut 深冻结与 digest",
)
def test_plan_digest_survives_builder_input_mutation() -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle

    sources, _bundle, snapshot, envelope = _typed_probe_pipeline_inputs(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    plan_parameters = {
        "group_id": "boundary_io",
        "region_kind": "left_baseline",
        "capacity": 1,
    }
    plan = _make_plan(
        typed_platform,
        parameters=plan_parameters,
        family="shape_packing_hall",
    )
    plugin = _RecordingPlugin(
        plan,
        _make_probe_proof(typed_platform, family="shape_packing_hall"),
    )
    registry = _make_registry(
        typed_platform,
        plugin,
        family="shape_packing_hall",
        mode="geometric",
        stage=typed_platform.CapabilityStage.COMPILABLE,
        compiler_version="b0-spy-v1",
        required_dependencies=frozenset(sources["artifact_hashes"]),
    )
    result = typed_platform.validate_and_compile_cut(envelope, snapshot, registry)
    assert isinstance(result, typed_platform.CompiledCut)
    snapshot_digest_before = snapshot.digest
    plan_digest_before = result.plan.digest
    compiled_digest_before = result.digest
    for digest in (
        snapshot_digest_before,
        plan_digest_before,
        compiled_digest_before,
    ):
        _assert_sha256_hex(digest)

    _mutate_builder_sources(sources)
    plan_parameters["region_kind"] = "bottom_baseline"
    plan_parameters["capacity"] = 999

    assert snapshot.digest == snapshot_digest_before
    assert result.plan.digest == plan_digest_before
    assert result.plan.parameters == {
        "group_id": "boundary_io",
        "region_kind": "left_baseline",
        "capacity": 1,
    }
    assert result.digest == compiled_digest_before
    assert result.snapshot_digest == snapshot.digest
    attacked_plan = _make_plan(
        typed_platform,
        parameters=plan_parameters,
        family="shape_packing_hall",
    )
    assert attacked_plan.digest != plan_digest_before

    def assert_plan_digests_unchanged() -> None:
        assert result.plan.digest == plan_digest_before
        assert result.digest == compiled_digest_before
        assert snapshot.digest == snapshot_digest_before

    with pytest.raises((TypeError, AttributeError)):
        result.plan.parameters["capacity"] = 999
    assert_plan_digests_unchanged()
    with pytest.raises((TypeError, AttributeError)):
        result.plan.parameters.update({"capacity": 999})
    assert_plan_digests_unchanged()
    # Nested-mapping deep-freeze coverage moved to the real F1 chain in
    # test_stage_b_region_capacity (group_cell_weights is F1-shaped; this
    # platform fixture explicitly opts into the F6 scalar typed-probe schema;
    # the default mechanism/rejection helpers remain permanent cutset/F2).


@pytest.mark.xfail(
    condition=_stage_b_missing("src.cuts.typed_platform", "FamilyPlugin"),
    strict=True,
    reason="stage-B B1.5 待实现: §6 钉① verifier/compiler 同一 snapshot 对象",
)
def test_verifier_and_compiler_receive_same_snapshot_object() -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle

    sources, _bundle, snapshot, envelope = _typed_probe_pipeline_inputs(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    plugin = _RecordingPlugin(
        _make_plan(typed_platform, family="shape_packing_hall"),
        _make_probe_proof(typed_platform, family="shape_packing_hall"),
    )
    registry = _make_registry(
        typed_platform,
        plugin,
        family="shape_packing_hall",
        mode="geometric",
        stage=typed_platform.CapabilityStage.COMPILABLE,
        compiler_version="b0-spy-v1",
        required_dependencies=frozenset(sources["artifact_hashes"]),
    )

    result = typed_platform.validate_and_compile_cut(envelope, snapshot, registry)

    assert isinstance(result, typed_platform.CompiledCut)
    assert inspect.isclass(typed_platform.FamilyPlugin)
    assert getattr(typed_platform.FamilyPlugin, "_is_protocol", False)
    expected_parameters = {
        "parse_and_validate_proof": ("self", "proof_payload", "snapshot"),
        "derive_body": ("self", "proof"),
        "compile": ("self", "body", "proof", "snapshot"),
        "validate_plan": ("self", "plan", "proof", "snapshot"),
    }
    for method_name, parameter_names in expected_parameters.items():
        method = getattr(typed_platform.FamilyPlugin, method_name)
        assert callable(method)
        assert tuple(inspect.signature(method).parameters) == parameter_names
    _assert_compilable_plugin_single_pass(plugin)
    snapshot_ids = {
        id(plugin.calls["parse_and_validate_proof"][0][1]),
        id(plugin.calls["compile"][0][2]),
        id(plugin.calls["validate_plan"][0][2]),
    }
    assert snapshot_ids == {id(snapshot)}


@pytest.mark.xfail(
    condition=_stage_b_missing("src.cuts.typed_platform", "FamilyPlugin"),
    strict=True,
    reason="stage-B B1.5 待实现: §2.7/§6 钉⑥ frozen proof 单对象且 compiler 禁读 raw bytes",
)
def test_pipeline_reuses_frozen_proof_without_compiler_raw_byte_access() -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle

    sources, _bundle, snapshot, envelope = _typed_probe_pipeline_inputs(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    plugin = _RecordingPlugin(
        _make_plan(typed_platform, family="shape_packing_hall"),
        _make_probe_proof(typed_platform, family="shape_packing_hall"),
    )
    registry = _make_registry(
        typed_platform,
        plugin,
        family="shape_packing_hall",
        mode="geometric",
        stage=typed_platform.CapabilityStage.COMPILABLE,
        compiler_version="b0-spy-v1",
        required_dependencies=frozenset(sources["artifact_hashes"]),
    )

    result = typed_platform.validate_and_compile_cut(envelope, snapshot, registry)

    assert isinstance(result, typed_platform.CompiledCut)
    _assert_compilable_plugin_single_pass(plugin)
    proof_ids = {
        id(plugin.calls["derive_body"][0][0]),
        id(plugin.calls["compile"][0][1]),
        id(plugin.calls["validate_plan"][0][1]),
    }
    assert proof_ids == {id(plugin.proof)}
    raw_payload = plugin.calls["parse_and_validate_proof"][0][0]
    compile_args = plugin.calls["compile"][0]
    assert id(raw_payload) not in {id(argument) for argument in compile_args}
    assert not any(isinstance(argument, bytes) for argument in compile_args)
    assert not any(hasattr(argument, "cert_payload") or hasattr(argument, "proof_payload") for argument in compile_args)
    with pytest.raises(AttributeError):
        plugin.proof.family = "attacker"


class _UntouchedMaster:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        raise AssertionError(f"master was touched through {name}")


def _build_shadow_result(
    frozen_artifacts: Any,
    state_snapshot: Any,
    typed_platform: Any,
    lifecycle: Any,
) -> tuple[dict[str, Any], Any, Any, Any, Any, _RecordingPlugin]:
    sources, _bundle, snapshot, _envelope = _typed_probe_pipeline_inputs(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    shadow_cut = _make_pattern_nogood_cut(
        sources,
        anonymous_slot_ref_type=lifecycle.AnonymousSlotRef,
        cut_literal_type=lifecycle.CutLiteral,
        cut_type=lifecycle.Cut,
        scope_type=lifecycle.CutScope,
        cert_type=lifecycle.OracleCert,
        canonicalize=lifecycle.step_0_canonicalize,
        compute_blocked_cells_hash=lifecycle.compute_blocked_cells_hash,
        compute_exterior_blocks_hash=lifecycle.compute_exterior_blocks_hash,
        compute_ghost_rect_id=lifecycle.compute_ghost_rect_id,
    )
    shadow_envelope = _trusted_test_envelope(
        typed_platform,
        lifecycle,
        shadow_cut,
        snapshot,
    )
    shadow_plugin = _RecordingPlugin(
        _make_plan(typed_platform),
        _make_probe_proof(typed_platform, family="pattern_nogood"),
    )
    shadow_registry = _make_registry(
        typed_platform,
        shadow_plugin,
        family="pattern_nogood",
        mode="literal",
        stage=typed_platform.CapabilityStage.VALIDATED,
        compiler_version=None,
        required_dependencies=frozenset(sources["artifact_hashes"]),
    )
    shadow = typed_platform.validate_and_compile_cut(shadow_envelope, snapshot, shadow_registry)
    return (
        sources,
        shadow_cut,
        shadow_envelope,
        snapshot,
        shadow,
        shadow_plugin,
    )


@pytest.mark.xfail(
    condition=_stage_b_missing("src.cuts.typed_platform", "ShadowValidated"),
    strict=True,
    reason="stage-B B1.5 待实现: §2.5/§2.8 F5 VALIDATED 的 ShadowValidated 出口",
)
def test_validated_capability_returns_shadow_without_compiling() -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle

    _sources, _raw_cut, envelope, snapshot, shadow, plugin = _build_shadow_result(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )

    assert isinstance(shadow, typed_platform.ShadowValidated)
    assert shadow.cut_id == envelope.cut_id
    assert shadow.telemetry_tag == "common-mode-untrusted"
    _assert_sha256_hex(shadow.proof_digest)
    _assert_sha256_hex(shadow.snapshot_digest)
    assert len(plugin.calls["parse_and_validate_proof"]) == 1
    proof_payload, parsed_snapshot = plugin.calls["parse_and_validate_proof"][0]
    assert proof_payload == envelope.proof_payload
    assert parsed_snapshot is snapshot
    assert shadow.proof_digest == envelope.proof_hash
    assert envelope.proof_hash == hashlib.sha256(proof_payload).hexdigest()
    assert shadow.snapshot_digest == snapshot.digest
    assert len(plugin.calls["derive_body"]) <= 1
    assert plugin.calls["compile"] == []
    assert plugin.calls["validate_plan"] == []

    # B1.5解除补充义务：另用 production registry + 真实 F5 envelope 复验；
    # 本 spy seam 只证明 VALIDATED dispatch 的结果代数与零 compile。


@pytest.mark.xfail(
    condition=_stage_b5_apply_missing(),
    strict=True,
    reason="stage-B B5 待实现: §2.9/§6 钉③④ step_8 类型拒绝 raw Cut/ShadowValidated",
)
def test_step_8_rejects_raw_and_shadow_results_without_touching_master() -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle

    sources, raw_cut, _envelope, _snapshot, shadow, shadow_plugin = _build_shadow_result(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )
    assert isinstance(shadow, typed_platform.ShadowValidated)
    assert len(shadow_plugin.calls["parse_and_validate_proof"]) == 1
    assert shadow_plugin.calls["compile"] == []
    assert shadow_plugin.calls["validate_plan"] == []
    assert sources["state"].source_digest

    signature = inspect.signature(lifecycle.step_8_apply_to_master)
    assert "scope_binding" in signature.parameters
    master = _UntouchedMaster()
    for rejected in (raw_cut, shadow):
        with pytest.raises((TypeError, ValueError)):
            lifecycle.step_8_apply_to_master(
                rejected,
                master,
                scope_binding=None,
            )
    assert master.calls == []

    # B5 wiring supplement: _maybe_attach_framework_cuts must explicitly match
    # CutRejection/ShadowValidated and prove the real master spy stays at zero.


def _bound_region_sources(
    bstate_type: Any,
    group_state_type: Any,
    *,
    ghost_rect: tuple[int, int, int, int],
    group_id: str = "boundary_io",
) -> dict[str, Any]:
    facility_templates = {
        "boundary_storage_port": {
            "placement_rule": "left_or_bottom_boundary",
            "dimensions": {"w": 1, "h": 3},
            "needs_power": False,
        }
    }
    poses = [
        {
            "pose_id": f"boundary_pose_{index}",
            "anchor": {"x": 0, "y": index},
            "occupied_cells": [
                [0, index % 68],
                [0, (index + 1) % 68],
                [0, (index + 2) % 68],
            ],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
        for index in range(46)
    ]
    canonical_rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": facility_templates,
    }
    candidate_placements = {"facility_pools": {"boundary_storage_port": poses}}
    # Match the production F1 capability manifest
    # (typed_platform._PRODUCTION_V1_ARTIFACT_DEPENDENCIES); the scope dependency
    # set derives from these names via cut_to_envelope_v1, so an incomplete set
    # is refused at the typed scope stage before the resolver is reached.
    artifact_hashes = {
        "candidate_placements": "1" * 64,
        "canonical_rules": "2" * 64,
        "certified_exact_source_tree": "3" * 64,
        "commodity_demands": "4" * 64,
        "generic_io_requirements": "5" * 64,
        "mandatory_exact_instances": "6" * 64,
        "orbit_homogeneity_digest": "7" * 64,
        "preprocess_plan": "8" * 64,
    }
    x, y, width, height = ghost_rect
    ghost_cells = frozenset((cell_x, cell_y) for cell_x in range(x, x + width) for cell_y in range(y, y + height))
    state = bstate_type(
        groups={
            group_id: group_state_type(
                group_id=group_id,
                demand=46,
                pose_domain=frozenset(pose["pose_id"] for pose in poses),
                selected_poses=[],
            )
        },
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset(),
        artifact_hashes=artifact_hashes,
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type={group_id: "boundary_storage_port"},
        source_digest="d" * 64,
    )
    return {
        "artifact_hashes": artifact_hashes,
        "candidate_placements": candidate_placements,
        "canonical_rules": canonical_rules,
        "facility_templates": facility_templates,
        "instance_to_facility_type": {group_id: "boundary_storage_port"},
        "state": state,
    }


def _build_real_tiny_master(
    master_model_type: Any,
    *,
    ghost_rect: tuple[int, int] = (3, 1),
) -> Any:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": f"pose_{tag}",
                "anchor": {"x": x, "y": 0},
                "occupied_cells": [[x, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for tag, x in (("left", 0), ("mid", 2), ("right", 4))
        ]
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {"miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}},
    }
    core = master_model_type.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
    )
    return master_model_type.from_exact_core(core, ghost_rect=ghost_rect)


def _build_bound_region_master(master_model_type: Any, sources: dict[str, Any]) -> Any:
    instances = [
        {
            "instance_id": f"boundary_{index:03d}",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index in range(46)
    ]
    core = master_model_type.build_exact_core(
        instances,
        sources["candidate_placements"]["facility_pools"],
        sources["canonical_rules"],
        skip_power_coverage=True,
    )
    return master_model_type.from_exact_core(core, ghost_rect=(3, 1))


def _real_master_mutation_projection(master: Any, *, proto_path: Path) -> tuple[Any, ...]:
    from ortools.sat import cp_model_pb2

    delegate = master._coordinate_delegate
    assert delegate is not None
    cache_names = (
        "_eq_literal_cache",
        "_slot_pose_match_cache",
        "_pose_present_cache",
        "_pose_idx_by_pose_id_cache",
    )
    caches = tuple(
        (
            name,
            tuple(sorted((repr(key), repr(value)) for key, value in getattr(delegate, name).items())),
        )
        for name in cache_names
    )
    native_proto = delegate.model.Proto()
    native_serializer = getattr(native_proto, "SerializeToString", None)
    if native_serializer is not None:
        proto_bytes = native_serializer(deterministic=True)
    else:
        # OR-Tools 9.15 exposes a pybind CpModelProto without SerializeToString.
        # Export to the generated protobuf type, then use deterministic binary
        # serialization—the semantic equivalent required by this contract.
        if not delegate.model.export_to_file(str(proto_path)):
            raise AssertionError(f"failed to export CP-SAT proto to {proto_path}")
        generated_proto = cp_model_pb2.CpModelProto.FromString(proto_path.read_bytes())
        proto_bytes = generated_proto.SerializeToString(deterministic=True)
    return proto_bytes, caches


def _compile_bound_region_case(
    frozen_artifacts: Any,
    state_snapshot: Any,
    typed_platform: Any,
    lifecycle: Any,
    generate_region_capacity_cuts: Any,
    registry: Any,
    *,
    ghost_rect: tuple[int, int, int, int],
    group_id: str,
) -> tuple[dict[str, Any], Any, Any]:
    sources = _bound_region_sources(
        lifecycle.BState,
        lifecycle.GroupState,
        ghost_rect=ghost_rect,
        group_id=group_id,
    )
    sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
    bundle = _build_bundle(frozen_artifacts.build_frozen_artifact_bundle, sources)
    snapshot = state_snapshot.build_validated_state_snapshot(sources["state"], bundle)
    cuts = generate_region_capacity_cuts(sources["state"], sources["canonical_rules"])
    assert len(cuts) == 1
    envelope = typed_platform.cut_to_envelope_v1(cuts[0])
    compiled = typed_platform.validate_and_compile_cut(envelope, snapshot, registry)
    assert isinstance(compiled, typed_platform.CompiledCut)
    return sources, snapshot, compiled


def _build_scope_binding_world(
    frozen_artifacts: Any,
    state_snapshot: Any,
    typed_platform: Any,
    lifecycle: Any,
    generate_region_capacity_cuts: Any,
    master_model_type: Any,
) -> tuple[Any, str, Any, Any, Any, Any]:
    registry = typed_platform.build_production_registry()
    seed_sources = _bound_region_sources(
        lifecycle.BState,
        lifecycle.GroupState,
        ghost_rect=(0, 0, 3, 1),
    )
    master = _build_bound_region_master(master_model_type, seed_sources)
    group_id = str(master._group_id_by_instance["boundary_000"])
    _sources_a, snapshot_a, compiled_a = _compile_bound_region_case(
        frozen_artifacts,
        state_snapshot,
        typed_platform,
        lifecycle,
        generate_region_capacity_cuts,
        registry,
        ghost_rect=(0, 0, 3, 1),
        group_id=group_id,
    )
    _sources_b, snapshot_b, compiled_b = _compile_bound_region_case(
        frozen_artifacts,
        state_snapshot,
        typed_platform,
        lifecycle,
        generate_region_capacity_cuts,
        registry,
        ghost_rect=(2, 0, 3, 1),
        group_id=group_id,
    )
    return master, group_id, snapshot_a, compiled_a, snapshot_b, compiled_b


def _build_bound_snapshot(
    frozen_artifacts: Any,
    state_snapshot: Any,
    lifecycle: Any,
    *,
    group_id: str,
    selected_poses: list[str],
) -> Any:
    sources = _bound_region_sources(
        lifecycle.BState,
        lifecycle.GroupState,
        ghost_rect=(0, 0, 3, 1),
        group_id=group_id,
    )
    sources["state"].groups[group_id].selected_poses.extend(selected_poses)
    sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
    bundle = _build_bundle(frozen_artifacts.build_frozen_artifact_bundle, sources)
    return state_snapshot.build_validated_state_snapshot(sources["state"], bundle)


def _assert_step_8_rejected_without_master_mutation(
    lifecycle: Any,
    compiled: Any,
    master: Any,
    binding: Any,
    *,
    tmp_path: Path,
) -> None:
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "before.pb")
    build_stats_before = repr(master.build_stats)
    with pytest.raises((TypeError, ValueError)):
        lifecycle.step_8_apply_to_master(
            compiled,
            master,
            scope_binding=binding,
        )
    after = _real_master_mutation_projection(master, proto_path=tmp_path / "after.pb")
    assert after == before
    assert repr(master.build_stats) == build_stats_before


@pytest.mark.xfail(
    condition=_stage_b5_apply_missing(),
    strict=True,
    reason="stage-B B5 待实现: §2.6 三连① ghost digest 单项错绑拒绝",
)
def test_step_8_rejects_ghost_digest_misbinding_without_master_mutation(
    tmp_path: Path,
) -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle
    from src.cuts.lifecycle import _resolve_model_scope_binding
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.models.master_model import MasterPlacementModel

    master, _group_id, snapshot_a, compiled_a, _snapshot_b, compiled_b = _build_scope_binding_world(
        frozen_artifacts,
        state_snapshot,
        typed_platform,
        lifecycle,
        generate_region_capacity_cuts,
        MasterPlacementModel,
    )
    scope_a = compiled_a.plan.model_scope
    scope_b = compiled_b.plan.model_scope
    rect_b_idx = next(
        index for index, domain in enumerate(master._ghost_domains) if domain["anchor"] == {"x": 2, "y": 0}
    )
    binding = _resolve_model_scope_binding(scope_b, snapshot_a, master)

    assert scope_a.ghost_rect_digest != binding.ghost_rect_digest
    assert scope_a.domain_fingerprint == binding.master_domain_projection
    assert compiled_a.snapshot_digest == binding.snapshot_digest
    assert binding.condition_lits == (master.u_vars[rect_b_idx],)
    assert binding.condition_lits[0] is master.u_vars[rect_b_idx]
    _assert_step_8_rejected_without_master_mutation(
        lifecycle,
        compiled_a,
        master,
        binding,
        tmp_path=tmp_path,
    )


@pytest.mark.xfail(
    condition=_stage_b5_apply_missing(),
    strict=True,
    reason="stage-B B5 待实现: §2.6 三连② domain projection 单项错绑拒绝",
)
def test_step_8_rejects_domain_projection_misbinding_without_master_mutation(
    tmp_path: Path,
) -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle
    from src.cuts.lifecycle import _resolve_model_scope_binding
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.models.master_model import MasterPlacementModel

    master, _group_id, snapshot_a, compiled_a, _snapshot_b, _compiled_b = _build_scope_binding_world(
        frozen_artifacts,
        state_snapshot,
        typed_platform,
        lifecycle,
        generate_region_capacity_cuts,
        MasterPlacementModel,
    )
    scope_a = compiled_a.plan.model_scope
    master.facility_pools["boundary_storage_port"][0]["alpha_projection_drift"] = True
    binding = _resolve_model_scope_binding(scope_a, snapshot_a, master)

    assert scope_a.ghost_rect_digest == binding.ghost_rect_digest
    assert scope_a.domain_fingerprint != binding.master_domain_projection
    assert compiled_a.snapshot_digest == binding.snapshot_digest
    _assert_step_8_rejected_without_master_mutation(
        lifecycle,
        compiled_a,
        master,
        binding,
        tmp_path=tmp_path,
    )


@pytest.mark.xfail(
    condition=_stage_b5_apply_missing(),
    strict=True,
    reason="stage-B B5 待实现: §2.6 三连③ snapshot digest 单项错绑拒绝",
)
def test_step_8_rejects_snapshot_digest_misbinding_without_master_mutation(
    tmp_path: Path,
) -> None:
    from src.cuts import frozen_artifacts, state_snapshot, typed_platform
    from src.cuts import lifecycle
    from src.cuts.lifecycle import _resolve_model_scope_binding
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.models.master_model import MasterPlacementModel

    master, group_id, snapshot_a, compiled_a, _snapshot_b, _compiled_b = _build_scope_binding_world(
        frozen_artifacts,
        state_snapshot,
        typed_platform,
        lifecycle,
        generate_region_capacity_cuts,
        MasterPlacementModel,
    )
    snapshot_alt = _build_bound_snapshot(
        frozen_artifacts,
        state_snapshot,
        lifecycle,
        group_id=group_id,
        selected_poses=["boundary_pose_0"],
    )
    scope_a = compiled_a.plan.model_scope
    binding = _resolve_model_scope_binding(scope_a, snapshot_alt, master)

    assert snapshot_alt.digest != snapshot_a.digest
    assert scope_a.ghost_rect_digest == binding.ghost_rect_digest
    assert scope_a.domain_fingerprint == binding.master_domain_projection
    assert compiled_a.snapshot_digest != binding.snapshot_digest
    _assert_step_8_rejected_without_master_mutation(
        lifecycle,
        compiled_a,
        master,
        binding,
        tmp_path=tmp_path,
    )


@pytest.mark.xfail(
    condition=_stage_b5b_atomic_lowering_missing(),
    strict=True,
    reason="stage-B B5b 待实现: §4.11 原子 _lower_region_capacity_cut(precheck 前移)缺失",
)
def test_failed_lowering_preserves_master_proto_and_internal_caches(
    tmp_path: Path,
) -> None:
    from src.cuts import typed_platform
    from src.models.master_model import MasterPlacementModel

    assert inspect.isclass(typed_platform.CompiledCut)
    master = _build_real_tiny_master(MasterPlacementModel, ghost_rect=(1, 1))
    delegate = master._coordinate_delegate
    assert delegate is not None
    valid_group = str(master._group_id_by_instance["miner_001"])
    group_cell_weights = {valid_group: 1, "zz_missing_group": 1}
    # B5b landed the atomic _lower_region_capacity_cut (the xfail beacon gates
    # this test on its existence), so the delegate always carries it now.
    lower = delegate._lower_region_capacity_cut
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "before.pb")

    applied = lower(
        group_cell_weights=group_cell_weights,
        capacity=1,
        condition_lits=(),
    )

    assert applied is False
    assert _real_master_mutation_projection(master, proto_path=tmp_path / "after.pb") == before


def test_f6_failed_lowering_preserves_master_proto_and_internal_caches(
    tmp_path: Path,
) -> None:
    """§4.11 atomicity for F6 baseline-packing (pure-new B5b differential test).

    A pose with empty ``occupied_cells`` trips the precheck's per-pose guard, but
    only AFTER an earlier on-baseline pose would have minted its presence literal
    under the legacy interleaving.  The precheck front-move decides the whole cut
    before the first mutation, so the rejection leaves the model proto and every
    literal cache byte-for-byte unchanged.
    """
    from src.tests.cuts.test_stage_b_shape_packing_hall import (
        _ALL_POSES,
        _FACILITY_TYPE,
        _build_tiny_master,
    )

    master = _build_tiny_master(_ALL_POSES)
    group_id = str(master._group_id_by_instance["port_001"])
    # Corrupt a higher-indexed pose so the pose-loop guard fires downstream of an
    # on-baseline representable pose (the legacy mutate-then-False window).
    master.facility_pools[_FACILITY_TYPE][-1]["occupied_cells"] = []
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "before.pb")

    applied = master._lower_baseline_packing_cut(
        group_id=group_id,
        region_kind="left_baseline",
        capacity=1,
        condition_lits=(master.u_vars[35],),
    )

    assert applied is False
    assert _real_master_mutation_projection(master, proto_path=tmp_path / "after.pb") == before


def test_f7_failed_lowering_preserves_master_proto_and_internal_caches(
    tmp_path: Path,
) -> None:
    """F7 late rejection must not populate the lazy pose-id cache."""
    from src.tests.cuts.test_stage_b_power_hitting_set import (
        _FACILITY_TYPE,
        _GROUP_ID,
        _TARGET_POSE_ID,
        _build_master,
    )

    master = _build_master(skip_power_coverage=True)
    # Use a valid group and pose, then fail at the later coverer-table gate.
    # Before the pure pose-id precheck fix this returned False with an unchanged
    # proto but populated `_pose_idx_by_pose_id_cache`.
    del master._power_coverers_by_template_pose[_FACILITY_TYPE][1]
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "before.pb")

    applied = master._lower_power_pose_exclusion_cut(
        group_id=_GROUP_ID,
        pose_id=_TARGET_POSE_ID,
        blocked_cells={(2, 1)},
        condition_lits=(master.u_vars[0],),
    )

    assert applied is False
    assert _real_master_mutation_projection(master, proto_path=tmp_path / "after.pb") == before


def test_pose_present_precheck_and_mint_reject_duplicate_slot_keys_atomically(
    tmp_path: Path,
) -> None:
    """Malformed duplicate slot keys cannot split predicate and mint outcomes."""
    from dataclasses import replace

    from src.models.master_model import MasterPlacementModel

    master = _build_real_tiny_master(MasterPlacementModel, ghost_rect=(1, 1))
    delegate = master._coordinate_delegate
    assert delegate is not None
    group_id = str(master._group_id_by_instance["miner_001"])
    template = next(
        str(group["facility_type"]) for group in master._mandatory_groups if str(group["group_id"]) == group_id
    )
    pose_tuple = next(iter(delegate._template_pose_tuple_by_idx[template].values()))
    good_slot = delegate.mandatory_slots[group_id][0]
    bad_pose = (pose_tuple[0] + 1000, pose_tuple[1] + 1000, pose_tuple[2] + 1000)
    bad_slot = replace(
        good_slot,
        allowed_tuples=(bad_pose,),
        tuple_to_pose_idx={bad_pose: 0},
    )
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "before.pb")

    assert not delegate._pose_present_representable([bad_slot, good_slot], pose_tuple)
    assert delegate._pose_present_literal([bad_slot, good_slot], pose_tuple) is None
    assert _real_master_mutation_projection(master, proto_path=tmp_path / "after.pb") == before
