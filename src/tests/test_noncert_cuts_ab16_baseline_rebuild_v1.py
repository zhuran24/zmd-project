from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724"
TOOL_PATH = TOOL_DIR / "baseline_rebuild_v1.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(TOOL_DIR))
    try:
        spec = importlib.util.spec_from_file_location("cuts_ab16_baseline_rebuild_v1", TOOL_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(TOOL_DIR))


REBUILD = _load()


def _provenance_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    raw: bytes | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    output = tmp_path / "baseline"
    output.mkdir(mode=0o700)
    record: dict[str, object] = {
        "import_mode": "ordinary_pathfinder",
        "materialization_receipt_identity": {
            "path": str(tmp_path / "materialization.json"),
            "sha256": "1" * 64,
            "size_bytes": 1,
        },
        "package_id": "2" * 64,
        "repository_head": "3" * 40,
        "schema_version": "noncert-cuts-ab16-campaign-snapshot-provenance-v1",
        "snapshot_manifest_identity": {
            "path": str(tmp_path / "manifest.json"),
            "sha256": "4" * 64,
            "size_bytes": 1,
        },
        "snapshot_root": str(tmp_path),
    }
    provenance = output / REBUILD.CAMPAIGN_PROVENANCE_NAME
    provenance.write_bytes(raw if raw is not None else REBUILD.baseline_contract.canonical_json(record))
    provenance.chmod(0o444)

    def replay(path: Path) -> dict[str, object]:
        assert path == provenance
        return dict(record)

    monkeypatch.setattr(REBUILD, "_campaign_provenance", replay)
    return output, provenance, record


def test_accepts_exact_provenance_only_state_and_retains_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, provenance, record = _provenance_only(tmp_path, monkeypatch)
    state = REBUILD._open_provenance_only_output(output, provenance)
    try:
        assert state.root == output
        assert state.provenance == record
        assert state.provenance_identity == {
            "path": str(provenance),
            "sha256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
            "size_bytes": provenance.stat().st_size,
        }
        REBUILD._verify_provenance_member(state)
    finally:
        state.close()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("extra", "PROVENANCE_ONLY"),
        ("mode", "mode0444"),
        ("hardlink", "nlink1"),
        ("directory", "regular"),
    ],
)
def test_rejects_non_provenance_only_member_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    output, provenance, _ = _provenance_only(tmp_path, monkeypatch)
    if mutation == "extra":
        (output / "unexpected").write_text("no\n", encoding="utf-8")
    elif mutation == "mode":
        provenance.chmod(0o644)
    elif mutation == "hardlink":
        os.link(provenance, tmp_path / "second-link")
    else:
        provenance.unlink()
        provenance.mkdir()
    with pytest.raises(REBUILD.BaselineRebuildError, match=message):
        REBUILD._open_provenance_only_output(output, provenance)


def test_rejects_symlink_output_and_symlink_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target, provenance, _ = _provenance_only(tmp_path, monkeypatch)
    alias = tmp_path / "baseline-alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(REBUILD.BaselineRebuildError, match="symlink"):
        REBUILD._open_provenance_only_output(alias, alias / provenance.name)

    provenance.unlink()
    external = tmp_path / "external.json"
    external.write_bytes(REBUILD.baseline_contract.canonical_json({"external": True}))
    external.chmod(0o444)
    provenance.symlink_to(external)
    with pytest.raises(REBUILD.BaselineRebuildError, match="regular nlink1"):
        REBUILD._open_provenance_only_output(target, provenance)


def test_rejects_absent_output_and_noncanonical_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    absent = tmp_path / "absent"
    with pytest.raises(REBUILD.BaselineRebuildError, match="missing"):
        REBUILD._open_provenance_only_output(
            absent,
            absent / REBUILD.CAMPAIGN_PROVENANCE_NAME,
        )

    output, provenance, record = _provenance_only(
        tmp_path,
        monkeypatch,
        raw=(json.dumps({"not": "the canonical record"}, indent=2) + "\n").encode(),
    )
    assert REBUILD.baseline_contract.canonical_json(record) != provenance.read_bytes()
    with pytest.raises(REBUILD.BaselineRebuildError, match="not canonical"):
        REBUILD._open_provenance_only_output(output, provenance)


