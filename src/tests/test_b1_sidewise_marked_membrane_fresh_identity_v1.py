from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT
    / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"
    / "identity_contract_v1.py"
)


def _load_contract() -> ModuleType:
    name = "_test_smm4_identity_contract_v1"
    spec = importlib.util.spec_from_file_location(name, CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def contract() -> ModuleType:
    return _load_contract()


def _full_identity() -> dict[str, Any]:
    return {
        "path": "/authority/smm4/authority.json",
        "size_bytes": 4096,
        "sha256": "a" * 64,
        "mode_octal": "0644",
        "device": 259,
        "inode": 9001,
        "link_count": 1,
    }


def _projection() -> dict[str, Any]:
    full = _full_identity()
    return {
        "path": full["path"],
        "size_bytes": full["size_bytes"],
        "sha256": full["sha256"],
        "mode_octal": full["mode_octal"],
    }


def test_happy_path_validates_projects_and_joins(contract: ModuleType) -> None:
    full = _full_identity()
    projection = _projection()

    assert contract.validate_full_identity(full, "full") == full
    assert contract.validate_full_identity(full, "full") is not full
    assert contract.validate_projection(projection, "projection") == projection
    assert contract.validate_projection(projection, "projection") is not projection
    assert contract.canonical_content_projection(full, "full") == projection
    assert contract.assert_identity_join(full, projection, copy.deepcopy(full), "authority") == projection


@pytest.mark.parametrize("field", tuple(_full_identity()))
def test_full_identity_rejects_each_missing_field(contract: ModuleType, field: str) -> None:
    value = _full_identity()
    del value[field]

    with pytest.raises(contract.IdentityContractError, match="missing fields"):
        contract.validate_full_identity(value, "full")


@pytest.mark.parametrize("extra_field", ("writer_only_note", 17))
def test_full_identity_rejects_extra_field(contract: ModuleType, extra_field: Any) -> None:
    value = _full_identity()
    value[extra_field] = "must not be silently dropped"

    with pytest.raises(contract.IdentityContractError, match="unexpected fields"):
        contract.validate_full_identity(value, "full")


@pytest.mark.parametrize("field", tuple(_projection()))
def test_projection_rejects_each_missing_field(contract: ModuleType, field: str) -> None:
    value = _projection()
    del value[field]

    with pytest.raises(contract.IdentityContractError, match="missing fields"):
        contract.validate_projection(value, "projection")


def test_projection_rejects_extra_field(contract: ModuleType) -> None:
    value = _projection()
    value["device"] = 259

    with pytest.raises(contract.IdentityContractError, match="unexpected fields"):
        contract.validate_projection(value, "projection")


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("size_bytes", True),
        ("size_bytes", -1),
        ("device", False),
        ("device", -1),
        ("inode", True),
        ("inode", 0),
        ("link_count", False),
        ("link_count", 0),
        ("link_count", 2),
    ),
)
def test_full_identity_rejects_invalid_exact_integer_fields(
    contract: ModuleType,
    field: str,
    bad_value: Any,
) -> None:
    value = _full_identity()
    value[field] = bad_value

    with pytest.raises(contract.IdentityContractError):
        contract.validate_full_identity(value, "full")


@pytest.mark.parametrize(
    "bad_path",
    (
        "",
        "relative/authority.json",
        "//authority/smm4/authority.json",
        "/authority/smm4/../authority.json",
        "/authority/smm4/authority.json/",
        "/authority/\x00smm4.json",
        42,
    ),
)
def test_identity_rejects_noncanonical_path(contract: ModuleType, bad_path: Any) -> None:
    value = _full_identity()
    value["path"] = bad_path

    with pytest.raises(contract.IdentityContractError, match="path"):
        contract.validate_full_identity(value, "full")


@pytest.mark.parametrize(
    "bad_hash",
    (
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        42,
    ),
)
def test_identity_rejects_invalid_sha256(contract: ModuleType, bad_hash: Any) -> None:
    value = _full_identity()
    value["sha256"] = bad_hash

    with pytest.raises(contract.IdentityContractError, match="sha256"):
        contract.validate_full_identity(value, "full")


@pytest.mark.parametrize("bad_mode", ("644", "00644", "08aa", 0o644))
def test_identity_rejects_invalid_mode(contract: ModuleType, bad_mode: Any) -> None:
    value = _full_identity()
    value["mode_octal"] = bad_mode

    with pytest.raises(contract.IdentityContractError, match="mode_octal"):
        contract.validate_full_identity(value, "full")


@pytest.mark.parametrize(
    ("field", "new_value"),
    (
        ("path", "/authority/smm4/other.json"),
        ("size_bytes", 4097),
        ("sha256", "b" * 64),
        ("mode_octal", "0444"),
    ),
)
def test_join_rejects_content_drift(
    contract: ModuleType,
    field: str,
    new_value: Any,
) -> None:
    actual = _full_identity()
    actual[field] = new_value

    with pytest.raises(contract.IdentityContractError, match=rf"{field} drifted"):
        contract.assert_identity_join(_full_identity(), _projection(), actual, "authority")


@pytest.mark.parametrize(
    ("field", "new_value", "message"),
    (
        ("device", 260, "device drifted"),
        ("inode", 9002, "inode drifted"),
        ("link_count", 2, "link_count must equal 1"),
    ),
)
def test_join_rejects_physical_identity_drift(
    contract: ModuleType,
    field: str,
    new_value: int,
    message: str,
) -> None:
    actual = _full_identity()
    actual[field] = new_value

    with pytest.raises(contract.IdentityContractError, match=message):
        contract.assert_identity_join(_full_identity(), _projection(), actual, "authority")


@pytest.mark.parametrize(
    ("field", "new_value"),
    (
        ("path", "/authority/smm4/other.json"),
        ("size_bytes", 4097),
        ("sha256", "b" * 64),
        ("mode_octal", "0444"),
    ),
)
def test_join_rejects_projection_inconsistent_with_expected_full(
    contract: ModuleType,
    field: str,
    new_value: Any,
) -> None:
    projection = _projection()
    projection[field] = new_value

    with pytest.raises(contract.IdentityContractError, match=rf"projection {field} disagrees"):
        contract.assert_identity_join(_full_identity(), projection, _full_identity(), "authority")
