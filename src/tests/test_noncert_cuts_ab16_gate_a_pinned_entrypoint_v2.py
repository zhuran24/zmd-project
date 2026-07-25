from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
ENTRYPOINT_PATH = TOOLS / "gate_a_pinned_entrypoint_v2.py"

SPEC = importlib.util.spec_from_file_location(
    "noncert_cuts_ab16_gate_a_pinned_entrypoint_v2_tested",
    ENTRYPOINT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
ENTRYPOINT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENTRYPOINT
SPEC.loader.exec_module(ENTRYPOINT)


def _identity(path: Path) -> dict[str, object]:
    metadata = path.stat()
    raw = path.read_bytes()
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def test_ordinary_path_execution_is_rejected() -> None:
    with pytest.raises(
        ENTRYPOINT.PinnedEntrypointError,
        match="ordinary path execution is forbidden",
    ):
        ENTRYPOINT._retained_entry_fd(str(ENTRYPOINT_PATH))


def test_retained_entry_accepts_real_planned_style_identity() -> None:
    descriptor = os.open(ENTRYPOINT_PATH, os.O_RDONLY)
    try:
        assert (
            ENTRYPOINT._snapshot_retained_entry(
                f"/proc/self/fd/{descriptor}",
                _identity(ENTRYPOINT_PATH),
            )
            == ENTRYPOINT_PATH.read_bytes()
        )
    finally:
        os.close(descriptor)


def test_retained_entry_rejects_path_swap(tmp_path: Path) -> None:
    source = tmp_path / "entry.py"
    source.write_bytes(b"original entry bytes\n")
    expected = _identity(source)
    descriptor = os.open(source, os.O_RDONLY)
    try:
        replacement = tmp_path / "replacement.py"
        replacement.write_bytes(b"different entry bytes\n")
        replacement.replace(source)
        with pytest.raises(
            ENTRYPOINT.PinnedEntrypointError,
            match="pinned entrypoint",
        ):
            ENTRYPOINT._snapshot_retained_entry(
                f"/proc/self/fd/{descriptor}",
                expected,
            )
    finally:
        os.close(descriptor)


def test_dependency_drift_is_rejected_before_compile(tmp_path: Path) -> None:
    dependency = tmp_path / "dependency.py"
    dependency.write_bytes(b"VALUE = 1\n")
    expected = _identity(dependency)
    dependency.write_bytes(b"VALUE = 2\n")
    with pytest.raises(
        ENTRYPOINT.PinnedEntrypointError,
        match="differs from planned byte identity",
    ):
        ENTRYPOINT._snapshot_expected_path(expected, label="dependency")


def test_observation_is_detached_and_canonical(tmp_path: Path) -> None:
    source = tmp_path / "tool.py"
    source.write_bytes(b"VALUE = 1\n")
    sources = {
        ENTRYPOINT.ENTRYPOINT_ROLE: _identity(source),
        **{role: _identity(source) for _module_name, role in ENTRYPOINT.MODULE_LOAD_ORDER},
    }
    digest = hashlib.sha256(_canonical(sources) + b"\n").hexdigest()
    raw = _canonical(
        {
            "planned_source_identities": sources,
            "planned_source_set_digest": digest,
        }
    )
    observation = tmp_path / "planned.json"
    observation.write_bytes(raw)
    snapshot = ENTRYPOINT._snapshot_detached_observation(
        observation,
        expected_size=len(raw),
        expected_sha256=hashlib.sha256(raw).hexdigest(),
    )
    assert (
        ENTRYPOINT._planned_sources(
            snapshot,
            expected_set_digest=digest,
        )
        == sources
    )

    observation.write_bytes(raw + b"\n")
    with pytest.raises(
        ENTRYPOINT.PinnedEntrypointError,
        match="detached identity drifted",
    ):
        ENTRYPOINT._snapshot_detached_observation(
            observation,
            expected_size=len(raw),
            expected_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_dispatch_surface_has_no_formal_or_organic_arm() -> None:
    calls: list[tuple[str, list[str]]] = []

    def target(name: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(main=lambda argv: calls.append((name, list(argv))) or 0)

    modules = {
        "disposable_drill_authority_v2": target("build"),
        "organic_unit_orchestrator_v2": target("orchestrator"),
        "gate_a_validation_v2": target("validation"),
    }
    assert ENTRYPOINT._dispatch("build-disposable", ["--x"], modules) == 0
    assert ENTRYPOINT._dispatch("drill", ["--y"], modules) == 0
    assert ENTRYPOINT._dispatch("record-preflight", ["--z"], modules) == 0
    assert ENTRYPOINT._dispatch("finalize", ["--q"], modules) == 0
    assert calls == [
        ("build", ["--x"]),
        ("orchestrator", ["drill", "--y"]),
        ("validation", ["record-preflight", "--z"]),
        ("validation", ["finalize", "--q"]),
    ]
    with pytest.raises(
        ENTRYPOINT.PinnedEntrypointError,
        match="not a Gate-A operation",
    ):
        ENTRYPOINT._dispatch("formal", [], modules)


def test_parser_forwards_target_options_without_reinterpreting_them() -> None:
    arguments = ENTRYPOINT._parse_arguments(
        [
            "--planned-source-observation",
            "/authority/planned.json",
            "--planned-source-observation-size",
            "42",
            "--planned-source-observation-sha256",
            "a" * 64,
            "--planned-source-set-digest",
            "b" * 64,
            "drill",
            "--pre-run",
            "/attempt/pre-run.json",
            "--selection",
            "/attempt/selection.json",
        ]
    )
    assert arguments.command == "drill"
    assert arguments.forwarded == [
        "--pre-run",
        "/attempt/pre-run.json",
        "--selection",
        "/attempt/selection.json",
    ]


def test_real_dependency_closure_preloads_from_planned_bytes_only() -> None:
    v4_tools = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
    sources = {ENTRYPOINT.ENTRYPOINT_ROLE: _identity(ENTRYPOINT_PATH)}
    for module_name, role in ENTRYPOINT.MODULE_LOAD_ORDER:
        root = v4_tools if module_name == "campaign_authority_v4" else TOOLS
        sources[role] = _identity(root / f"{module_name}.py")

    module_names = [name for name, _role in ENTRYPOINT.MODULE_LOAD_ORDER]
    previous = {name: sys.modules.pop(name) for name in module_names if name in sys.modules}
    loaded: dict[str, types.ModuleType] = {}
    blocker = None
    original_path: list[str] | None = None
    try:
        loaded, blocker, original_path = ENTRYPOINT._preload_modules(sources)
        assert list(loaded) == module_names
        assert loaded["disposable_drill_authority_v2"].bootstrap is loaded["ab16_campaign_bootstrap_v2"]
        assert loaded["gate_a_validation_v2"].drill_authority is loaded["disposable_drill_authority_v2"]
    finally:
        for name in reversed(module_names):
            sys.modules.pop(name, None)
        if blocker is not None and blocker in sys.meta_path:
            sys.meta_path.remove(blocker)
        if original_path is not None:
            sys.path[:] = original_path
        sys.modules.update(previous)


def test_entrypoint_source_is_regular_and_not_symlinked() -> None:
    metadata = ENTRYPOINT_PATH.lstat()
    assert stat.S_ISREG(metadata.st_mode)
    assert not ENTRYPOINT_PATH.is_symlink()
