from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STATE_KEYS = {"final_result", "final_status", "terminal_frontier_evidence"}
STRONG_STATUS_STRINGS = {"CERTIFIED", "INFEASIBLE"}
STRONG_STATUS_NAMES = {"RUN_STATUS_CERTIFIED", "RUN_STATUS_INFEASIBLE"}
STATUS_NORMALIZER_NAMES = {"normalized_status"}
ARTIFACT_CALLEES = {
    "save_certified_final_solution_and_blueprint",
    "_save_final_result",
    "export_certified_blueprint",
    "export_certified_delivery_manifest",
    "write_blueprint_payload",
}
ARTIFACT_FILENAMES = {
    "final_solution.json",
    "optimal_blueprint.json",
    "certified_delivery_manifest.json",
}
VERIFIED_PRODUCER_CALLEE = "_mark_candidate_result_from_verified_producer"


@dataclass(frozen=True)
class Finding:
    module: str
    line: int
    pattern: str
    qualname: str
    key: str | None = None
    callee: str | None = None


@dataclass(frozen=True)
class AllowEntry:
    pattern: str
    module: str
    qualname: str
    source_sha256: str
    line: int | None
    keys: frozenset[str]
    callee: str | None

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "AllowEntry":
        return cls(
            pattern=str(raw["pattern"]),
            module=_normalize_module(str(raw["module"])),
            qualname=str(raw["qualname"]),
            source_sha256=str(raw["source_sha256"]),
            line=int(raw["line"]) if raw.get("line") is not None else None,
            keys=frozenset(str(key) for key in raw.get("keys", [])),
            callee=str(raw["callee"]) if raw.get("callee") is not None else None,
        )

    def matches(self, finding: Finding) -> bool:
        if self.pattern != finding.pattern:
            return False
        if self.module != finding.module:
            return False
        if self.qualname != finding.qualname:
            return False
        if self.line is not None and self.line != finding.line:
            return False
        if self.keys and finding.key not in self.keys:
            return False
        if self.callee is not None and self.callee != finding.callee:
            return False
        return True


