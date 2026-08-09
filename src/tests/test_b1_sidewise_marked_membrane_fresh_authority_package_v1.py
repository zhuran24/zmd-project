from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"


def load_package() -> ModuleType:
    path = RESEARCH / "authority_package_v1.py"
    sys.path.insert(0, str(RESEARCH))
    spec = importlib.util.spec_from_file_location("_test_smm4_authority_package", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def package() -> ModuleType:
    return load_package()


def make_package(tmp_path: Path, authority_raw: bytes = b'{"status":"fixture"}\n') -> tuple[Path, str]:
    directory = tmp_path / "authority-a001"
    directory.mkdir()
    directory.chmod(0o755)
    authority = directory / "authority.json"
    authority.write_bytes(authority_raw)
    authority.chmod(0o644)
    seal_raw = f"{hashlib.sha256(authority_raw).hexdigest()}  authority.json\n".encode("ascii")
    seal = directory / "SHA256SUMS"
    seal.write_bytes(seal_raw)
    seal.chmod(0o644)
    return directory, hashlib.sha256(seal_raw).hexdigest()


def test_valid_package_returns_raw_full7_and_external_package_id(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, package_id = make_package(tmp_path)
    result = package.verify_authority_package(directory.resolve(), package_id)
    assert set(result) == {"authority_raw", "authority", "seal", "package_id"}
    assert result["authority_raw"] == b'{"status":"fixture"}\n'
    assert result["package_id"] == package_id
    assert set(result["authority"]) == {
        "path",
        "size_bytes",
        "sha256",
        "mode_octal",
        "device",
        "inode",
        "link_count",
    }
    assert set(result["seal"]) == set(result["authority"])
    assert result["authority"]["path"] == str(directory.resolve() / "authority.json")
    assert result["seal"]["path"] == str(directory.resolve() / "SHA256SUMS")
    assert result["authority"]["mode_octal"] == result["seal"]["mode_octal"] == "0644"
    assert result["authority"]["link_count"] == result["seal"]["link_count"] == 1
    assert result["authority"]["inode"] != result["seal"]["inode"]


@pytest.mark.parametrize(
    "seal_raw",
    (
        b"",
        b"0" * 64 + b"  authority.json\n",
        b"0" * 64 + b"  authority.json\n" + b"0" * 64 + b"  extra.json\n",
        b"0" * 64 + b"  renamed.json\n",
        b"0" * 64 + b" authority.json\n",
        b"0" * 64 + b"  authority.json",
    ),
)
def test_missing_extra_or_noncanonical_seal_lines_fail_closed(
    seal_raw: bytes,
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, _ = make_package(tmp_path)
    (directory / "SHA256SUMS").write_bytes(seal_raw)
    (directory / "SHA256SUMS").chmod(0o644)
    package_id = hashlib.sha256(seal_raw).hexdigest()
    with pytest.raises(package.AuthorityPackageError, match="seal bytes"):
        package.verify_authority_package(directory.resolve(), package_id)


def test_changed_authority_and_resealed_package_rejects_stale_external_id(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, original_package_id = make_package(tmp_path)
    changed = b'{"status":"changed"}\n'
    (directory / "authority.json").write_bytes(changed)
    resealed = f"{hashlib.sha256(changed).hexdigest()}  authority.json\n".encode("ascii")
    (directory / "SHA256SUMS").write_bytes(resealed)
    with pytest.raises(package.AuthorityPackageError, match="external package id mismatch"):
        package.verify_authority_package(directory.resolve(), original_package_id)


@pytest.mark.parametrize("package_id", ("", "0" * 63, "A" * 64, 0, None))
def test_package_id_must_be_exact_lowercase_sha256(
    package_id: Any,
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, _ = make_package(tmp_path)
    with pytest.raises(package.AuthorityPackageError, match="lowercase 64-hex"):
        package.verify_authority_package(directory.resolve(), package_id)


def test_renamed_parent_and_member_sets_fail_closed(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, package_id = make_package(tmp_path)
    renamed_parent = tmp_path / "authority-renamed"
    directory.rename(renamed_parent)
    with pytest.raises(package.AuthorityPackageError, match="basename"):
        package.verify_authority_package(renamed_parent.resolve(), package_id)

    directory, package_id = make_package(tmp_path)
    (directory / "authority.json").rename(directory / "authority-renamed.json")
    with pytest.raises(package.AuthorityPackageError, match="member set"):
        package.verify_authority_package(directory.resolve(), package_id)


def test_swapped_member_contents_fail_even_with_matching_external_seal_hash(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, _ = make_package(tmp_path)
    authority_raw = (directory / "authority.json").read_bytes()
    old_seal = (directory / "SHA256SUMS").read_bytes()
    (directory / "authority.json").write_bytes(old_seal)
    new_seal = f"{hashlib.sha256(old_seal).hexdigest()}  authority.json\n".encode("ascii")
    (directory / "SHA256SUMS").write_bytes(new_seal)
    package_id = hashlib.sha256(new_seal).hexdigest()
    with pytest.raises(package.AuthorityPackageError, match="malformed JSON"):
        package.verify_authority_package(directory.resolve(), package_id)
    assert authority_raw != old_seal


def test_symlink_parent_and_member_fail_closed(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    directory, package_id = make_package(real_root)
    alias_root = tmp_path / "alias"
    alias_root.symlink_to(real_root, target_is_directory=True)
    alias_directory = alias_root / "authority-a001"
    with pytest.raises(package.AuthorityPackageError, match="symlink or alias"):
        package.verify_authority_package(alias_directory.absolute(), package_id)

    shutil.rmtree(directory)
    directory.mkdir()
    external = tmp_path / "external-authority.json"
    external.write_bytes(b'{"status":"fixture"}\n')
    external.chmod(0o644)
    (directory / "authority.json").symlink_to(external)
    seal_raw = f"{hashlib.sha256(external.read_bytes()).hexdigest()}  authority.json\n".encode("ascii")
    (directory / "SHA256SUMS").write_bytes(seal_raw)
    (directory / "SHA256SUMS").chmod(0o644)
    with pytest.raises(package.AuthorityPackageError, match="filesystem check failed"):
        package.verify_authority_package(directory.resolve(), hashlib.sha256(seal_raw).hexdigest())


def test_hardlink_and_mode_drift_fail_closed(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, package_id = make_package(tmp_path)
    os.link(directory / "authority.json", tmp_path / "authority-hardlink.json")
    with pytest.raises(package.AuthorityPackageError, match="link_count"):
        package.verify_authority_package(directory.resolve(), package_id)

    (tmp_path / "authority-hardlink.json").unlink()
    (directory / "authority.json").chmod(0o600)
    with pytest.raises(package.AuthorityPackageError, match="mode"):
        package.verify_authority_package(directory.resolve(), package_id)


def test_authority_directory_mode_drift_fails_closed(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, package_id = make_package(tmp_path)
    directory.chmod(0o700)
    with pytest.raises(package.AuthorityPackageError, match="mode is not 0755"):
        package.verify_authority_package(directory.resolve(), package_id)


@pytest.mark.parametrize(
    "field",
    (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_uid",
        "st_gid",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    ),
)
def test_every_security_relevant_stat_field_drift_is_rejected(
    field: str,
    package: ModuleType,
) -> None:
    values = {
        "st_dev": 1,
        "st_ino": 2,
        "st_mode": 0o100644,
        "st_nlink": 1,
        "st_uid": 1000,
        "st_gid": 1000,
        "st_size": 20,
        "st_mtime_ns": 30,
        "st_ctime_ns": 40,
    }
    before = SimpleNamespace(**values)
    changed = dict(values)
    changed[field] = changed[field] + 1
    after = SimpleNamespace(**changed)
    with pytest.raises(package.AuthorityPackageError, match="stat fields drifted"):
        package._require_stable(before, after, "fixture")


def test_parent_replacement_during_retained_fd_read_fails_closed(
    tmp_path: Path,
    package: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory, package_id = make_package(tmp_path)
    original_read_all = package._read_all
    call_count = 0

    def replace_parent(descriptor: int, expected_size: int, label: str) -> bytes:
        nonlocal call_count
        raw = original_read_all(descriptor, expected_size, label)
        call_count += 1
        if call_count == 1:
            moved = tmp_path / "authority-moved"
            directory.rename(moved)
            replacement, replacement_id = make_package(tmp_path)
            assert replacement == directory
            assert replacement_id == package_id
        return raw

    monkeypatch.setattr(package, "_read_all", replace_parent)
    with pytest.raises(
        package.AuthorityPackageError,
        match="stat fields drifted|renamed, swapped, or replaced",
    ):
        package.verify_authority_package(directory.resolve(), package_id)


def test_member_swap_during_retained_fd_read_fails_closed(
    tmp_path: Path,
    package: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory, package_id = make_package(tmp_path)
    original_read_all = package._read_all
    call_count = 0

    def swap_members(descriptor: int, expected_size: int, label: str) -> bytes:
        nonlocal call_count
        raw = original_read_all(descriptor, expected_size, label)
        call_count += 1
        if call_count == 1:
            temporary = directory / "member-swap"
            (directory / "authority.json").rename(temporary)
            (directory / "SHA256SUMS").rename(directory / "authority.json")
            temporary.rename(directory / "SHA256SUMS")
        return raw

    monkeypatch.setattr(package, "_read_all", swap_members)
    with pytest.raises(
        package.AuthorityPackageError,
        match="stat fields drifted|renamed, swapped, or replaced",
    ):
        package.verify_authority_package(directory.resolve(), package_id)


def test_extra_member_and_non_object_authority_fail_closed(
    tmp_path: Path,
    package: ModuleType,
) -> None:
    directory, package_id = make_package(tmp_path)
    (directory / "unexpected").write_bytes(b"")
    with pytest.raises(package.AuthorityPackageError, match="member set"):
        package.verify_authority_package(directory.resolve(), package_id)

    (directory / "unexpected").unlink()
    raw = json.dumps(["not", "an", "object"]).encode() + b"\n"
    (directory / "authority.json").write_bytes(raw)
    seal_raw = f"{hashlib.sha256(raw).hexdigest()}  authority.json\n".encode("ascii")
    (directory / "SHA256SUMS").write_bytes(seal_raw)
    with pytest.raises(package.AuthorityPackageError, match="top-level"):
        package.verify_authority_package(directory.resolve(), hashlib.sha256(seal_raw).hexdigest())
