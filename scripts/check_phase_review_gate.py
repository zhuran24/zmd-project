#!/usr/bin/env python3
"""Check the manual Phase 1.2 review gate.

The Phase 1.2 "three clean reviews" rule is an owner-governance standard, not a
repo-derived proof protocol.  Earlier V37-V50 hardening tried to infer clean
credit from review reports, receipts, package metadata, and Git authority; that
created a large parser/state-machine attack surface.  This checker is therefore
intentionally small: it validates that the repository remains fail-closed unless
an explicit owner manual decision opens P1.3B.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Callable, NoReturn, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_DIR = PROJECT_ROOT / "data" / "review_gates"
LIFECYCLE_PATH = PROJECT_ROOT / "src" / "cuts" / "lifecycle.py"
FIXED_WITNESS_VERIFIER_PATH = (
    PROJECT_ROOT / "src" / "search" / "terminal_fixed_witness_verifier.py"
)
FIXED_WITNESS_CAPSULE_PATH = PROJECT_ROOT / "src" / "search" / "terminal_fixed_witness_capsule.py"
REQUIRED_FIXED_WITNESS_VERIFIER_FUNCTIONS = (
    "verify_terminal_fixed_witness",
    "project_terminal_fixed_witness_records_for_sink",
)

APPROVED_REVIEW_ANCHOR = "v99_p1_2_close_kernel_sealing"
BLOCKED_STATUSES = {"blocked_manual_review_count", "blocked", "open"}
CLOSED_STATUS = "closed_manual_owner_decision"
COUNTING_AUTHORITY = "owner_manual_count_outside_repo"
RECEIPT_ROLE = "informational_record_only"


class GateError(RuntimeError):
    pass


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise GateError(f"invalid JSON constant {value!r}; phase-gate JSON must be strict JSON")


def load_gate(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except GateError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot read {rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{rel(path)} must contain a JSON object")
    return value


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GateError(f"{label} must be a list")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise GateError(f"{label} must be a boolean")
    return value


def require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GateError(f"{label} must be an integer")
    return value


def require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{label} must be a non-empty string")
    return value


def _check_allowed_top_level_keys(gate: dict[str, Any]) -> list[str]:
    allowed = {
        "schema_version",
        "gate_id",
        "phase",
        "status",
        "updated_at",
        "summary",
        "current_review_anchor",
        "manual_review_standard",
        "owner_manual_state",
        "owner_manual_decision",
        "next_phase_entry",
        "informational_history",
        "required_doc_markers",
        "source_boundaries",
        "receipt_policy",
    }
    old_auto_authority_keys = {
        "counters",
        "last_reset",
        "review_history",
        "current_review_package",
        "clean_review_receipt_protocol",
        "counter_domains",
    }
    errors: list[str] = []
    for key in sorted(set(gate) - allowed):
        errors.append(f"unsupported top-level key for manual phase gate: {key}")
    for key in sorted(old_auto_authority_keys & set(gate)):
        errors.append(
            f"manual phase gate must not contain repo-derived clean-count authority key: {key}"
        )
    return errors


def _check_manual_review_standard(standard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = require_int(
        standard.get("required_consecutive_clean_full_reviews"),
        "manual_review_standard.required_consecutive_clean_full_reviews",
    )
    if required != 3:
        errors.append("manual_review_standard.required_consecutive_clean_full_reviews must be 3")
    authority = require_str(standard.get("counting_authority"), "manual_review_standard.counting_authority")
    if authority != COUNTING_AUTHORITY:
        errors.append(
            "manual_review_standard.counting_authority must be "
            f"{COUNTING_AUTHORITY!r}, not {authority!r}"
        )
    derives = require_bool(
        standard.get("repo_derives_clean_count_from_receipts"),
        "manual_review_standard.repo_derives_clean_count_from_receipts",
    )
    if derives:
        errors.append("repo must not derive clean-review count from receipts")
    receipt_role = require_str(standard.get("receipt_role"), "manual_review_standard.receipt_role")
    if receipt_role != RECEIPT_ROLE:
        errors.append(f"manual_review_standard.receipt_role must be {RECEIPT_ROLE!r}")
    for index, raw_class in enumerate(
        require_list(
            standard.get("finding_classes_that_break_manual_clean_review"),
            "manual_review_standard.finding_classes_that_break_manual_clean_review",
        )
    ):
        require_str(raw_class, f"manual_review_standard.finding_classes_that_break_manual_clean_review[{index}]")
    return errors


def _check_owner_manual_state(state: dict[str, Any], *, current_anchor: str) -> list[str]:
    errors: list[str] = []
    if require_str(state.get("counting_authority"), "owner_manual_state.counting_authority") != COUNTING_AUTHORITY:
        errors.append("owner_manual_state.counting_authority must match manual review standard")
    owner_anchor = require_str(state.get("current_review_anchor"), "owner_manual_state.current_review_anchor")
    if owner_anchor != current_anchor:
        errors.append("owner_manual_state.current_review_anchor must match current_review_anchor")
    if owner_anchor != APPROVED_REVIEW_ANCHOR:
        errors.append(
            "owner_manual_state.current_review_anchor must equal approved checker anchor "
            f"{APPROVED_REVIEW_ANCHOR!r}"
        )
    if require_bool(
        state.get("repo_derives_clean_count_from_receipts"),
        "owner_manual_state.repo_derives_clean_count_from_receipts",
    ):
        errors.append("owner_manual_state must keep repo_derives_clean_count_from_receipts=false")
    if require_bool(state.get("p1_3b_entry_allowed"), "owner_manual_state.p1_3b_entry_allowed"):
        # The state may be allowed only when the explicit decision object below is present.
        pass
    owner_count_status = require_str(state.get("owner_clean_count_status"), "owner_manual_state.owner_clean_count_status")
    if owner_count_status != "maintained_outside_repo":
        errors.append("owner_manual_state.owner_clean_count_status must be maintained_outside_repo")
    return errors


def _check_owner_manual_decision(raw_decision: Any, *, next_allowed: bool) -> list[str]:
    errors: list[str] = []
    if not next_allowed:
        if raw_decision is None:
            return errors
        decision = require_mapping(raw_decision, "owner_manual_decision")
        if decision.get("p1_3b_entry_allowed") is True:
            errors.append("owner_manual_decision cannot allow P1.3B while next_phase_entry.allowed=false")
        return errors

    decision = require_mapping(raw_decision, "owner_manual_decision")
    if not require_bool(decision.get("p1_3b_entry_allowed"), "owner_manual_decision.p1_3b_entry_allowed"):
        errors.append("owner_manual_decision.p1_3b_entry_allowed must be true when next phase is allowed")
    if require_str(decision.get("counting_authority"), "owner_manual_decision.counting_authority") != COUNTING_AUTHORITY:
        errors.append("owner_manual_decision.counting_authority must be owner_manual_count_outside_repo")
    for key in ("decision_id", "decided_by", "decided_at", "decision_note"):
        require_str(decision.get(key), f"owner_manual_decision.{key}")
    if require_bool(
        decision.get("acknowledges_repo_does_not_prove_clean_count"),
        "owner_manual_decision.acknowledges_repo_does_not_prove_clean_count",
    ) is not True:
        errors.append("owner_manual_decision must acknowledge repo does not prove clean count")
    if require_bool(
        decision.get("acknowledges_owner_verified_three_clean_reviews"),
        "owner_manual_decision.acknowledges_owner_verified_three_clean_reviews",
    ) is not True:
        errors.append("owner_manual_decision must acknowledge owner-verified three clean reviews")
    return errors


def _step_8_apply_to_master_is_fail_closed() -> bool:
    try:
        tree = ast.parse(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot parse {rel(LIFECYCLE_PATH)}: {exc}") from exc
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "step_8_apply_to_master":
            for child in ast.walk(node):
                if isinstance(child, ast.Raise):
                    raised = child.exc
                    if (
                        isinstance(raised, ast.Call)
                        and isinstance(raised.func, ast.Name)
                        and raised.func.id == "NotImplementedError"
                    ):
                        return True
                    if isinstance(raised, ast.Name) and raised.id == "NotImplementedError":
                        return True
            return False
    raise GateError("function not found in src/cuts/lifecycle.py: step_8_apply_to_master")


def _check_step_8_boundary(*, next_allowed: bool) -> list[str]:
    if next_allowed:
        return []
    if _step_8_apply_to_master_is_fail_closed():
        return []
    return ["P1.3B is not manually allowed, so step_8_apply_to_master must remain fail-closed"]


def _parse_python(path: Path) -> ast.Module:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise GateError(f"cannot parse {rel(path)}: {exc}") from exc
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_p1_2_parent", parent)
    return tree


def _function_def(tree: ast.Module, name: str, *, path: Path) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise GateError(f"function not found in {rel(path)}: {name}")


def _source_text(path: Path, node: ast.AST) -> str:
    source = path.read_text(encoding="utf-8")
    return ast.get_source_segment(source, node) or ""


def _ast_root(node: ast.AST) -> ast.AST:
    root = node
    while True:
        parent = getattr(root, "_p1_2_parent", None)
        if parent is None:
            return root
        root = parent


def _store_target_names(target: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(target):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
    return names


def _assign_targets(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return set()
    names: set[str] = set()
    for target in targets:
        names.update(_store_target_names(target))
    return names


def _constant_bool_value(
    value: ast.AST | None,
    false_names: set[str] | None = None,
    true_names: set[str] | None = None,
) -> bool | None:
    if isinstance(value, ast.Constant):
        return bool(value.value)
    if isinstance(value, ast.Name):
        if value.id == "TYPE_CHECKING" or value.id in (false_names or set()):
            return False
        if value.id in (true_names or set()):
            return True
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not):
        operand_value = _constant_bool_value(value.operand, false_names, true_names)
        if operand_value is not None:
            return not operand_value
    if isinstance(value, ast.BoolOp):
        if isinstance(value.op, ast.And):
            for operand in value.values:
                operand_value = _constant_bool_value(operand, false_names, true_names)
                if operand_value is False:
                    return False
                if operand_value is None:
                    return None
            return True
        if isinstance(value.op, ast.Or):
            for operand in value.values:
                operand_value = _constant_bool_value(operand, false_names, true_names)
                if operand_value is True:
                    return True
                if operand_value is None:
                    return None
            return False
    return None


def _is_constant_false(value: ast.AST | None) -> bool:
    return _constant_bool_value(value) is False


def _module_constant_bool_names(node: ast.AST) -> tuple[set[str], set[str]]:
    root = _ast_root(node)
    if not isinstance(root, ast.Module):
        return set(), set()
    false_names: set[str] = set()
    true_names: set[str] = set()
    for statement in root.body:
        targets = _assign_targets(statement)
        if not targets:
            continue
        value = None
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = _constant_bool_value(statement.value, false_names, true_names)
        if value is False:
            false_names.update(targets)
            true_names.difference_update(targets)
        elif value is True:
            true_names.update(targets)
            false_names.difference_update(targets)
        else:
            false_names.difference_update(targets)
            true_names.difference_update(targets)
    return false_names, true_names


def _module_constant_false_names(node: ast.AST) -> set[str]:
    false_names, _true_names = _module_constant_bool_names(node)
    return false_names


def _function_scope_binding_names(node: ast.AST) -> set[str]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    names = {
        argument.arg
        for argument in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        )
    }
    if node.args.vararg is not None:
        names.add(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.add(node.args.kwarg.arg)

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.generic_visit(child)
            else:
                names.add(child.name)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.generic_visit(child)
            else:
                names.add(child.name)

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            names.add(child.name)

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_Assign(self, child: ast.Assign) -> None:
            names.update(_assign_targets(child))
            self.visit(child.value)

        def visit_AnnAssign(self, child: ast.AnnAssign) -> None:
            names.update(_assign_targets(child))
            if child.value is not None:
                self.visit(child.value)

        def visit_AugAssign(self, child: ast.AugAssign) -> None:
            names.update(_assign_targets(child))
            self.visit(child.value)

        def visit_For(self, child: ast.For) -> None:
            names.update(_store_target_names(child.target))
            self.generic_visit(child)

        def visit_AsyncFor(self, child: ast.AsyncFor) -> None:
            names.update(_store_target_names(child.target))
            self.generic_visit(child)

        def visit_With(self, child: ast.With) -> None:
            for item in child.items:
                if item.optional_vars is not None:
                    names.update(_store_target_names(item.optional_vars))
            self.generic_visit(child)

        def visit_AsyncWith(self, child: ast.AsyncWith) -> None:
            for item in child.items:
                if item.optional_vars is not None:
                    names.update(_store_target_names(item.optional_vars))
            self.generic_visit(child)

        def visit_ExceptHandler(self, child: ast.ExceptHandler) -> None:
            if child.name is not None:
                names.add(child.name)
            self.generic_visit(child)

        def visit_Import(self, child: ast.Import) -> None:
            for alias in child.names:
                names.add(alias.asname or alias.name.split(".")[0])

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            for alias in child.names:
                names.add(alias.asname or alias.name)

    Visitor().visit(node)
    return names


def _constant_guard_value(
    test: ast.AST,
    false_names: set[str],
    true_names: set[str],
) -> bool | None:
    return _constant_bool_value(test, false_names, true_names)


def _reachable_direct_call(node: ast.AST, predicate: Callable[[ast.Call], bool]) -> bool:
    found = False
    module_false_names, module_true_names = _module_constant_bool_names(node)
    function_bindings = _function_scope_binding_names(node)
    false_names = module_false_names - function_bindings
    true_names = module_true_names - function_bindings

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.false_names = set(false_names)
            self.true_names = set(true_names)

        def visit_statements(self, statements: Sequence[ast.stmt]) -> None:
            for statement in statements:
                self.visit(statement)
                if isinstance(statement, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    break

        def _record_assignment(self, targets: set[str], value: bool | None) -> None:
            if value is False:
                self.false_names.update(targets)
                self.true_names.difference_update(targets)
            elif value is True:
                self.true_names.update(targets)
                self.false_names.difference_update(targets)
            else:
                self.false_names.difference_update(targets)
                self.true_names.difference_update(targets)

        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.visit_statements(child.body)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.visit_statements(child.body)

        def visit_Module(self, child: ast.Module) -> None:
            if child is node:
                self.visit_statements(child.body)

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_Assign(self, child: ast.Assign) -> None:
            self.visit(child.value)
            targets = _assign_targets(child)
            value = _constant_bool_value(child.value, self.false_names, self.true_names)
            self._record_assignment(targets, value)

        def visit_AnnAssign(self, child: ast.AnnAssign) -> None:
            if child.value is not None:
                self.visit(child.value)
            targets = _assign_targets(child)
            value = _constant_bool_value(child.value, self.false_names, self.true_names)
            self._record_assignment(targets, value)

        def visit_AugAssign(self, child: ast.AugAssign) -> None:
            self.visit(child.value)
            targets = _assign_targets(child)
            self.false_names.difference_update(targets)
            self.true_names.difference_update(targets)

        def visit_If(self, child: ast.If) -> None:
            guard_value = _constant_guard_value(child.test, self.false_names, self.true_names)
            if guard_value is False:
                self.visit_statements(child.orelse)
                return
            if guard_value is True:
                self.visit_statements(child.body)
                return
            self.visit(child.test)
            saved_false = set(self.false_names)
            saved_true = set(self.true_names)
            self.visit_statements(child.body)
            self.false_names = set(saved_false)
            self.true_names = set(saved_true)
            self.visit_statements(child.orelse)
            self.false_names = saved_false
            self.true_names = saved_true

        def visit_While(self, child: ast.While) -> None:
            guard_value = _constant_guard_value(child.test, self.false_names, self.true_names)
            if guard_value is False:
                self.visit_statements(child.orelse)
                return
            self.visit(child.test)
            saved_false = set(self.false_names)
            saved_true = set(self.true_names)
            self.visit_statements(child.body)
            self.false_names = set(saved_false)
            self.true_names = set(saved_true)
            self.visit_statements(child.orelse)
            self.false_names = saved_false
            self.true_names = saved_true

        def visit_IfExp(self, child: ast.IfExp) -> None:
            guard_value = _constant_guard_value(child.test, self.false_names, self.true_names)
            if guard_value is False:
                self.visit(child.orelse)
                return
            if guard_value is True:
                self.visit(child.body)
                return
            self.visit(child.test)
            self.visit(child.body)
            self.visit(child.orelse)

        def visit_BoolOp(self, child: ast.BoolOp) -> None:
            if isinstance(child.op, ast.And):
                for operand in child.values:
                    self.visit(operand)
                    operand_value = _constant_bool_value(operand, self.false_names, self.true_names)
                    if operand_value is False:
                        break
                return
            if isinstance(child.op, ast.Or):
                for operand in child.values:
                    self.visit(operand)
                    operand_value = _constant_bool_value(operand, self.false_names, self.true_names)
                    if operand_value is True:
                        break
                return
            self.generic_visit(child)

        def visit_Import(self, child: ast.Import) -> None:
            for alias in child.names:
                name = alias.asname or alias.name.split(".")[0]
                self.false_names.discard(name)
                self.true_names.discard(name)

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            for alias in child.names:
                name = alias.asname or alias.name
                self.false_names.discard(name)
                self.true_names.discard(name)

        def visit_For(self, child: ast.For) -> None:
            targets = _store_target_names(child.target)
            self.false_names.difference_update(targets)
            self.true_names.difference_update(targets)
            self.visit(child.iter)
            self.visit_statements(child.body)
            self.visit_statements(child.orelse)

        def visit_AsyncFor(self, child: ast.AsyncFor) -> None:
            targets = _store_target_names(child.target)
            self.false_names.difference_update(targets)
            self.true_names.difference_update(targets)
            self.visit(child.iter)
            self.visit_statements(child.body)
            self.visit_statements(child.orelse)

        def visit_With(self, child: ast.With) -> None:
            for item in child.items:
                self.visit(item.context_expr)
                if item.optional_vars is not None:
                    targets = _store_target_names(item.optional_vars)
                    self.false_names.difference_update(targets)
                    self.true_names.difference_update(targets)
            self.visit_statements(child.body)

        def visit_AsyncWith(self, child: ast.AsyncWith) -> None:
            for item in child.items:
                self.visit(item.context_expr)
                if item.optional_vars is not None:
                    targets = _store_target_names(item.optional_vars)
                    self.false_names.difference_update(targets)
                    self.true_names.difference_update(targets)
            self.visit_statements(child.body)

        def visit_Try(self, child: ast.Try) -> None:
            self.visit_statements(child.body)
            for handler in child.handlers:
                self.visit(handler)
            self.visit_statements(child.orelse)
            self.visit_statements(child.finalbody)

        def visit_ExceptHandler(self, child: ast.ExceptHandler) -> None:
            if child.name is not None:
                self.false_names.discard(child.name)
                self.true_names.discard(child.name)
            if child.type is not None:
                self.visit(child.type)
            self.visit_statements(child.body)

        def visit_Call(self, child: ast.Call) -> None:
            nonlocal found
            if predicate(child):
                found = True
            self.generic_visit(child)

    Visitor().visit(node)
    return found


def _direct_calls_name(node: ast.AST, name: str) -> bool:
    return _reachable_direct_call(
        node,
        lambda child: isinstance(child.func, ast.Name) and child.func.id == name,
    )


def _direct_calls_attr(node: ast.AST, attr: str) -> bool:
    return _reachable_direct_call(
        node,
        lambda child: isinstance(child.func, ast.Attribute) and child.func.attr == attr,
    )


def _function_imports_exact_name(node: ast.AST, *, module: str, name: str) -> bool:
    found = False

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.generic_visit(child)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.generic_visit(child)

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            nonlocal found
            if child.level == 0 and child.module == module:
                for alias in child.names:
                    if alias.name == name and alias.asname is None:
                        found = True

    Visitor().visit(node)
    return found


def _fixed_witness_verifier_semantics_errors(*, tree: ast.Module, path: Path) -> list[str]:
    errors: list[str] = []
    verify_fn = _function_def(tree, "verify_terminal_fixed_witness", path=path)
    verify_source = _source_text(path, verify_fn)
    if not (
        _direct_calls_name(verify_fn, "PortBindingModel")
        and _direct_calls_attr(verify_fn, "from_placement_core")
        and 'binding_status != "FEASIBLE"' in verify_source
        and 'routing_status != "FEASIBLE"' in verify_source
        and "_connector_body_exclusion_violation" in verify_source
    ):
        errors.append(
            "verify_terminal_fixed_witness must rerun binding and routing through "
            "PortBindingModel and RoutingSubproblem"
        )
    if "_accept(" not in verify_source or "_reject(" not in verify_source:
        errors.append("verify_terminal_fixed_witness must return explicit accept/reject verdicts")

    project_fn = _function_def(tree, "project_terminal_fixed_witness_records_for_sink", path=path)
    if not _direct_calls_name(project_fn, "_project_terminal_fixed_witness_records_for_unverified_verdict"):
        errors.append("public fixed-witness projection wrapper must reject unverified in-process verdicts")
    try:
        projection_fn = _function_def(tree, "_project_terminal_fixed_witness_records_from_capsule", path=path)
    except GateError:
        errors.append("fixed-witness projection must demote rejected terminal records")
    else:
        projection_source = _source_text(path, projection_fn)
        for token in (
            'record["status"] = _PROJECTED_UNPROVEN',
            'record.pop("solution", None)',
            "record.pop(CANDIDATE_PROOF_FIELD, None)",
            "publishable = reason is None",
        ):
            if token not in projection_source:
                errors.append(
                    "fixed-witness projection must demote rejected terminal records"
                )
                break
    return errors


def _fixed_witness_capsule_semantics_errors(*, path: Path) -> list[str]:
    if not path.exists():
        return [f"fixed-witness capsule missing: {rel(path)}"]
    tree = _parse_python(path)
    errors: list[str] = []
    build_fn = _function_def(tree, "build_terminal_fixed_witness_projection_at_sink", path=path)
    if not _direct_calls_name(build_fn, "_invoke_isolated_capsule"):
        errors.append("fixed-witness capsule must invoke isolated replay")
    for required_call in (
        "_verdict_from_capsule_response",
        "_capsule_response_violation",
        "_project_terminal_fixed_witness_records_from_capsule",
    ):
        if not _direct_calls_name(build_fn, required_call):
            errors.append(f"fixed-witness capsule build path must call {required_call}")

    try:
        invoke_fn = _function_def(tree, "_invoke_isolated_capsule", path=path)
    except GateError:
        errors.append("fixed-witness capsule isolated replay must launch python -I with a nonce")
        errors.append("fixed-witness capsule subprocess boundary must remain explicit and non-shell")
    else:
        invoke_source = _source_text(path, invoke_fn)
        if not _direct_calls_attr(invoke_fn, "run") or '"-I"' not in invoke_source or "nonce" not in invoke_source:
            errors.append("fixed-witness capsule isolated replay must launch python -I with a nonce")
        if "check=False" not in invoke_source or "shell=True" in invoke_source:
            errors.append("fixed-witness capsule subprocess boundary must remain explicit and non-shell")

    try:
        execute_fn = _function_def(tree, "_execute_isolated_capsule_request", path=path)
    except GateError:
        errors.append("fixed-witness capsule must import verify_terminal_fixed_witness from the real verifier module")
        errors.append("fixed-witness capsule must execute verify_terminal_fixed_witness")
    else:
        execute_source = _source_text(path, execute_fn)
        if not _function_imports_exact_name(
            execute_fn,
            module="src.search.terminal_fixed_witness_verifier",
            name="verify_terminal_fixed_witness",
        ):
            errors.append("fixed-witness capsule must import verify_terminal_fixed_witness from the real verifier module")
        if not _direct_calls_name(execute_fn, "verify_terminal_fixed_witness"):
            errors.append("fixed-witness capsule must execute verify_terminal_fixed_witness")
        for token in (
            "compute_exact_artifact_hashes",
            "_materialize_replay_snapshot",
            "canonical_state_bytes_for_fixed_witness",
        ):
            if token not in execute_source:
                errors.append(f"fixed-witness capsule execution path missing binding token: {token}")

    try:
        response_fn = _function_def(tree, "_capsule_response_violation", path=path)
    except GateError:
        errors.append("fixed-witness capsule response must gate publishable verdicts")
    else:
        response_source = _source_text(path, response_fn)
        for token in (
            "verdict.publishable",
            "verdict.binding_status",
            "verdict.routing_status",
            '"FEASIBLE"',
        ):
            if token not in response_source:
                errors.append("fixed-witness capsule response must gate publishable verdicts")
                break
    return errors


def _fixed_witness_verifier_functions_present() -> list[str]:
    """Require the P1.2-FIX-1 fixed-witness terminal verifier to remain present.

    The certified publish path projects every terminal witness ``(R*, pi*)``
    through this verifier; a closed phase gate re-enables publication through the
    P1.2-FIX-2 open-gate, so the gate must fail closed if the verifier module or
    its public entry points are removed.  This is checked for every gate state so
    that opening P1.3B never silently drops the requirement (the prior generic
    "stay blocked" anchor carried no witness predicate, so lifting it lost the
    binding entirely).
    """
    if not FIXED_WITNESS_VERIFIER_PATH.exists():
        return [f"fixed-witness terminal verifier missing: {rel(FIXED_WITNESS_VERIFIER_PATH)}"]
    try:
        tree = _parse_python(FIXED_WITNESS_VERIFIER_PATH)
    except GateError as exc:
        return [f"cannot parse {rel(FIXED_WITNESS_VERIFIER_PATH)}: {exc}"]
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    errors: list[str] = []
    for required in REQUIRED_FIXED_WITNESS_VERIFIER_FUNCTIONS:
        if required not in defined:
            errors.append(
                f"fixed-witness terminal verifier must define {required} "
                f"(P1.2-FIX-1 publish-path binding)"
            )
    try:
        errors.extend(
            _fixed_witness_verifier_semantics_errors(
                tree=tree,
                path=FIXED_WITNESS_VERIFIER_PATH,
            )
        )
    except GateError as exc:
        errors.append(str(exc))
    try:
        errors.extend(_fixed_witness_capsule_semantics_errors(path=FIXED_WITNESS_CAPSULE_PATH))
    except GateError as exc:
        errors.append(str(exc))
    return errors


def _check_fixed_witness_close_binding() -> list[str]:
    """Bind the manual phase gate to the FIX-1 fixed-witness verifier (P1.2-FIX-3).

    Enforced for every gate state.  A blocked gate keeps the verifier in the
    publish path; an owner-opened gate inherits the same requirement instead of
    falling back to a shape + acknowledgement-only close.
    """
    return _fixed_witness_verifier_functions_present()


def _check_doc_markers(markers: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, raw_marker in enumerate(markers):
        marker = require_mapping(raw_marker, f"required_doc_markers[{index}]")
        rel_path = require_str(marker.get("path"), f"required_doc_markers[{index}].path")
        needle = require_str(marker.get("contains"), f"required_doc_markers[{index}].contains")
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"required doc marker target missing: {rel_path}")
            continue
        text = full_path.read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"required marker not found in {rel_path}: {needle!r}")
    return errors


def _check_informational_history(history: list[Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw_entry in enumerate(history):
        entry = require_mapping(raw_entry, f"informational_history[{index}]")
        package = require_str(entry.get("package"), f"informational_history[{index}].package")
        if package in seen:
            errors.append(f"duplicate informational history package: {package}")
        seen.add(package)
        require_str(entry.get("classification"), f"informational_history[{index}].classification")
        for path_index, raw_path in enumerate(
            require_list(entry.get("evidence_paths", []), f"informational_history[{index}].evidence_paths")
        ):
            rel_path = require_str(raw_path, f"informational_history[{index}].evidence_paths[{path_index}]")
            if not (PROJECT_ROOT / rel_path).exists():
                errors.append(f"informational history evidence path missing: {rel_path}")
    return errors


def check_gate(path: Path) -> tuple[str, list[str]]:
    gate = load_gate(path)
    errors: list[str] = []
    errors.extend(_check_allowed_top_level_keys(gate))

    try:
        schema_version = require_int(gate.get("schema_version"), "schema_version")
    except GateError as exc:
        errors.append(str(exc))
        schema_version = -1
    if schema_version != 2:
        errors.append("manual phase gate schema_version must be 2")

    gate_id = require_str(gate.get("gate_id"), "gate_id")
    status = require_str(gate.get("status"), "status")
    if status not in BLOCKED_STATUSES | {CLOSED_STATUS}:
        errors.append(f"unsupported manual phase gate status: {status}")
    current_anchor = require_str(gate.get("current_review_anchor"), "current_review_anchor")
    if current_anchor != APPROVED_REVIEW_ANCHOR:
        errors.append(
            "current_review_anchor must equal approved checker anchor "
            f"{APPROVED_REVIEW_ANCHOR!r}"
        )

    standard = require_mapping(gate.get("manual_review_standard"), "manual_review_standard")
    errors.extend(_check_manual_review_standard(standard))

    owner_state = require_mapping(gate.get("owner_manual_state"), "owner_manual_state")
    errors.extend(_check_owner_manual_state(owner_state, current_anchor=current_anchor))
    owner_state_allowed = require_bool(owner_state.get("p1_3b_entry_allowed"), "owner_manual_state.p1_3b_entry_allowed")

    next_phase_entry = require_mapping(gate.get("next_phase_entry"), "next_phase_entry")
    next_allowed = require_bool(next_phase_entry.get("allowed"), "next_phase_entry.allowed")
    if owner_state_allowed != next_allowed:
        errors.append("owner_manual_state.p1_3b_entry_allowed must match next_phase_entry.allowed")
    if status in BLOCKED_STATUSES and next_allowed:
        errors.append("blocked/open manual gate must not allow P1.3B")
    if status == CLOSED_STATUS and not next_allowed:
        errors.append("closed manual gate should allow P1.3B")
    if require_str(next_phase_entry.get("authority"), "next_phase_entry.authority") != "owner_manual_decision_only":
        errors.append("next_phase_entry.authority must be owner_manual_decision_only")

    try:
        errors.extend(_check_owner_manual_decision(gate.get("owner_manual_decision"), next_allowed=next_allowed))
    except GateError as exc:
        errors.append(str(exc))
    errors.extend(_check_step_8_boundary(next_allowed=next_allowed))
    errors.extend(_check_fixed_witness_close_binding())
    try:
        errors.extend(_check_informational_history(require_list(gate.get("informational_history", []), "informational_history")))
        errors.extend(_check_doc_markers(require_list(gate.get("required_doc_markers", []), "required_doc_markers")))
    except GateError as exc:
        errors.append(str(exc))

    try:
        receipt_policy = require_mapping(gate.get("receipt_policy"), "receipt_policy")
        if require_str(receipt_policy.get("role"), "receipt_policy.role") != RECEIPT_ROLE:
            errors.append("receipt_policy.role must be informational_record_only")
        if require_bool(receipt_policy.get("can_open_p1_3b"), "receipt_policy.can_open_p1_3b"):
            errors.append("receipt_policy.can_open_p1_3b must be false")
    except GateError as exc:
        errors.append(str(exc))

    summary = (
        f"{gate_id}: status={status}, anchor={current_anchor}, "
        f"next_allowed={next_allowed}, counting_authority={COUNTING_AUTHORITY}"
    )
    return summary, errors


def _gate_paths() -> list[Path]:
    return sorted(DEFAULT_GATE_DIR.glob("phase_*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-ready",
        nargs="*",
        metavar="GATE_ID",
        help="Fail unless the named gate(s) are manually opened by owner decision.",
    )
    args = parser.parse_args()

    required_ready = set(args.require_ready or [])
    any_errors = False
    ready_by_gate: dict[str, bool] = {}

    for path in _gate_paths():
        try:
            summary, errors = check_gate(path)
            gate_id = require_str(load_gate(path).get("gate_id"), "gate_id")
            next_allowed = require_bool(
                require_mapping(load_gate(path).get("next_phase_entry"), "next_phase_entry").get("allowed"),
                "next_phase_entry.allowed",
            )
            ready_by_gate[gate_id] = next_allowed
        except GateError as exc:
            print(f"phase review gate check failed for {rel(path)}: {exc}", file=sys.stderr)
            any_errors = True
            continue
        print(summary)
        if errors:
            any_errors = True
            print(f"phase review gate check failed for {rel(path)}: {len(errors)} issue(s)")
            for error in errors[:80]:
                print(f"  - {error}")
            if len(errors) > 80:
                print(f"  ... {len(errors) - 80} more")

    for gate_id in sorted(required_ready):
        if gate_id not in ready_by_gate:
            print(f"{gate_id} is not ready: gate not found")
            any_errors = True
        elif not ready_by_gate[gate_id]:
            print(f"{gate_id} is not ready: owner manual decision has not opened next phase")
            any_errors = True

    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
