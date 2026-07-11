"""Runtime trust anchor for the frozen canonical ``certified_exact`` inputs.

Campaign hashes prove continuity only after a campaign has been created.  They
must not let a fresh campaign choose its own theorem by pinning whatever bytes
happen to be present on first launch.  The canonical project therefore has a
fixed input contract in source-controlled runtime code.

Toy projects remain supported for model-level regression tests.  The fixed
contract applies to the source checkout itself and to project roots that carry
``PROJECT_LOCK.md``.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

LOCKED_EXACT_PROJECT_MARKER = "PROJECT_LOCK.md"

LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS = (
    "data/proof_obligations/p1_2_proof_obligations.json",
    "data/proof_obligations/strong_status_write_allowlist.json",
    "scripts/check_p1_2_proof_obligations.py",
)
LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256 = (
    "8ff3b2c9beb64eaa77df9f11bae12d7cca690eaf2d6931d765e71046387cc513"
)
LOCKED_P1_2_CHECKER_PROTECTED_CALLEES = (
    "_check_step7_contract",
    "_check_source_digest_contract",
    "_check_source_digest_uses_contract",
    "_check_runtime_cache_policy",
    "_check_certified_cut_replay_contract",
    "_check_candidate_sink_replay_contract",
    "_check_certified_publication_boundary_contract",
    "_check_strong_status_write_allowlist_gate",
    "_check_isolated_exec_bytecode_binding_contract",
    "_check_evidence_and_tests",
    "_check_close_kernel_checker_self_binding",
    "_check_error_collector_integrity",
    "_check_main_self_integrity_preflight_shape",
    "_check_main_error_reporting_shape",
    "_check_error_collector_return_shape",
    "_check_proof_obligation_manifest_semantic_projection",
    "_check_close_kernel_contract",
    "_check_certified_artifact_contract_runtime_anchor",
    "_check_phase_gate_provenance_contract",
    "_check_phase_anchor",
    "_check_exact_session_atomic_snapshot_contract",
    "_check_independent_infeasibility_reverifier_contract",
    "_check_unique_top_level_bindings",
    "_check_terminal_final_result_violation_structure",
    "_check_terminal_project_precheck_structure",
    "_check_validate_terminal_solution_structure",
    "_check_terminal_ghost_pick_structure",
    "_check_exact_runtime_tcb_source_pins",
    "_check_l0_runtime_tcb_bindings",
    "_check_l0_supervisor_seal_body",
    "_check_literal_strict_slot_assignment",
    "_check_live_top_level_postwrite_guard",
    "_check_l0_child_verdict_dataflow",
    "_check_l0_supervisor_gate_result_flow",
    "_check_l0_supervisor_seal_state_body",
    "_check_child_module_toplevel_closed_world",
    "_check_true_child_runtime_tcb_source_pins",
    "_check_close_kernel_import_dependency_import_time_shape",
    "_check_true_verifier_entrypoint_body",
    "_check_child_verify_supervisor_domain_body",
    "_check_call_result_flow_to_truthy_consumer",
    "_check_call_assignment_no_rebind",
    "_check_expr_result_flow_to_truthy_consumer",
    "_check_true_verifier_child_domain_elevation_window",
    "_check_true_verifier_child_closed_world",
    "_check_true_verifier_child_return_dict_closed_world",
    "_check_child_project_records_body",
    "_check_child_project_candidate_records_direct_structure",
    "_check_child_fixed_witness_body",
    "_check_child_fixed_witness_direct_structure",
    "_check_publisher_transaction_shape",
    "_check_close_kernel_files_fully_pinned",
)

LOCKED_EXACT_ARTIFACT_PATHS = {
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "canonical_rules": "rules/canonical_rules.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "preprocess_plan": "rules/preprocess_plan.json",
}

LOCKED_EXACT_ARTIFACT_SHA256 = {
    "mandatory_exact_instances": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    "candidate_placements": "a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b",
    "canonical_rules": "32664aac6c075af7d57e001a0a2b11b9a8b9304d8513739414aaa7ed4501bcb3",
    "generic_io_requirements": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    "preprocess_plan": "1bcf0d13e1709cd7e04ddea439ee005e837584f2f66a1a921159d198019c9ed8",
}

LOCKED_EXACT_ARTIFACT_SIZE_BYTES = {
    "candidate_placements": 45_774_305,
}


class LockedExactArtifactContractError(ValueError):
    """Raised when a canonical project root does not match its frozen theorem."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = str(reason)
        super().__init__(f"{self.reason}: {detail}")