def test_rejects_noncanonical_provenance_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _, _ = _provenance_only(tmp_path, monkeypatch)
    external = tmp_path / "campaign-provenance.json"
    external.write_text("{}\n", encoding="utf-8")
    external.chmod(0o444)
    with pytest.raises(REBUILD.BaselineRebuildError, match="canonical baseline child"):
        REBUILD._open_provenance_only_output(output, external)


def test_same_fd_read_fails_closed_on_member_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, provenance, _ = _provenance_only(tmp_path, monkeypatch)
    original_pread = os.pread
    changed = False

    def mutate_after_read(descriptor: int, length: int, offset: int) -> bytes:
        nonlocal changed
        chunk = original_pread(descriptor, length, offset)
        if not changed and chunk:
            changed = True
            provenance.chmod(0o644)
            provenance.write_bytes(provenance.read_bytes() + b" ")
            provenance.chmod(0o444)
        return chunk

    monkeypatch.setattr(REBUILD.os, "pread", mutate_after_read)
    with pytest.raises(REBUILD.BaselineRebuildError, match="grew|changed"):
        REBUILD._open_provenance_only_output(output, provenance)


def test_retained_fds_reject_member_and_directory_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, provenance, _ = _provenance_only(tmp_path, monkeypatch)
    state = REBUILD._open_provenance_only_output(output, provenance)
    try:
        raw = provenance.read_bytes()
        provenance.chmod(0o644)
        provenance.unlink()
        provenance.write_bytes(raw)
        provenance.chmod(0o444)
        with pytest.raises(REBUILD.BaselineRebuildError, match="member identity drifted"):
            REBUILD._verify_provenance_member(state)
    finally:
        state.close()

    other = tmp_path / "second"
    other.mkdir()
    output, provenance, _ = _provenance_only(other, monkeypatch)
    state = REBUILD._open_provenance_only_output(output, provenance)
    moved = other / "retained"
    try:
        output.rename(moved)
        output.mkdir()
        with pytest.raises(REBUILD.BaselineRebuildError, match="path binding drifted"):
            REBUILD._verify_provenance_member(state)
    finally:
        state.close()


def test_exclusive_file_and_directory_publication_never_overwrites(tmp_path: Path) -> None:
    parent = tmp_path / "owned"
    parent.mkdir()
    output = parent / "receipt.json"
    identity = REBUILD._write_exclusive(output, b"first\n")
    metadata = output.stat()
    assert output.read_bytes() == b"first\n"
    assert stat.S_IMODE(metadata.st_mode) == 0o600
    assert metadata.st_nlink == 1
    assert identity["path"] == str(output)
    with pytest.raises(REBUILD.BaselineRebuildError, match="exclusive output creation failed"):
        REBUILD._write_exclusive(output, b"second\n")
    assert output.read_bytes() == b"first\n"

    staging = REBUILD._mkdir_exclusive(parent / "staging")
    assert staging.is_dir()
    assert stat.S_IMODE(staging.stat().st_mode) == 0o700
    with pytest.raises(REBUILD.BaselineRebuildError, match="exclusive directory creation failed"):
        REBUILD._mkdir_exclusive(staging)


def test_main_rejects_invalid_prestate_before_any_rebuild(tmp_path: Path) -> None:
    output = tmp_path / "absent"
    provenance = output / REBUILD.CAMPAIGN_PROVENANCE_NAME
    argv = [
        "--output-dir",
        str(output),
        "--run-nonce",
        "fixture",
        "--campaign-provenance",
        str(provenance),
        "--candidate-placements",
        str(tmp_path / "candidate.json"),
        "--canonical-rules",
        str(tmp_path / "rules.json"),
        "--mandatory-instances",
        str(tmp_path / "mandatory.json"),
    ]
    with pytest.raises(REBUILD.BaselineRebuildError, match="missing"):
        REBUILD.main(argv)
    assert not output.exists()
