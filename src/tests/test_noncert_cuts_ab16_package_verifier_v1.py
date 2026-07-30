from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
VERIFIER_PATH = RESEARCH / "package_independent_verifier_v1.py"
VERIFIER_PACKAGE_PATH = "payload/tool.package_independent_verifier_v1.py"

FD_LOADER = (
    "import os,sys;"
    "f=int(sys.argv[1]);"
    "n=os.fstat(f).st_size;"
    "r=os.pread(f,n,0);"
    "sys.argv=['/proc/self/fd/'+str(f)]+sys.argv[2:];"
    "globals()['__file__']='/proc/self/fd/'+str(f);"
    "exec(compile(r,globals()['__file__'],'exec',dont_inherit=True),globals())"
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_test_ab16_package_independent_verifier", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier() -> ModuleType:
    return _load()


def _source_identity(path: str, raw: bytes) -> dict[str, object]:
    return {
        "device": 1,
        "inode": 1,
        "mode": 0o600,
        "mode_octal": "0600",
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _write_package(
    tmp_path: Path,
    *,
    forged_verifier_manifest: bool = False,
) -> tuple[Path, dict[str, object]]:
    package = tmp_path / "package"
    payload = package / "payload"
    payload.mkdir(parents=True)
    verifier_raw = VERIFIER_PATH.read_bytes()
    members = {
        VERIFIER_PACKAGE_PATH: verifier_raw,
        "payload/input.fixture.json": _canonical({"fixture": "value"}),
    }
    for relative, raw in members.items():
        path = package / relative
        path.write_bytes(raw)
        path.chmod(0o600)

    member_records: list[dict[str, object]] = []
    source_records: list[dict[str, object]] = []
    for relative, raw in sorted(members.items()):
        digest = hashlib.sha256(raw).hexdigest()
        member_records.append(
            {
                "path": relative,
                "sha256": "0" * 64 if forged_verifier_manifest and relative == VERIFIER_PACKAGE_PATH else digest,
                "size_bytes": len(raw),
            }
        )
        role = Path(relative).name
        source_records.append(
            {
                "package_path": relative,
                "parse_json": relative.endswith(".json"),
                "role": role,
                "source_identity": _source_identity(f"/predeclared/{role}", raw),
            }
        )
    manifest = {
        "authorization_semantics": "byte qualification only; package PASS cannot launch any child",
        "external_sources": source_records,
        "manager_epoch": {"schema": "fixture-manager-epoch-v1"},
        "package_members": member_records,
        "repository_head": "1" * 40,
        "run_nonce": "run-fixture-0001",
        "schema": "noncert-cuts-campaign-authority-manifest-v5",
        "seal_contract": {
            "package_id": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_domain": "all regular files below package except SHA256SUMS",
            "writes_after_seal": "forbidden",
        },
    }
    manifest_raw = _canonical(manifest)
    (package / "package-manifest.json").write_bytes(manifest_raw)
    (package / "package-manifest.json").chmod(0o600)
    seal_members = dict(members)
    seal_members["package-manifest.json"] = manifest_raw
    seal_raw = "".join(
        f"{hashlib.sha256(seal_members[path]).hexdigest()}  {path}\n" for path in sorted(seal_members)
    ).encode("ascii")
    (package / "SHA256SUMS").write_bytes(seal_raw)
    (package / "SHA256SUMS").chmod(0o600)
    pin = {
        "package_path": VERIFIER_PACKAGE_PATH,
        "sha256": hashlib.sha256(verifier_raw).hexdigest(),
        "size_bytes": len(verifier_raw),
    }
    return package, pin


def _verify_in_process(
    verifier: ModuleType,
    package: Path,
    pin: dict[str, object],
) -> tuple[dict[str, object], bytes]:
    package_fd = os.open(package, os.O_RDONLY | os.O_DIRECTORY)
    verifier_fd = os.open(package / VERIFIER_PACKAGE_PATH, os.O_RDONLY)
    read_fd, write_fd = os.pipe()
    try:
        result = verifier.verify_package_from_fds(
            package_fd=package_fd,
            verifier_fd=verifier_fd,
            result_fd=write_fd,
            expected_verifier=pin,
            install_landlock=False,
            enforce_ambient=False,
            enforce_fd_surface=False,
        )
        os.close(write_fd)
        write_fd = -1
        raw = b""
        while block := os.read(read_fd, 65536):
            raw += block
        return result, raw
    finally:
        for descriptor in (package_fd, verifier_fd, read_fd, write_fd):
            if descriptor >= 0:
                os.close(descriptor)


def _run_selected_fd(
    package: Path,
    pin: dict[str, object],
    *,
    ambient_origin: Path | None = None,
    extra_fd: int | None = None,
) -> tuple[subprocess.CompletedProcess[bytes], bytes]:
    package_fd = os.open(package, os.O_RDONLY | os.O_DIRECTORY)
    verifier_fd = os.open(package / VERIFIER_PACKAGE_PATH, os.O_RDONLY)
    read_fd, write_fd = os.pipe()
    pass_fds = [package_fd, verifier_fd, write_fd]
    if extra_fd is not None:
        pass_fds.append(extra_fd)
    prefix = ""
    if ambient_origin is not None:
        prefix = (
            "import types;"
            "_m=types.ModuleType('ambient_fixture');"
            f"_m.__file__={str(ambient_origin)!r};"
            "sys.modules['ambient_fixture']=_m;"
        )
    command = [
        sys.executable,
        "-I",
        "-B",
        "-S",
        "-c",
        FD_LOADER.replace("exec(compile", prefix + "exec(compile", 1),
        str(verifier_fd),
        "--package-fd",
        str(package_fd),
        "--verifier-fd",
        str(verifier_fd),
        "--result-fd",
        str(write_fd),
        "--expected-verifier-json",
        json.dumps(pin, separators=(",", ":"), sort_keys=True),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=tuple(pass_fds),
            timeout=30,
        )
        os.close(write_fd)
        write_fd = -1
        raw = b""
        while block := os.read(read_fd, 65536):
            raw += block
        return completed, raw
    finally:
        for descriptor in (package_fd, verifier_fd, read_fd, write_fd):
            if descriptor >= 0:
                os.close(descriptor)


def test_retained_fd_verifier_replays_exact_package_and_writes_canonical_pipe_result(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin = _write_package(tmp_path)
    result, raw = _verify_in_process(verifier, package, pin)
    assert result["status"] == "PASS"
    assert result["arm_launch_authorized"] is False
    assert result["classification_authorized"] is False
    assert result["whole_campaign_authorized"] is False
    assert result["verifier_identity"] == pin
    assert raw == _canonical(result)
    assert json.loads(raw)["artifact_manifest_sha256"] == result["artifact_manifest_sha256"]


def test_manifest_cannot_self_authorize_forged_verifier_identity(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin = _write_package(tmp_path, forged_verifier_manifest=True)
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin)
    assert captured.value.code == "VERIFIER_MANIFEST_DRIFT"


def test_external_verifier_pin_drift_fails_before_package_manifest_trust(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin = _write_package(tmp_path)
    stale = dict(pin)
    stale["sha256"] = "f" * 64
    with pytest.raises(verifier.PackageVerifierError, match="external pre-registration"):
        _verify_in_process(verifier, package, stale)


@pytest.mark.parametrize("node_kind", ["regular", "directory", "symlink", "fifo"])
def test_complete_root_closure_rejects_every_extra_node_type(
    tmp_path: Path,
    verifier: ModuleType,
    node_kind: str,
) -> None:
    package, pin = _write_package(tmp_path)
    extra = package / "unexpected"
    if node_kind == "regular":
        extra.write_bytes(b"extra")
    elif node_kind == "directory":
        extra.mkdir()
    elif node_kind == "symlink":
        extra.symlink_to("payload")
    else:
        os.mkfifo(extra)
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin)
    assert captured.value.code in {
        "PACKAGE_CLOSURE_DRIFT",
        "PACKAGE_SEAL_DRIFT",
        "SPECIAL_NODE_REJECTED",
        "SYMLINK_REJECTED",
    }


def test_path_escape_and_noncanonical_seal_are_rejected(verifier: ModuleType) -> None:
    with pytest.raises(verifier.PackageVerifierError, match="unsafe relative path"):
        verifier._parse_sha256sums((b"0" * 64) + b"  ../escape\n")
    with pytest.raises(verifier.PackageVerifierError, match="ordering"):
        verifier._parse_sha256sums(
            (b"1" * 64) + b"  z\n" + (b"2" * 64) + b"  a\n"
        )


def test_real_landlock_selected_fd_positive_control(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    try:
        abi = verifier._landlock_abi()
    except verifier.PackageVerifierError as exc:
        if exc.code == "LANDLOCK_UNAVAILABLE":
            pytest.skip(str(exc))
        raise
    assert abi >= 1
    package, pin = _write_package(tmp_path)
    completed, raw = _run_selected_fd(package, pin)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert completed.stdout == b""
    result = json.loads(raw)
    assert raw == _canonical(result)
    assert result["status"] == "PASS"
    assert result["landlock"]["abi_version"] == abi
    assert result["landlock"]["new_path_opens_denied"] is True


def test_selected_fd_rejects_ambient_nonstdlib_module_without_authority_consumption(
    tmp_path: Path,
) -> None:
    package, pin = _write_package(tmp_path)
    completed, raw = _run_selected_fd(package, pin, ambient_origin=tmp_path / "ambient.py")
    assert completed.returncode == 2
    result = json.loads(raw)
    assert result["status"] == "FAIL_CLOSED"
    assert result["error_code"] == "AMBIENT_MODULE_REJECTED"
    assert result["arm_launch_authorized"] is False


def test_selected_fd_rejects_ambient_writable_path_descriptor(
    tmp_path: Path,
) -> None:
    package, pin = _write_package(tmp_path)
    writable_path = tmp_path / "ambient-output"
    writable_fd = os.open(writable_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        completed, raw = _run_selected_fd(package, pin, extra_fd=writable_fd)
    finally:
        os.close(writable_fd)
    assert completed.returncode == 2
    result = json.loads(raw)
    assert result["status"] == "FAIL_CLOSED"
    assert result["error_code"] == "FD_SURFACE_DRIFT"


def test_source_has_no_project_import_or_output_path_surface() -> None:
    source = VERIFIER_PATH.read_text()
    assert "from src" not in source
    assert "import src" not in source
    assert "docs.research" not in source
    assert "open(output" not in source
    assert "Path(" not in source