def certified_project_uses_locked_artifact_contract(project_root: Path) -> bool:
    """Return whether ``project_root`` represents the frozen canonical project.

    The source checkout is locked even if its marker is accidentally removed.
    A copied/installed project is locked when it carries ``PROJECT_LOCK.md``.
    A dangling or symlinked marker also selects the locked path, which is the
    fail-closed choice.
    """

    root = Path(project_root).resolve()
    source_root = Path(__file__).resolve().parents[2]
    if root == source_root:
        return True
    marker = root / LOCKED_EXACT_PROJECT_MARKER
    return marker.exists() or marker.is_symlink()


def _path_has_symlink_component(path: Path) -> bool:
    candidate = Path(path)
    if not candidate.parts:
        return False
    current = Path(candidate.anchor) if candidate.is_absolute() else Path()
    parts = candidate.parts[1:] if candidate.is_absolute() else candidate.parts
    for part in parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _reject_locked_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _locked_json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _load_locked_close_kernel_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_locked_json_object_pairs,
        parse_constant=_reject_locked_json_constant,
    )
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value


def _locked_close_kernel_manifest_projection_violation(path: Path) -> str | None:
    try:
        manifest = _load_locked_close_kernel_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return "locked_p1_2_close_kernel_manifest_invalid"
    declared = manifest.get("semantic_projection_sha256")
    if declared != LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256:
        return "locked_p1_2_close_kernel_semantic_projection_mismatch"
    return None


