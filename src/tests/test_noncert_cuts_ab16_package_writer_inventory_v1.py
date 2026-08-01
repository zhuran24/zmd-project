"""Zero-authority checks for the closed prospective AB16 writer inventory."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_authority_v1 as budget,
)
from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
    AB16BudgetedCutLedgerWriter,
    AB16BudgetedCutManager,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_package_writer_inventory_v1 as inventory,
)
from src.cuts import ledger as ledger_module
from src.cuts.ledger import CutLedgerWriter
from src.models.cut_manager import CutManager


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
WRITE_FLAG_NAMES = frozenset(
    {"O_APPEND", "O_CREAT", "O_RDWR", "O_TRUNC", "O_WRONLY"}
)
DIRECT_MUTATION_ATTRIBUTES = frozenset(
    {
        "chmod",
        "fchmod",
        "ftruncate",
        "link",
        "makedirs",
        "mkdir",
        "posix_fallocate",
        "pwrite",
        "rmdir",
        "symlink",
        "touch",
        "unlink",
    }
)
NATIVE_DIRECT_MUTATION_SYMBOLS = frozenset({"renameat2"})


def _tokens(node: ast.AST) -> set[str]:
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name)
    } | {
        item.attr
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
    }


class _DirectMutationScanner(ast.NodeVisitor):
    """Conservative direct-mutation scan; runtime enforcement remains primary."""

    def __init__(self) -> None:
        self._scope: list[str] = []
        self._functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.observed: set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self._scope.append(node.name)
        self._functions.append(node)
        self.generic_visit(node)
        self._functions.pop()
        self._scope.pop()

    def _named_flags_are_writable(self, name: str) -> bool:
        if not self._functions:
            return False
        for node in ast.walk(self._functions[-1]):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if (
                value is not None
                and any(
                    isinstance(target, ast.Name) and target.id == name
                    for target in targets
                )
                and _tokens(value) & WRITE_FLAG_NAMES
            ):
                return True
        return False

    def _named_native_mutator(self, name: str) -> bool:
        if not self._functions:
            return False
        for node in ast.walk(self._functions[-1]):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            value = node.value
            if (
                value is not None
                and any(
                    isinstance(target, ast.Name) and target.id == name
                    for target in targets
                )
                and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "getattr"
                and len(value.args) >= 2
                and isinstance(value.args[1], ast.Constant)
                and value.args[1].value
                in NATIVE_DIRECT_MUTATION_SYMBOLS
            ):
                return True
            if (
                value is not None
                and any(
                    isinstance(target, ast.Name) and target.id == name
                    for target in targets
                )
                and isinstance(value, ast.Attribute)
                and value.attr in NATIVE_DIRECT_MUTATION_SYMBOLS
            ):
                return True
        return False

    @staticmethod
    def _mode_is_writable(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(character in node.value for character in "awx+")
        )

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        attribute = (
            function.attr
            if isinstance(function, ast.Attribute)
            else function.id
            if isinstance(function, ast.Name)
            else ""
        )
        mutates = attribute in DIRECT_MUTATION_ATTRIBUTES
        if (
            isinstance(function, ast.Name)
            and self._named_native_mutator(function.id)
        ):
            mutates = True
        if (
            attribute in {"rename", "replace"}
            and isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "os"
        ):
            mutates = True
        if attribute == "open":
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "os"
                and len(node.args) >= 2
            ):
                flags = node.args[1]
                mutates = bool(_tokens(flags) & WRITE_FLAG_NAMES)
                if isinstance(flags, ast.Name):
                    mutates = mutates or self._named_flags_are_writable(flags.id)
            elif any(self._mode_is_writable(argument) for argument in node.args[:2]):
                mutates = True
            elif any(
                keyword.arg == "mode" and self._mode_is_writable(keyword.value)
                for keyword in node.keywords
            ):
                mutates = True
        if mutates:
            self.observed.add(".".join(self._scope) or "<module>")
        self.generic_visit(node)


def _scan(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scanner = _DirectMutationScanner()
    scanner.visit(tree)
    symbols: set[str] = set()

    class SymbolCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.scope.append(node.name)
            symbols.add(".".join(self.scope))
            self.generic_visit(node)
            self.scope.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(cast(ast.FunctionDef, node))

    SymbolCollector().visit(tree)
    return scanner.observed, symbols


def test_inventory_is_closed_research_only_and_covers_every_required_route() -> None:
    assert inventory.PACKAGE_WRITER_INVENTORY_SCHEMA == (
        "noncert-cuts-ab16-package-writer-inventory-v1"
    )
    assert inventory.AUTHORITY_SCOPE == "AB16_RESEARCH_ONLY"
    assert inventory.FALSE_AUTHORITY
    assert all(value is False for value in inventory.FALSE_AUTHORITY.values())
    assert {
        "ab16_formal_launch_authority_v1.py",
        "package_independent_verifier_v1.py",
    } <= set(inventory.PROSPECTIVE_EXECUTION_TOOL_FILES)
    assert tuple(inventory.WRITER_ROUTES) == (
        "append-channels",
        "detached-replay",
        "fixed-artifacts",
        "model-export",
        "scratch-tmpdir",
        "terminal-cleanup",
    )
    assert (
        "ab16_final_release_actor_v1._FinalReleaseServer._publish_replay_receipt"
        in inventory.WRITER_ROUTES["detached-replay"]["entrypoints"]
    )
    for route in inventory.WRITER_ROUTES.values():
        assert set(route) == {"authority", "entrypoints", "path_contract"}
        assert route["authority"]
        assert route["entrypoints"]
        assert route["path_contract"]


def test_every_prospective_direct_mutation_scope_is_registered() -> None:
    scanned_paths = {
        (RESEARCH / filename).relative_to(ROOT).as_posix()
        for filename in inventory.PROSPECTIVE_EXECUTION_TOOL_FILES
    } | set(inventory.PROSPECTIVE_EXTERNAL_EXECUTION_TOOL_FILES) | set(
        inventory.CORE_WRITER_FILES
    )
    assert set(inventory.DIRECT_MUTATION_SCOPES) <= scanned_paths
    for relative in sorted(scanned_paths):
        path = ROOT / relative
        assert path.is_file(), relative
        observed, symbols = _scan(path)
        registered = set(inventory.DIRECT_MUTATION_SCOPES.get(relative, ()))
        assert observed <= registered, (
            relative,
            sorted(observed - registered),
        )
        assert registered <= symbols, (
            relative,
            sorted(registered - symbols),
        )


def test_direct_mutation_scanner_rejects_a_new_unregistered_writer() -> None:
    tree = ast.parse(
        """