class StrongStatusVisitor(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.findings: list[Finding] = []
        self._qualname_stack: list[str] = []
        self._function_stack: list[ast.AST] = []
        self._verified_alias_stack: list[set[str]] = []
        self._path_alias_stack: list[dict[str, tuple[str, ...]]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._qualname_stack.append(node.name)
        self.generic_visit(node)
        self._qualname_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._qualname_stack.append(node.name)
        self._function_stack.append(node)
        self._verified_alias_stack.append(set())
        self._path_alias_stack.append({})
        for stmt in node.body:
            self.visit(stmt)
        self._path_alias_stack.pop()
        self._verified_alias_stack.pop()
        self._function_stack.pop()
        self._qualname_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> Any:
        self._record_verified_aliases(node.targets, node.value)
        self._record_path_aliases(node.targets, node.value)
        for target in node.targets:
            self._check_assignment_target(target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if node.value is not None:
            self._record_verified_aliases([node.target], node.value)
            self._record_path_aliases([node.target], node.value)
            self._check_assignment_target(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:
        self._check_assignment_target(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        callee = _call_name(node.func)
        if _is_verified_producer_getattr_call(node):
            self._add(node, "verified_producer_reference", callee="getattr")
        elif _is_verified_producer_dict_lookup_call(node):
            self._add(node, "verified_producer_reference", callee="dict_get")
        elif isinstance(node.func, ast.Name) and self._is_verified_alias(node.func.id):
            self._add(node, "verified_producer_reference", callee=node.func.id)

        if isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            self._check_update_call(node)
        elif callee == "dict":
            self._check_dict_constructor(node)
        elif callee == "setattr":
            self._check_setattr_call(node)

        if callee == "mark_campaign_stopped":
            status_arg = _call_status_arg(node, positional_index=1)
            if status_arg is not None and not _is_none_literal(status_arg):
                self._add(node, "mark_campaign_stopped", callee=callee)
        elif callee in ARTIFACT_CALLEES:
            self._add(node, "artifact_write", callee=callee)
        elif callee == "atomic_write_json":
            artifact_filename = self._artifact_filename_from_atomic_write(node)
            if artifact_filename is not None:
                self._add(node, "artifact_write", key=artifact_filename, callee=callee)
        elif callee == "_build_certified_result":
            self._add(node, "build_certified_result", callee=callee)
        elif callee == "mark_candidate_result":
            status_arg = _call_status_arg(node, positional_index=2)
            if status_arg is not None and _is_strong_status_value(status_arg):
                self._add(node, "candidate_status", callee=callee)
        elif callee == "HeuristicFinderResult":
            status_arg = _keyword_arg(node, "status")
            if status_arg is not None and _is_strong_status_value(status_arg):
                self._add(node, "heuristic_status", callee=callee)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if isinstance(node.ctx, ast.Load) and node.attr == VERIFIED_PRODUCER_CALLEE:
            self._add(node, "verified_producer_reference", callee=VERIFIED_PRODUCER_CALLEE)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load) and node.id == VERIFIED_PRODUCER_CALLEE:
            self._add(node, "verified_producer_reference", callee=VERIFIED_PRODUCER_CALLEE)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if (
            isinstance(node.ctx, ast.Load)
            and _constant_string(node.slice) == VERIFIED_PRODUCER_CALLEE
            and _is_dict_attribute_expr(node.value)
        ):
            self._add(node, "verified_producer_reference", callee="dict_subscript")
        self.generic_visit(node)

    def _record_verified_aliases(self, targets: list[ast.expr], value: ast.AST) -> None:
        if not self._verified_alias_stack:
            return
        if not _contains_verified_producer_reference(value):
            return
        for target in targets:
            if isinstance(target, ast.Name):
                self._verified_alias_stack[-1].add(target.id)

    def _is_verified_alias(self, name: str) -> bool:
        return bool(self._verified_alias_stack and name in self._verified_alias_stack[-1])

    def _record_path_aliases(self, targets: list[ast.expr], value: ast.AST) -> None:
        if not self._path_alias_stack:
            return
        aliases = self._path_alias_stack[-1]
        suffix = self._path_suffix(value)
        for target in targets:
            if isinstance(target, ast.Name):
                if suffix is None:
                    aliases.pop(target.id, None)
                else:
                    aliases[target.id] = suffix

    def _check_assignment_target(self, target: ast.expr, value: ast.AST, line: int) -> None:
        key = _string_subscript_key(target)
        if key is None:
            if _is_state_like_subscript_target(target):
                self._add_at(line, "state_key_write_dynamic")
            return
        if key in STATE_KEYS and self._is_state_key_write_value(value):
            self._add_at(line, "state_key_write", key=key)
        if key == "status" and _is_candidate_status_write_value(value):
            self._add_at(line, "candidate_status", key=key)

    def _is_state_key_write_value(self, value: ast.AST) -> bool:
        return not _is_none_literal(value)

    def _check_update_call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute):
            return
        target = node.func.value
        state_like = _is_state_like_expr(target)
        record_like = _is_record_like_expr(target)
        if not state_like and not record_like:
            return

        for arg in node.args:
            self._check_update_payload(
                arg,
                node.lineno,
                state_like=state_like,
                record_like=record_like,
            )
        for keyword in node.keywords:
            if keyword.arg is None:
                self._add_dynamic_update(
                    node.lineno,
                    state_like=state_like,
                    record_like=record_like,
                )
                continue
            self._check_key_value(
                keyword.arg,
                keyword.value,
                node.lineno,
                state_like=state_like,
                record_like=record_like,
                dynamic_pattern=False,
            )

    def _check_update_payload(
        self,
        payload: ast.AST,
        line: int,
        *,
        state_like: bool,
        record_like: bool,
    ) -> None:
        if isinstance(payload, ast.Dict):
            for key_node, value_node in zip(payload.keys, payload.values):
                if key_node is None:
                    self._add_dynamic_update(
                        line,
                        state_like=state_like,
                        record_like=record_like,
                    )
                    continue
                key = _constant_string(key_node)
                if key is None:
                    self._add_dynamic_update(
                        line,
                        state_like=state_like,
                        record_like=record_like,
                    )
                    continue
                self._check_key_value(
                    key,
                    value_node,
                    line,
                    state_like=state_like,
                    record_like=record_like,
                    dynamic_pattern=False,
                )
            return

        if isinstance(payload, ast.Call) and _call_name(payload.func) == "dict":
            saw_static_key = False
            for keyword in payload.keywords:
                if keyword.arg is None:
                    self._add_dynamic_update(
                        line,
                        state_like=state_like,
                        record_like=record_like,
                    )
                    continue
                saw_static_key = True
                self._check_key_value(
                    keyword.arg,
                    keyword.value,
                    line,
                    state_like=state_like,
                    record_like=record_like,
                    dynamic_pattern=False,
                )
            if payload.args:
                if len(payload.args) == 1 and isinstance(payload.args[0], ast.Dict):
                    self._check_update_payload(
                        payload.args[0],
                        line,
                        state_like=state_like,
                        record_like=record_like,
                    )
                else:
                    self._add_dynamic_update(
                        line,
                        state_like=state_like,
                        record_like=record_like,
                    )
            elif not saw_static_key:
                self._add_dynamic_update(
                    line,
                    state_like=state_like,
                    record_like=record_like,
                )
            return

        self._add_dynamic_update(line, state_like=state_like, record_like=record_like)

    def _check_key_value(
        self,
        key: str,
        value: ast.AST,
        line: int,
        *,
        state_like: bool,
        record_like: bool,
        dynamic_pattern: bool,
    ) -> None:
        if state_like and key in STATE_KEYS:
            pattern = "state_key_write_dynamic" if dynamic_pattern else "state_key_write"
            if dynamic_pattern or self._is_state_key_write_value(value):
                self._add_at(line, pattern, key=key)
        if record_like and key == "status" and (
            dynamic_pattern or _is_candidate_status_write_value(value)
        ):
            pattern = "candidate_status_update_dynamic" if dynamic_pattern else "candidate_status"
            self._add_at(line, pattern, key=key)

    def _add_dynamic_update(self, line: int, *, state_like: bool, record_like: bool) -> None:
        if state_like:
            self._add_at(line, "state_key_write_dynamic")
        if record_like:
            self._add_at(line, "candidate_status_update_dynamic", key="status")

    def _check_dict_constructor(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            if keyword.arg in STATE_KEYS and self._is_state_key_write_value(keyword.value):
                self._add_at(node.lineno, "state_key_write", key=keyword.arg)
            if keyword.arg == "status" and _is_candidate_status_write_value(keyword.value):
                self._add_at(node.lineno, "candidate_status", key="status")

    def _check_setattr_call(self, node: ast.Call) -> None:
        if len(node.args) < 3:
            return
        key = _constant_string(node.args[1])
        if key is None:
            return
        value = node.args[2]
        if key in STATE_KEYS and self._is_state_key_write_value(value):
            self._add_at(node.lineno, "state_key_write", key=key)
        if key == "status" and _is_candidate_status_write_value(value):
            self._add_at(node.lineno, "candidate_status", key=key)

    def _artifact_filename_from_atomic_write(self, node: ast.Call) -> str | None:
        if not node.args:
            return None
        suffix = self._path_suffix(node.args[0])
        if suffix is None:
            return None
        for part in reversed(suffix):
            if part in ARTIFACT_FILENAMES:
                return part
        return None

    def _path_suffix(self, node: ast.AST) -> tuple[str, ...] | None:
        if isinstance(node, ast.Name) and self._path_alias_stack:
            return self._path_alias_stack[-1].get(node.id)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _path_segments(node.value)
        if isinstance(node, ast.Call) and _call_name(node.func) == "Path" and node.args:
            return self._path_suffix(node.args[0])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = self._path_suffix(node.left)
            right = self._path_suffix(node.right)
            if left is not None and right is not None:
                return left + right
            return right if right is not None else left
        return None

    def _add(
        self,
        node: ast.AST,
        pattern: str,
        *,
        key: str | None = None,
        callee: str | None = None,
    ) -> None:
        self._add_at(
            int(getattr(node, "lineno", 0)),
            pattern,
            key=key,
            callee=callee,
        )

    def _add_at(
        self,
        line: int,
        pattern: str,
        *,
        key: str | None = None,
        callee: str | None = None,
    ) -> None:
        self.findings.append(
            Finding(
                module=self.module,
                line=line,
                pattern=pattern,
                qualname=self._qualname(),
                key=key,
                callee=callee,
            )
        )

    def _qualname(self) -> str:
        return ".".join(self._qualname_stack) if self._qualname_stack else "<module>"


def _call_status_arg(node: ast.Call, *, positional_index: int) -> ast.AST | None:
    keyword = _keyword_arg(node, "status")
    if keyword is not None:
        return keyword
    if len(node.args) > positional_index:
        return node.args[positional_index]
    return None


def _keyword_arg(node: ast.Call, name: str) -> ast.AST | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_candidate_status_write_value(value: ast.AST) -> bool:
    if _is_strong_status_value(value):
        return True
    return isinstance(value, ast.Name) and value.id in STATUS_NORMALIZER_NAMES


def _is_strong_status_value(value: ast.AST) -> bool:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value in STRONG_STATUS_STRINGS
    if isinstance(value, ast.Name):
        return value.id in STRONG_STATUS_NAMES
    return False


def _is_none_literal(value: ast.AST) -> bool:
    return isinstance(value, ast.Constant) and value.value is None


def _string_subscript_key(target: ast.expr) -> str | None:
    if not isinstance(target, ast.Subscript):
        return None
    return _constant_string(target.slice)


def _contains_verified_producer_reference(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if _is_verified_producer_attribute(child):
            return True
        if _is_verified_producer_name(child):
            return True
        if isinstance(child, ast.Call) and (
            _is_verified_producer_getattr_call(child)
            or _is_verified_producer_dict_lookup_call(child)
        ):
            return True
    return False


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_verified_producer_attribute(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and node.attr == VERIFIED_PRODUCER_CALLEE
    )


def _is_verified_producer_name(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == VERIFIED_PRODUCER_CALLEE
    )


def _is_verified_producer_getattr_call(node: ast.Call) -> bool:
    return (
        _call_name(node.func) == "getattr"
        and len(node.args) >= 2
        and _constant_string(node.args[1]) == VERIFIED_PRODUCER_CALLEE
    )


def _is_verified_producer_dict_lookup_call(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _is_dict_attribute_expr(node.func.value)
        and bool(node.args)
        and _constant_string(node.args[0]) == VERIFIED_PRODUCER_CALLEE
    )


def _is_dict_attribute_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "__dict__"


def _is_state_like_subscript_target(target: ast.expr) -> bool:
    return isinstance(target, ast.Subscript) and _is_state_like_expr(target.value)


def _is_state_like_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"state", "campaign_state"}
    if isinstance(node, ast.Attribute):
        return node.attr == "state"
    return False


def _is_record_like_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"record", "candidate_record"}
    return False


def _path_segments(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.replace("\\", "/").split("/") if part not in {"", "."})


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _normalize_module(path: str) -> str:
    return path.replace("\\", "/")


def _module_for_path(path: Path, root: Path) -> str:
    return _normalize_module(path.resolve().relative_to(root.resolve()).as_posix())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_allowlist(path: Path) -> list[AllowEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("allowlist")
    if not isinstance(entries, list):
        raise ValueError("allowlist JSON must contain an 'allowlist' array")
    return [AllowEntry.from_json(entry) for entry in entries]


def _python_files(root: Path) -> list[Path]:
    src_root = root / "src"
    if not src_root.exists():
        return []
    files: list[Path] = []
    for path in src_root.rglob("*.py"):
        rel = path.resolve().relative_to(root.resolve())
        parts = rel.parts
        if len(parts) >= 2 and parts[0] == "src" and parts[1] == "tests":
            continue
        files.append(path)
    return sorted(files)


def _scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _python_files(root):
        module = _module_for_path(path, root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = StrongStatusVisitor(module)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return findings


def _pin_failures(root: Path, entries: list[AllowEntry]) -> list[str]:
    failures: list[str] = []
    checked: set[tuple[str, str]] = set()
    for entry in entries:
        # Each allowlist entry pins the whole module file, not only the AST node.
        # This is intentional: moving or editing a registered proof sink should
        # force review even when the node shape still matches.
        key = (entry.module, entry.source_sha256)
        if key in checked:
            continue
        checked.add(key)
        path = root / Path(entry.module)
        if not path.exists():
            failures.append(
                _format_failure(
                    entry.module,
                    "-",
                    "source_sha256",
                    entry.qualname,
                    "allowlist source file missing",
                )
            )
            continue
        actual = _sha256(path)
        if actual != entry.source_sha256:
            failures.append(
                _format_failure(
                    entry.module,
                    "-",
                    "source_sha256",
                    entry.qualname,
                    f"allowlist source_sha256 mismatch: expected {entry.source_sha256} actual {actual}",
                )
            )
    return failures


def _unregistered_failures(
    findings: list[Finding],
    entries: list[AllowEntry],
) -> list[str]:
    failures: list[str] = []
    for finding in findings:
        if any(entry.matches(finding) for entry in entries):
            continue
        failures.append(
            _format_failure(
                finding.module,
                str(finding.line),
                finding.pattern,
                finding.qualname,
                "unregistered strong-status write",
            )
        )
    return failures


def _format_failure(
    module: str,
    line: str,
    pattern: str,
    qualname: str,
    message: str,
) -> str:
    return f'({module},{line},{pattern},{qualname},"{message}")'


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check P1.2 strong-status write sites against the AST allowlist."
    )
    parser.add_argument("--root", type=Path, default=_default_root())
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Defaults to data/proof_obligations/strong_status_write_allowlist.json under --root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or []))
    root = args.root.resolve()
    allowlist_path = (
        args.allowlist
        if args.allowlist is not None
        else root / "data" / "proof_obligations" / "strong_status_write_allowlist.json"
    )
    try:
        entries = _load_allowlist(allowlist_path)
        findings = _scan(root)
    except Exception as exc:  # noqa: BLE001
        print(f"strong-status write allowlist check error: {type(exc).__name__}: {exc}")
        return 1

    failures = _pin_failures(root, entries)
    failures.extend(_unregistered_failures(findings, entries))
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print(
        "strong-status write allowlist check passed: "
        f"{len(findings)} registered AST node(s), {len(entries)} allowlist entry(ies)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