def _locked_target_name_bindings(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names.update(_locked_target_name_bindings(element))
        return names
    if isinstance(target, ast.Starred):
        return _locked_target_name_bindings(target.value)
    return set()


def _locked_import_bound_names(stmt: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(stmt, ast.Import):
        return {alias.asname or alias.name.split(".", 1)[0] for alias in stmt.names}
    return {alias.asname or alias.name for alias in stmt.names}


def _locked_pattern_bound_names(pattern: ast.AST) -> set[str]:
    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_MatchAs(self, node: ast.MatchAs) -> None:
            if node.name is not None:
                names.add(node.name)
            if node.pattern is not None:
                self.visit(node.pattern)

        def visit_MatchStar(self, node: ast.MatchStar) -> None:
            if node.name is not None:
                names.add(node.name)

        def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
            if node.rest is not None:
                names.add(node.rest)
            for pattern_node in node.patterns:
                self.visit(pattern_node)

    Visitor().visit(pattern)
    return names


def _locked_type_param_bound_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for type_param in getattr(node, "type_params", ()):
        name = getattr(type_param, "name", None)
        if isinstance(name, str):
            names.add(name)
        elif isinstance(name, ast.Name):
            names.add(name.id)
    return names


def _locked_type_alias_bound_names(stmt: ast.stmt) -> set[str]:
    type_alias_cls = getattr(ast, "TypeAlias", None)
    if type_alias_cls is None or not isinstance(stmt, type_alias_cls):
        return set()
    name_node = getattr(stmt, "name", None)
    if isinstance(name_node, ast.Name):
        return {name_node.id}
    return set()


def _locked_namedexpr_targets(node: ast.AST) -> set[str]:
    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, child: ast.Lambda) -> None:
            for default in child.args.defaults:
                self.visit(default)
            for default in child.args.kw_defaults:
                if default is not None:
                    self.visit(default)

        def visit_NamedExpr(self, child: ast.NamedExpr) -> None:
            names.update(_locked_target_name_bindings(child.target))
            self.visit(child.value)

    Visitor().visit(node)
    return names


def _locked_child_statement_bound_names(statements: Sequence[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        names.update(_locked_current_scope_bound_names(stmt))
    return names


def _locked_function_def_time_nodes(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    # round-20 (G1): mirror the checker's ``_function_def_time_nodes`` exactly so
    # the parent binding walker and the parent closed-world scan see every
    # def-time-evaluated expression -- including ``*args``/``**kwargs`` argument
    # annotations, which the previous manual list omitted.  A hidden
    # ``def f(*a: (main := 0))`` namedexpr (with future annotations off) would
    # otherwise rebind ``main`` at import time while the parent counted only one
    # top-level ``FunctionDef`` binding, making the parent mirror strictly wider
    # than the checker it decides to run.
    values: list[ast.AST] = [*node.decorator_list]
    values.extend(node.args.defaults)
    values.extend(default for default in node.args.kw_defaults if default is not None)
    values.extend(arg.annotation for arg in node.args.posonlyargs if arg.annotation is not None)
    values.extend(arg.annotation for arg in node.args.args if arg.annotation is not None)
    values.extend(arg.annotation for arg in node.args.kwonlyargs if arg.annotation is not None)
    if node.args.vararg is not None and node.args.vararg.annotation is not None:
        values.append(node.args.vararg.annotation)
    if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
        values.append(node.args.kwarg.annotation)
    if node.returns is not None:
        values.append(node.returns)
    values.extend(getattr(node, "type_params", ()))
    return values


def _locked_class_def_time_nodes(node: ast.ClassDef) -> list[ast.AST]:
    values: list[ast.AST] = [*node.decorator_list, *node.bases]
    values.extend(keyword.value for keyword in node.keywords)
    values.extend(getattr(node, "type_params", ()))
    return values


def _locked_current_scope_bound_names(stmt: ast.stmt) -> set[str]:
    names: set[str] = set()
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.add(stmt.name)
        names.update(_locked_type_param_bound_names(stmt))
        for value in _locked_function_def_time_nodes(stmt):
            names.update(_locked_namedexpr_targets(value))
        return names
    if isinstance(stmt, ast.ClassDef):
        names.add(stmt.name)
        names.update(_locked_type_param_bound_names(stmt))
        for value in _locked_class_def_time_nodes(stmt):
            names.update(_locked_namedexpr_targets(value))
        return names
    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            names.update(_locked_target_name_bindings(target))
        names.update(_locked_namedexpr_targets(stmt.value))
    elif isinstance(stmt, ast.AnnAssign):
        names.update(_locked_target_name_bindings(stmt.target))
        names.update(_locked_namedexpr_targets(stmt.annotation))
        if stmt.value is not None:
            names.update(_locked_namedexpr_targets(stmt.value))
    elif isinstance(stmt, ast.AugAssign):
        names.update(_locked_target_name_bindings(stmt.target))
        names.update(_locked_namedexpr_targets(stmt.value))
    elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
        names.update(_locked_import_bound_names(stmt))
    elif isinstance(stmt, ast.Delete):
        for target in stmt.targets:
            names.update(_locked_target_name_bindings(target))
    elif isinstance(stmt, (ast.Global, ast.Nonlocal)):
        names.update(stmt.names)
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        names.update(_locked_target_name_bindings(stmt.target))
        names.update(_locked_namedexpr_targets(stmt.iter))
        names.update(_locked_child_statement_bound_names(stmt.body))
        names.update(_locked_child_statement_bound_names(stmt.orelse))
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        for item in stmt.items:
            if item.optional_vars is not None:
                names.update(_locked_target_name_bindings(item.optional_vars))
            names.update(_locked_namedexpr_targets(item.context_expr))
        names.update(_locked_child_statement_bound_names(stmt.body))
    elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
        names.update(_locked_child_statement_bound_names(stmt.body))
        names.update(_locked_child_statement_bound_names(stmt.orelse))
        names.update(_locked_child_statement_bound_names(stmt.finalbody))
        for handler in stmt.handlers:
            if handler.type is not None:
                names.update(_locked_namedexpr_targets(handler.type))
            if handler.name is not None:
                names.add(handler.name)
            names.update(_locked_child_statement_bound_names(handler.body))
    elif isinstance(stmt, ast.While):
        # round-20 (G2): a ``while`` body executes at import/class-exec time, so a
        # rebind inside it (``while True: witness = _noop; break``) must count as a
        # scope binding just like ``if``/``for``/``with``.
        names.update(_locked_namedexpr_targets(stmt.test))
        names.update(_locked_child_statement_bound_names(stmt.body))
        names.update(_locked_child_statement_bound_names(stmt.orelse))
    elif isinstance(stmt, ast.If):
        names.update(_locked_namedexpr_targets(stmt.test))
        names.update(_locked_child_statement_bound_names(stmt.body))
        names.update(_locked_child_statement_bound_names(stmt.orelse))
    elif isinstance(stmt, ast.Match):
        names.update(_locked_namedexpr_targets(stmt.subject))
        for case in stmt.cases:
            names.update(_locked_pattern_bound_names(case.pattern))
            if case.guard is not None:
                names.update(_locked_namedexpr_targets(case.guard))
            names.update(_locked_child_statement_bound_names(case.body))
    else:
        names.update(_locked_type_alias_bound_names(stmt))
        names.update(_locked_namedexpr_targets(stmt))
    names.update(_locked_type_alias_bound_names(stmt))
    return names


def _locked_top_level_binding_points(tree: ast.Module, name: str) -> list[ast.stmt]:
    return [stmt for stmt in tree.body if name in _locked_current_scope_bound_names(stmt)]


def _locked_checker_has_canonical_entrypoint(tree: ast.Module) -> bool:
    if not tree.body or not isinstance(tree.body[-1], ast.If):
        return False
    stmt = tree.body[-1]
    test = stmt.test
    if not (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
        and not stmt.orelse
        and len(stmt.body) == 1
    ):
        return False
    raise_stmt = stmt.body[0]
    if not isinstance(raise_stmt, ast.Raise) or not isinstance(raise_stmt.exc, ast.Call):
        return False
    exc = raise_stmt.exc
    return (
        isinstance(exc.func, ast.Name)
        and exc.func.id == "SystemExit"
        and len(exc.args) == 1
        and not exc.keywords
        and isinstance(exc.args[0], ast.Call)
        and isinstance(exc.args[0].func, ast.Name)
        and exc.args[0].func.id == "main"
        and not exc.args[0].args
        and not exc.args[0].keywords
    )


_LOCKED_CHECKER_ALLOWED_IMPORTS = frozenset(
    {
        "ast",
        "builtins",
        "hashlib",
        "json",
        "shutil",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "weakref",
    }
)
_LOCKED_CHECKER_ALLOWED_FROM_IMPORTS = {
    "__future__": frozenset({"annotations"}),
    "pathlib": frozenset({"Path"}),
    "typing": frozenset({"Any", "Callable", "Iterator", "Mapping", "NoReturn", "Sequence"}),
}


_LOCKED_PROCESS_EXIT_CALL_NAMES = frozenset(
    {"exit", "quit", "os._exit", "sys.exit", "builtins.exit", "builtins.quit"}
)
_LOCKED_PROCESS_EXIT_ATTRS = frozenset({"_exit", "exit", "quit"})


def _locked_expr_qualified_name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = [node.attr]
        value = node.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
            return ".".join(reversed(parts))
    return None


def _locked_expr_is_process_exit_callable(node: ast.AST | None) -> str | None:
    name = _locked_expr_qualified_name(node)
    if name in _LOCKED_PROCESS_EXIT_CALL_NAMES:
        return name
    if isinstance(node, ast.Attribute) and node.attr in _LOCKED_PROCESS_EXIT_ATTRS:
        return name or node.attr
    return None


_LOCKED_IMPORT_TIME_REBIND_NAME_PRIMITIVES = frozenset(
    {
        "__import__",
        "compile",
        "delattr",
        "eval",
        "exec",
        "globals",
        "locals",
        "setattr",
        "vars",
    }
)
_LOCKED_IMPORT_TIME_REBIND_ATTR_PRIMITIVES = frozenset(
    {"__delattr__", "__dict__", "__setattr__", "__setitem__"}
)


def _locked_expr_contains_import_time_rebind_primitive(node: ast.AST | None) -> str | None:
    # round-16 (BLOCK 1): reject a namespace-write/dynamic-exec primitive hidden
    # in an import-time-evaluated expression of an otherwise-allowed top-level
    # statement (``_x = globals().__setitem__("main", lambda: 0)``, a FunctionDef
    # default, or a ClassDef body), which would rebind a protected global before
    # the canonical entrypoint runs.
    if node is None:
        return None
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in _LOCKED_IMPORT_TIME_REBIND_NAME_PRIMITIVES:
            return child.id
        if isinstance(child, ast.Attribute) and child.attr in _LOCKED_IMPORT_TIME_REBIND_ATTR_PRIMITIVES:
            return child.attr
    return None


def _locked_checker_import_statement_allowed(stmt: ast.Import | ast.ImportFrom) -> bool:
    if isinstance(stmt, ast.Import):
        return all(
            alias.asname is None and alias.name in _LOCKED_CHECKER_ALLOWED_IMPORTS
            for alias in stmt.names
        )
    if stmt.level != 0 or stmt.module not in _LOCKED_CHECKER_ALLOWED_FROM_IMPORTS:
        return False
    allowed_names = _LOCKED_CHECKER_ALLOWED_FROM_IMPORTS[stmt.module]
    return all(alias.asname is None and alias.name in allowed_names for alias in stmt.names)


def _locked_checker_class_body_statement_allowed(stmt: ast.stmt, *, is_first: bool) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    return (
        is_first
        and isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _locked_checker_top_level_class_is_inert_exception(stmt: ast.ClassDef) -> bool:
    """Only the checker exception carrier may be a top-level class.

    A top-level class body executes at import time, so ``global main; main = ...``
    inside one would silently rebind the module's runtime object while the pinned
    ``FunctionDef`` still passes the binding scan.  Reject every top-level class
    except the inert ``CheckError`` carrier.
    """

    return (
        stmt.name == "CheckError"
        and not stmt.decorator_list
        and tuple(ast.unparse(base) for base in stmt.bases) == ("RuntimeError",)
        and not stmt.keywords
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], ast.Pass)
    )


def _locked_checker_top_level_statement_allowed(
    stmt: ast.stmt, *, is_first: bool, is_last: bool
) -> bool:
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return _locked_checker_import_statement_allowed(stmt)
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # round-20 (G1): scan every def-time-evaluated expression, including
        # ``*args``/``**kwargs`` annotations and type params, for an import-time
        # rebind primitive.  The previous manual list omitted vararg/kwarg
        # annotations, letting ``def f(**kw: globals().__setitem__("main", ...))``
        # slip a namespace write past the closed world.
        for expr in _locked_function_def_time_nodes(stmt):
            if _locked_expr_contains_import_time_rebind_primitive(expr) is not None:
                return False
        return True
    if isinstance(stmt, ast.ClassDef):
        return _locked_checker_top_level_class_is_inert_exception(stmt)
    if isinstance(stmt, ast.Assign):
        if not (bool(stmt.targets) and all(isinstance(target, ast.Name) for target in stmt.targets)):
            return False
        if _locked_expr_contains_import_time_rebind_primitive(stmt.value) is not None:
            return False
        return _locked_expr_is_process_exit_callable(stmt.value) is None
    if isinstance(stmt, ast.AnnAssign):
        if not isinstance(stmt.target, ast.Name):
            return False
        if _locked_expr_contains_import_time_rebind_primitive(stmt.annotation) is not None:
            return False
        if _locked_expr_contains_import_time_rebind_primitive(stmt.value) is not None:
            return False
        return _locked_expr_is_process_exit_callable(stmt.value) is None
    if isinstance(stmt, ast.AugAssign):
        if not isinstance(stmt.target, ast.Name):
            return False
        if _locked_expr_contains_import_time_rebind_primitive(stmt.value) is not None:
            return False
        return _locked_expr_is_process_exit_callable(stmt.value) is None
    if (
        is_first
        and isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    ):
        return True
    if is_last and isinstance(stmt, ast.If):
        # The canonical ``if __name__ == "__main__"`` entrypoint is validated
        # independently by ``_locked_checker_has_canonical_entrypoint``.
        return True
    return False


def _locked_checker_top_level_closed_world_violation(tree: ast.Module) -> str | None:
    # Reject any module-level statement that could rebind a protected global at
    # import/exec time via a dynamic namespace write -- ``globals()["main"] = ...``
    # (an ``Assign`` with a ``Subscript`` target), ``sys.modules[__name__].x = ...``
    # (an ``Attribute`` target), a bare top-level ``setattr(...)``/``exec(...)``
    # call, or any top-level compound statement.  The binding-point count check
    # only sees ``Name`` targets, so a dynamic write would otherwise silently
    # rebind ``main`` after ``main`` is byte-pinned, bypassing every self-check.
    last_index = len(tree.body) - 1
    for index, stmt in enumerate(tree.body):
        if not _locked_checker_top_level_statement_allowed(
            stmt, is_first=(index == 0), is_last=(index == last_index)
        ):
            return (
                "locked_p1_2_close_kernel_checker_top_level_disallowed:"
                f"{type(stmt).__name__}:{getattr(stmt, 'lineno', '?')}"
            )
    return None


def _locked_close_kernel_checker_ast_anchor_violation(checker_path: Path) -> str | None:
    try:
        tree = ast.parse(checker_path.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError, ValueError):
        return "locked_p1_2_close_kernel_checker_ast_invalid"
    if not _locked_checker_has_canonical_entrypoint(tree):
        return "locked_p1_2_close_kernel_checker_entrypoint_invalid"
    top_level_violation = _locked_checker_top_level_closed_world_violation(tree)
    if top_level_violation is not None:
        return top_level_violation
    for name in ("main", *LOCKED_P1_2_CHECKER_PROTECTED_CALLEES):
        bindings = _locked_top_level_binding_points(tree, name)
        if len(bindings) != 1:
            return f"locked_p1_2_close_kernel_checker_protected_binding:{name}"
        binding = bindings[0]
        if not isinstance(binding, ast.FunctionDef) or binding.name != name:
            return f"locked_p1_2_close_kernel_checker_protected_binding:{name}"
        if binding.decorator_list:
            return f"locked_p1_2_close_kernel_checker_protected_binding:{name}"
    return None


def locked_p1_2_close_kernel_violation(
    project_root: Path,
    *,
    checker_timeout_seconds: float = 30.0,
) -> Optional[str]:
    """Return why the canonical V99 close-kernel authority is unavailable.

    Campaign source digests are continuity evidence. In locked projects, they
    must not become first-use trust anchors after the close-kernel authority is
    removed or redirected.
    """

    if not certified_project_uses_locked_artifact_contract(project_root):
        return None

    root = Path(project_root)
    for relative_path in LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS:
        path = root / relative_path
        if not path.exists():
            return f"locked_p1_2_close_kernel_missing:{relative_path}"
        if _path_has_symlink_component(path) or not path.is_file():
            return f"locked_p1_2_close_kernel_not_regular:{relative_path}"

    manifest_relative_path = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS[0]
    manifest_violation = _locked_close_kernel_manifest_projection_violation(
        root / manifest_relative_path
    )
    if manifest_violation is not None:
        return manifest_violation

    checker_relative_path = "scripts/check_p1_2_proof_obligations.py"
    checker_path = root / checker_relative_path
    checker_anchor_violation = _locked_close_kernel_checker_ast_anchor_violation(checker_path)
    if checker_anchor_violation is not None:
        return checker_anchor_violation
    # No "am I the checker?" self-skip: always re-verify by running the pinned
    # checker in a fresh isolated subprocess.  An identity-based skip (whether
    # keyed on ``sys.argv[0]`` -- forgeable via ``os.execv`` -- or
    # ``__main__.__file__``) is a trust exception that a launcher or in-process
    # state could abuse to bypass verification.  The child uses -I/-S/-B and a
    # fresh pycache prefix so parent PYTHONPATH/sitecustomize state and repository
    # bytecode caches cannot turn the checker process into a forged pass.  The
    # pinned checker (``check_p1_2_proof_obligations.py``) does not call this
    # function, so running it cannot recurse.  A future checker mode that needs
    # artifact hashing must pass an explicit non-recursive flag, not rely on a
    # bypassable identity skip.
    pycache_prefix = tempfile.mkdtemp(prefix="zmd_p1_2_close_kernel_pycache_")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                f"pycache_prefix={pycache_prefix}",
                str(checker_path),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=float(checker_timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "locked_p1_2_close_kernel_checker_timeout"
    except OSError as exc:
        return f"locked_p1_2_close_kernel_checker_error:{type(exc).__name__}"
    finally:
        shutil.rmtree(pycache_prefix, ignore_errors=True)
    if result.returncode != 0:
        return f"locked_p1_2_close_kernel_checker_rejected:{result.returncode}"
    return None


def validate_locked_p1_2_close_kernel(project_root: Path) -> None:
    """Fail closed before a locked project can self-seal a fresh campaign."""

    reason = locked_p1_2_close_kernel_violation(project_root)
    if reason is None:
        return
    raise LockedExactArtifactContractError(
        reason,
        (
            f"project_root={Path(project_root).resolve()}; restore the authoritative "
            "V99 close-kernel package instead of resealing the current tree"
        ),
    )


def locked_exact_artifact_contract_violation(
    *,
    project_root: Path,
    artifact_hashes: Mapping[str, str],
    artifact_sizes: Optional[Mapping[str, int]] = None,
) -> Optional[str]:
    """Return a stable fail-closed reason for a frozen-input mismatch."""

    if not certified_project_uses_locked_artifact_contract(project_root):
        return None

    for key, expected_hash in LOCKED_EXACT_ARTIFACT_SHA256.items():
        actual_hash = artifact_hashes.get(key)
        if actual_hash is None:
            return f"locked_exact_artifact_hash_missing:{key}"
        if str(actual_hash).lower() != str(expected_hash).lower():
            return f"locked_exact_artifact_hash_mismatch:{key}"

    actual_sizes = artifact_sizes
    if actual_sizes is None:
        root = Path(project_root)
        derived_sizes: dict[str, int] = {}
        for key in LOCKED_EXACT_ARTIFACT_SIZE_BYTES:
            try:
                derived_sizes[key] = int(
                    (root / LOCKED_EXACT_ARTIFACT_PATHS[key]).stat().st_size
                )
            except OSError:
                return f"locked_exact_artifact_size_unavailable:{key}"
        actual_sizes = derived_sizes

    for key, expected_size in LOCKED_EXACT_ARTIFACT_SIZE_BYTES.items():
        actual_size = actual_sizes.get(key)
        if actual_size is None:
            return f"locked_exact_artifact_size_missing:{key}"
        if int(actual_size) != int(expected_size):
            return f"locked_exact_artifact_size_mismatch:{key}"
    return None


def validate_locked_exact_artifact_contract(
    *,
    project_root: Path,
    artifact_hashes: Mapping[str, str],
    artifact_sizes: Optional[Mapping[str, int]] = None,
) -> None:
    """Reject a fresh/resumed canonical campaign whose theorem bytes drifted."""

    reason = locked_exact_artifact_contract_violation(
        project_root=project_root,
        artifact_hashes=artifact_hashes,
        artifact_sizes=artifact_sizes,
    )
    if reason is None:
        return
    key = reason.rsplit(":", 1)[-1]
    expected_hash = LOCKED_EXACT_ARTIFACT_SHA256.get(key)
    actual_hash = artifact_hashes.get(key)
    expected_size = LOCKED_EXACT_ARTIFACT_SIZE_BYTES.get(key)
    actual_size = None if artifact_sizes is None else artifact_sizes.get(key)
    detail_parts = [f"project_root={Path(project_root).resolve()}", f"artifact={key}"]
    if expected_hash is not None:
        detail_parts.extend(
            [f"expected_sha256={expected_hash}", f"actual_sha256={actual_hash}"]
        )
    if expected_size is not None:
        detail_parts.extend(
            [f"expected_size_bytes={expected_size}", f"actual_size_bytes={actual_size}"]
        )
    raise LockedExactArtifactContractError(reason, ", ".join(detail_parts))