import os
def surprise(path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    return os.open(path, flags, 0o600)
"""
    )
    scanner = _DirectMutationScanner()
    scanner.visit(tree)
    assert scanner.observed == {"surprise"}
    assert "surprise" not in {
        scope
        for scopes in inventory.DIRECT_MUTATION_SCOPES.values()
        for scope in scopes
    }


def test_guardian_native_retirement_and_restore_are_explicit_mutation_scopes() -> None:
    relative = (
        "docs/research/noncert_cuts_ab16_20260724/"
        "ab16_outer_guardian_v1.py"
    )
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    observed, _symbols = _scan(path)
    registered = set(inventory.DIRECT_MUTATION_SCOPES[relative])
    assert "_rename_noreplace_at" in observed
    assert {
        "_rename_noreplace_at",
        "_restore_unverified_retirement",
        "_retire_bound_socket_at",
    } <= registered

    calls_by_function: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls_by_function[node.name] = {
            child.func.id
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
        }
    assert "_rename_noreplace_at" in calls_by_function[
        "_restore_unverified_retirement"
    ]
    assert "_rename_noreplace_at" in calls_by_function[
        "_retire_bound_socket_at"
    ]


def test_package_runtime_roles_are_inside_the_closed_execution_set() -> None:
    source = (RESEARCH / "ab16_campaign_bootstrap_v2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    runtime_paths: dict[str, str] | None = None
    script_tools: dict[str, str] | None = None
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        target_names = {
            target.id
            for target in targets
            if isinstance(target, ast.Name)
        }
        if "PACKAGE_BUDGET_RUNTIME_ROLE_PATHS" in target_names:
            assert statement.value is not None
            runtime_paths = ast.literal_eval(statement.value)
        if "AB16_SCRIPT_TOOL_FILES" in target_names:
            assert statement.value is not None
            script_tools = ast.literal_eval(statement.value)
    assert runtime_paths is not None and script_tools is not None
    runtime_files = {
        Path(package_path).name.removeprefix("tool.")
        for package_path in runtime_paths.values()
    }
    inventoried_runtime_files = set(inventory.PROSPECTIVE_EXECUTION_TOOL_FILES) | {
        Path(path).name
        for path in inventory.PROSPECTIVE_EXTERNAL_EXECUTION_TOOL_FILES
    }
    assert runtime_files <= inventoried_runtime_files
    assert script_tools["ab16_package_writer_inventory_v1"] == (
        "ab16_package_writer_inventory_v1.py"
    )
    assert script_tools["ab16_formal_launch_authority_v1"] == (
        "ab16_formal_launch_authority_v1.py"
    )
    assert script_tools["package_independent_verifier_v1"] == (
        "package_independent_verifier_v1.py"
    )
    assert "ab16_package_writer_inventory_v1.py" not in runtime_files
    assert 'module.__dict__.pop("build_shared_object", None)' in source
    assert inventory.DISARMED_PACKAGE_WRITER_SCOPES == frozenset(
        {"ab16_native_budget_helper_v1.build_shared_object"}
    )


def test_model_tmpdir_and_terminal_routes_bind_the_enforced_primitives() -> None:
    broker_source = (RESEARCH / "ab16_budget_broker_v1.py").read_text(encoding="utf-8")
    runner_source = (RESEARCH / "organic_arm_runner_v1.py").read_text(encoding="utf-8")
    baseline_source = (RESEARCH / "baseline_rebuild_v1.py").read_text(encoding="utf-8")
    closure_source = (RESEARCH / "ab16_closure_actor_v1.py").read_text(encoding="utf-8")
    for source in (broker_source, runner_source):
        assert "export_model_to_sealed_memfd" in source
        assert "install_final_seals" in source
        assert "has_writable_mapping" in source
        assert "_publish_descriptor" in source
    assert '("tmp", 0o500)' in runner_source
    assert 'os.environ["TMPDIR"]' in runner_source
    assert "install_worker_confinement" in baseline_source
    assert 'os.environ["TMPDIR"]' in baseline_source
    assert "publish_preallocated_extent" in closure_source
    assert "FORMAL_MANIFEST_SCHEMA" in closure_source
    assert "writable_root_descriptors" in closure_source


def test_real_budget_broker_drives_core_append_writers_without_local_files(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "formal-root"
    legacy_ledger_root = tmp_path / "must-remain-absent-ledger"
    legacy_cut_root = tmp_path / "must-remain-absent-cuts"
    broker = budget.FormalBudgetBroker.create(
        artifact_root,
        category_limits={"ledger": 32 * 1024},
        owner_nonce="writer-inventory-test",
    )
    try:
        ledger = AB16BudgetedCutLedgerWriter(
            legacy_ledger_root,
            scope_id="scope",
            writer_id="writer",
            immutable_budget=broker,
            budget_channel="ledger-events",
            budget_segment_max_bytes=4096,
        )
        ledger.append("GENERATED", {"cut_id": "one"})
        ledger.seal()
        manager = AB16BudgetedCutManager(
            checkpoint_dir=legacy_cut_root,
            immutable_budget=broker,
            budget_channel="runtime-cuts",
            budget_segment_max_bytes=4096,
        )
        assert manager.add_cut(
            [{"instance_id": "i", "pose_id": "p"}],
            "reason",
            "source",
        )
        assert not legacy_ledger_root.exists()
        assert not legacy_cut_root.exists()
        paths = [record["path"] for record in broker.published_artifacts()]
        assert paths == [
            "channels/ledger-events/segment-00000000.bin",
            "channels/ledger-events/segment-00000001.bin",
            "channels/ledger-events/segment-00000002.bin",
            "channels/runtime-cuts/segment-00000000.bin",
        ]
        assert len(ledger.immutable_segment_records) == 3
        assert len(manager.immutable_segment_records) == 1
        closure = broker.snapshot_root_closure()
        assert broker.verify_root_closure(closure) == closure
        entries = cast(list[dict[str, object]], closure["entries"])
        assert {
            entry["path"]
            for entry in entries
            if entry["type"] == "regular"
        } == set(paths)
        assert all(
            entry["mode_octal"] == "0444"
            for entry in entries
            if entry["type"] == "regular"
        )
    finally:
        broker.close()


def test_default_core_writers_keep_the_exact_legacy_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ledger_module.time, "time", lambda: 123.5)
    ledger_root = tmp_path / "legacy-ledger"
    writer = CutLedgerWriter(
        ledger_root,
        scope_id="scope",
        writer_id="writer",
    )
    writer.append("GENERATED", {"cut_id": "one"})
    writer.seal()
    ledger_raw = writer.path.read_bytes()
    assert hashlib.sha256(ledger_raw).hexdigest() == (
        "b9d5b3bb7b459027f3ac072fea8a0fa224dbcc5b8b42c9ad4e1c91fd8e389deb"
    )

    cut_root = tmp_path / "legacy-cuts"
    manager = CutManager(checkpoint_dir=cut_root)
    assert manager.add_cut(
        [{"instance_id": "i", "pose_id": "p"}],
        "reason",
        "source",
    )
    assert manager.cuts_file.read_bytes() == (
        b'{"source": "source", "reason": "reason", '
        b'"conflict_set": [{"instance_id": "i", "pose_id": "p"}]}\n'
    )
