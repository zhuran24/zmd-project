from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import stat
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
VERIFIER_PATH = RESEARCH / "package_independent_verifier_v1.py"
BOOTSTRAP_PATH = RESEARCH / "ab16_campaign_bootstrap_v2.py"
LIFECYCLE_PATH = RESEARCH / "organic_resource_lifecycle_v2.py"
VERIFIER_PACKAGE_PATH = "payload/tool.package_independent_verifier_v1.py"
NATIVE_HELPER_PATH = RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"
NATIVE_HELPER_PACKAGE_PATH = "payload/system.native_budget_helper.bin"
NATIVE_HELPER_WRAPPER_PATH = RESEARCH / "ab16_native_budget_helper_v1.py"
NATIVE_HELPER_WRAPPER_PACKAGE_PATH = "payload/tool.ab16_native_budget_helper_v1.py"
FINAL_RELEASE_ACTOR_PACKAGE_PATH = "payload/tool.ab16_final_release_actor_v1.py"
FORMAL_LOADER_PACKAGE_PATH = "payload/tool.ab16_formal_loader_v1.py"
PYTHON_PACKAGE_PATH = "payload/system.python3_13.bin"
V4_AUTHORITY_PATH = (
    ROOT
    / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
    / "campaign_authority_v4.py"
)

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


def _run_selected_literal_shape(
    literal: str,
    identities: dict[str, object],
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            literal,
            "direct",
            json.dumps(
                identities,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "--",
        ],
        check=False,
        capture_output=True,
    )


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_test_ab16_package_independent_verifier", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_bootstrap() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_test_ab16_campaign_bootstrap_native_factory",
        BOOTSTRAP_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_lifecycle() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_test_ab16_selected_fd_lifecycle",
        LIFECYCLE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_selected_fd_cohorts_preserve_legacy_and_reject_bidirectional_mixes() -> None:
    bootstrap = _load_bootstrap()
    legacy = bootstrap._selected_byte_launch_contract(  # noqa: SLF001
        bootstrap.HISTORICAL_EXTERNAL_PLATFORM_SCHEMA
    )
    prospective = bootstrap._selected_byte_launch_contract(  # noqa: SLF001
        bootstrap.EXTERNAL_PLATFORM_SCHEMA
    )
    assert legacy == {
        "direct_fd_map": {
            "authority": 5,
            "loader": 4,
            "python": 3,
        },
        "execution_strategy": "selected-byte-python-loader-fd-v1",
        "literal_identity": {
            "sha256": (
                "619b0906281cf0ebd3d9361c6b6468b0"
                "a0cc9cb66a46dc0c98b18c25d89e43ff"
            ),
            "size_bytes": 2531,
        },
        "systemd_fd_map": {
            "authority": 5,
            "loader": 4,
            "python": 3,
        },
        "systemd_fd_names": [
            "ab16-python",
            "ab16-loader",
            "ab16-authority",
        ],
    }
    bootstrap._validate_selected_byte_launch_contract(  # noqa: SLF001
        bootstrap.HISTORICAL_EXTERNAL_PLATFORM_SCHEMA,
        legacy,
    )
    bootstrap._validate_selected_byte_launch_contract(  # noqa: SLF001
        bootstrap.EXTERNAL_PLATFORM_SCHEMA,
        prospective,
    )
    with pytest.raises(
        bootstrap.BootstrapError,
        match="cohort or version is mixed",
    ):
        bootstrap._validate_selected_byte_launch_contract(  # noqa: SLF001
            bootstrap.HISTORICAL_EXTERNAL_PLATFORM_SCHEMA,
            prospective,
        )
    with pytest.raises(
        bootstrap.BootstrapError,
        match="cohort or version is mixed",
    ):
        bootstrap._validate_selected_byte_launch_contract(  # noqa: SLF001
            bootstrap.EXTERNAL_PLATFORM_SCHEMA,
            legacy,
        )
    legacy_keys = {
        role: {}
        for role in ("authority", "loader", "python")
    }
    prospective_keys = {
        role: {}
        for role in (
            "authority",
            "loader",
            "native_helper",
            "native_helper_wrapper",
            "python",
        )
    }
    legacy_with_new_shape = _run_selected_literal_shape(
        bootstrap.SELECTED_BYTE_LAUNCH_V1,
        prospective_keys,
    )
    new_with_legacy_shape = _run_selected_literal_shape(
        bootstrap.SELECTED_BYTE_LAUNCH_V2,
        legacy_keys,
    )
    assert legacy_with_new_shape.returncode == 125
    assert legacy_with_new_shape.stderr == b"IDENTITY_KEYS\n"
    assert new_with_legacy_shape.returncode == 125
    assert new_with_legacy_shape.stderr == b"IDENTITY_KEYS\n"


def test_selected_fd_execution_source_builder_rejects_cross_cohort_identities() -> None:
    lifecycle = _load_lifecycle()
    common: dict[str, object] = {
        "authority_identity": {"role": "authority"},
        "initial_working_directory": "/campaign",
        "literal_identity": {"sha256": "0" * 64, "size_bytes": 1},
        "live_source_provenance_root": "/live",
        "loader_identity": {"role": "loader"},
        "module_origin_receipt_path": "/attempt/module-origin.json",
        "package_id": "1" * 64,
        "pre_run_authority_path": "/attempt/pre-run.json",
        "python_identity": {"role": "python"},
        "runner_package_tool_identity": {"role": "runner-package"},
        "runner_selection_path": "/attempt/selection.json",
        "runner_snapshot_member_identity": {"role": "runner-snapshot"},
        "runner_snapshot_relative_path": "organic_arm_runner_v1.py",
        "sealed_snapshot_execution_root": "/snapshot",
        "snapshot_manifest_identity": {"role": "snapshot-manifest"},
        "snapshot_materialization_receipt_identity": {
            "role": "snapshot-receipt"
        },
        "tmpdir": "/attempt/tmp",
    }
    legacy = lifecycle.build_sealed_execution_source(
        **common,
        native_helper_identity=None,
        native_helper_wrapper_identity=None,
        selected_byte_schema=lifecycle.SELECTED_BYTE_LAUNCH_SCHEMA_V1,
    )
    assert set(legacy["selected_byte_launch"]) == {
        "authority_identity",
        "execution_strategy",
        "fd_map",
        "literal_identity",
        "loader_identity",
        "open_file_names",
        "python_identity",
        "schema_version",
        "transport",
    }
    prospective = lifecycle.build_sealed_execution_source(
        **common,
        native_helper_identity={"role": "native-helper"},
        native_helper_wrapper_identity={"role": "native-helper-wrapper"},
        selected_byte_schema=lifecycle.SELECTED_BYTE_LAUNCH_SCHEMA_V2,
    )
    assert prospective["selected_byte_launch"]["fd_map"][
        "budget_broker"
    ] == 8
    with pytest.raises(
        lifecycle.LifecycleError,
        match="mix incompatible cohorts",
    ):
        lifecycle.build_sealed_execution_source(
            **common,
            native_helper_identity={"role": "native-helper"},
            native_helper_wrapper_identity={
                "role": "native-helper-wrapper"
            },
            selected_byte_schema=lifecycle.SELECTED_BYTE_LAUNCH_SCHEMA_V1,
        )
    with pytest.raises(
        lifecycle.LifecycleError,
        match="mix incompatible cohorts",
    ):
        lifecycle.build_sealed_execution_source(
            **common,
            native_helper_identity=None,
            native_helper_wrapper_identity=None,
            selected_byte_schema=lifecycle.SELECTED_BYTE_LAUNCH_SCHEMA_V2,
        )


def test_prospective_selected_literal_consumes_exact_fd3_through_fd8(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    loader = tmp_path / "loader.py"
    authority_path = tmp_path / "authority.py"
    wrapper = tmp_path / "native-wrapper.py"
    native = tmp_path / "native-helper.so"
    loader.write_text(
        """
import json
import os
import socket
import stat
import sys

expected = [
    "--loader-identity",
    "--authority-fd",
    "--authority-identity",
    "--native-helper-wrapper-fd",
    "--native-helper-wrapper-identity",
    "--native-helper-fd",
    "--native-helper-identity",
    "--budget-broker-fd",
]
positions = {value: index for index, value in enumerate(sys.argv)}
if any(value not in positions for value in expected):
    raise SystemExit(20)
if [int(sys.argv[positions[name] + 1]) for name in (
    "--authority-fd",
    "--native-helper-wrapper-fd",
    "--native-helper-fd",
    "--budget-broker-fd",
)] != [5, 6, 7, 8]:
    raise SystemExit(21)
if not stat.S_ISSOCK(os.fstat(8).st_mode):
    raise SystemExit(22)
for name in (
    "--loader-identity",
    "--authority-identity",
    "--native-helper-wrapper-identity",
    "--native-helper-identity",
):
    if set(json.loads(sys.argv[positions[name] + 1])) != {
        "mode", "path", "sha256", "size_bytes"
    }:
        raise SystemExit(23)
if sys.argv[-1] != "--zero-authority-probe":
    raise SystemExit(24)
print("SELECTED_FD3_8_OK", flush=True)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    authority_path.write_text("AUTHORITY = False\n", encoding="utf-8")
    wrapper.write_text("WRAPPER = True\n", encoding="utf-8")
    native.write_bytes(b"\x7fELF-zero-authority-fixture")
    for path in (loader, authority_path, wrapper, native):
        path.chmod(0o444)
    python_path = Path(os.path.realpath(sys.executable))

    def identity(path: Path) -> dict[str, object]:
        raw = path.read_bytes()
        return {
            "mode": stat.S_IMODE(path.stat().st_mode),
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

    identities = {
        "authority": identity(authority_path),
        "loader": identity(loader),
        "native_helper": identity(native),
        "native_helper_wrapper": identity(wrapper),
        "python": identity(python_path),
    }
    selected_files = (
        python_path,
        loader,
        authority_path,
        wrapper,
        native,
    )
    opened = [
        os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        for path in selected_files
    ]
    high = [
        fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, 64)
        for descriptor in opened
    ]
    for descriptor in opened:
        os.close(descriptor)
    broker_parent, broker_child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    broker_high = fcntl.fcntl(
        broker_child.fileno(),
        fcntl.F_DUPFD_CLOEXEC,
        64,
    )
    output_read, output_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        try:
            os.close(output_read)
            for target, source in zip(range(3, 8), high, strict=True):
                os.dup2(source, target)
            os.dup2(broker_high, 8)
            os.dup2(output_write, 1)
            for descriptor in (*high, broker_high, output_write):
                if descriptor > 8:
                    os.close(descriptor)
            os.execve(
                str(python_path),
                [
                    str(python_path),
                    "-I",
                    "-B",
                    "-c",
                    bootstrap.SELECTED_BYTE_LAUNCH_V2,
                    "direct",
                    json.dumps(
                        identities,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "--zero-authority-probe",
                ],
                {
                    "LANG": "C",
                    "LC_ALL": "C",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONHASHSEED": "0",
                    "PYTHONNOUSERSITE": "1",
                    "TZ": "UTC",
                },
            )
        except BaseException:
            os._exit(125)
    os.close(output_write)
    broker_child.close()
    try:
        output = bytearray()
        while True:
            block = os.read(output_read, 65536)
            if not block:
                break
            output.extend(block)
        waited, status = os.waitpid(pid, 0)
        assert waited == pid
        assert os.waitstatus_to_exitcode(status) == 0
        assert bytes(output) == b"SELECTED_FD3_8_OK\n"
    finally:
        os.close(output_read)
        broker_parent.close()
        os.close(broker_high)
        for descriptor in high:
            os.close(descriptor)


@pytest.fixture(scope="module")
def verifier() -> ModuleType:
    return _load()


def _source_identity(
    path: str,
    raw: bytes,
    *,
    mode: int = 0o600,
) -> dict[str, object]:
    return {
        "device": 1,
        "inode": 1,
        "mode": mode,
        "mode_octal": f"{mode:04o}",
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _write_package(
    tmp_path: Path,
    *,
    forged_verifier_manifest: bool = False,
    native_helper_raw: bytes | None = None,
    native_helper_role: str = "system.native_budget_helper.bin",
    native_helper_source_mode: int = 0o555,
    final_release_actor_role: str = "tool.ab16_final_release_actor_v1.py",
) -> tuple[Path, dict[str, object], dict[str, object]]:
    package = tmp_path / "package"
    payload = package / "payload"
    payload.mkdir(parents=True)
    verifier_raw = VERIFIER_PATH.read_bytes()
    members = {
        VERIFIER_PACKAGE_PATH: verifier_raw,
        NATIVE_HELPER_PACKAGE_PATH: (
            NATIVE_HELPER_PATH.read_bytes()
            if native_helper_raw is None
            else native_helper_raw
        ),
        NATIVE_HELPER_WRAPPER_PACKAGE_PATH: NATIVE_HELPER_WRAPPER_PATH.read_bytes(),
        FORMAL_LOADER_PACKAGE_PATH: (
            RESEARCH / "ab16_formal_loader_v1.py"
        ).read_bytes(),
        "payload/campaign_authority_v4.py": V4_AUTHORITY_PATH.read_bytes(),
        PYTHON_PACKAGE_PATH: Path(sys.executable).read_bytes(),
        "payload/input.fixture.json": _canonical({"fixture": "value"}),
        **{
            f"payload/tool.{name}.py": (
                RESEARCH / f"{name}.py"
            ).read_bytes()
            for name in (
                "ab16_authority_v2",
                "ab16_budget_authority_v1",
                "ab16_budget_broker_v1",
                "ab16_campaign_bootstrap_v2",
                "ab16_closure_actor_v1",
                "ab16_final_release_actor_v1",
                "ab16_formal_campaign_v1",
                "ab16_formal_controller_v1",
                "ab16_formal_launch_validator_v1",
                "ab16_formal_orchestrator_v1",
                "ab16_formal_success_verifier_v1",
                "ab16_outer_closeout_state_v1",
                "ab16_outer_guardian_v1",
                "ab16_outer_refunit_closeout_v1",
                "ab16_recovery_closeout_v1",
                "ab16_resource_admission_v1",
                "replay_ab16_formal_root_alt_v1",
                "replay_ab16_formal_root_v1",
                "systemd_unit_reference_v1",
            )
        },
    }
    for relative, raw in members.items():
        path = package / relative
        path.write_bytes(raw)
        path.chmod(
            0o555
            if relative == NATIVE_HELPER_PACKAGE_PATH
            else 0o600
        )

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
        role = (
            native_helper_role
            if relative == NATIVE_HELPER_PACKAGE_PATH
            else final_release_actor_role
            if relative == FINAL_RELEASE_ACTOR_PACKAGE_PATH
            else Path(relative).name
        )
        source_identity = _source_identity(
            f"/predeclared/{role}",
            raw,
            mode=(
                native_helper_source_mode
                if relative == NATIVE_HELPER_PACKAGE_PATH
                else 0o600
            ),
        )
        source_records.append(
            {
                "package_path": relative,
                "parse_json": relative.endswith(".json"),
                "role": role,
                "source_identity": source_identity,
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
    native_pin = verifier_module_pin()
    return package, pin, native_pin


def verifier_module_pin() -> dict[str, object]:
    return {
        "binary_format": "ELF64",
        "build_id_sha1": "808dbb57b4fd260e704cb7399e76d76fef2e3146",
        "byte_order": "little",
        "elf_abi": "SYSV",
        "elf_machine": 62,
        "elf_type": 3,
        "elf_version": 1,
        "host_machine": "x86_64",
        "host_platform": "linux",
        "mode": 0o555,
        "package_path": NATIVE_HELPER_PACKAGE_PATH,
        "sha256": "65150434dc370596413e3e425e5cdcaa2d7960b8b181109f738588e8f40dca81",
        "size_bytes": 16512,
        "wrapper_package_path": NATIVE_HELPER_WRAPPER_PACKAGE_PATH,
    }


def _factory_inputs(
    package: Path,
    pin: dict[str, object],
    native_pin: dict[str, object],
    result: dict[str, object],
) -> tuple[ModuleType, dict[str, object]]:
    bootstrap = _load_bootstrap()
    manifest = json.loads((package / "package-manifest.json").read_bytes())
    sources = {
        record["role"]: record["source_identity"]
        for record in manifest["external_sources"]
    }
    manifest_snapshot = bootstrap.authority.snapshot_regular(
        package / "package-manifest.json"
    )
    seal_snapshot = bootstrap.authority.snapshot_regular(
        package / "SHA256SUMS"
    )
    package_record = {
        "manifest_identity": bootstrap.authority.detached_identity(
            manifest_snapshot
        ),
        "package_dir": str(package.absolute()),
        "package_id": hashlib.sha256(seal_snapshot.data).hexdigest(),
        "schema": bootstrap.PACKAGE_SCHEMA,
        "seal_identity": bootstrap.authority.detached_identity(seal_snapshot),
        "status": "SEALED",
    }
    result["landlock"] = {
        "abi_version": 6,
        "handled_access_fs": 1,
        "new_path_opens_denied": True,
        "policy": "deny-all-filesystem-after-retained-fd-open-v1",
    }
    assert result["verifier_identity"] == pin
    assert result["native_helper_identity"] == native_pin
    return bootstrap, {
        "independent_result": result,
        "manager_epoch": result["manager_epoch"],
        "native_helper_source_identity": {
            **sources["system.native_budget_helper.bin"],
            "requested_path": sources["system.native_budget_helper.bin"][
                "path"
            ],
        },
        "package": package_record,
        "repository_head": result["repository_head"],
        "run_nonce": result["run_nonce"],
        "verifier_source_identity": sources[
            "tool.package_independent_verifier_v1.py"
        ],
        "wrapper_source_identity": sources[
            "tool.ab16_native_budget_helper_v1.py"
        ],
    }


def _verify_in_process(
    verifier: ModuleType,
    package: Path,
    pin: dict[str, object],
    native_pin: dict[str, object],
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
            expected_native_helper=native_pin,
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
    native_pin: dict[str, object],
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
        "--expected-native-helper-json",
        json.dumps(native_pin, separators=(",", ":"), sort_keys=True),
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
    package, pin, native_pin = _write_package(tmp_path)
    result, raw = _verify_in_process(verifier, package, pin, native_pin)
    assert result["status"] == "PASS"
    assert result["arm_launch_authorized"] is False
    assert result["classification_authorized"] is False
    assert result["whole_campaign_authorized"] is False
    assert result["verifier_identity"] == pin
    assert result["native_helper_identity"] == native_pin
    assert raw == _canonical(result)
    assert json.loads(raw)["artifact_manifest_sha256"] == result["artifact_manifest_sha256"]


def test_post_verifier_factory_uses_only_retained_package_members_and_owns_fds(
    tmp_path: Path,
    verifier: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    result, _raw = _verify_in_process(verifier, package, pin, native_pin)
    bootstrap, factory = _factory_inputs(
        package,
        pin,
        native_pin,
        result,
    )
    real_open = os.open
    real_close = os.close
    opened: dict[int, tuple[object, int, int | None]] = {}
    close_count: dict[int, int] = {}

    def tracked_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        opened[descriptor] = (path, flags, dir_fd)
        return descriptor

    def tracked_close(descriptor: int) -> None:
        if descriptor in opened:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(bootstrap.os, "open", tracked_open)
    monkeypatch.setattr(bootstrap.os, "close", tracked_close)
    root_fd = real_open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    before = len(os.listdir("/proc/self/fd"))
    try:
        handle = bootstrap.open_verified_package_native_budget_helper(
            package_root_fd=root_fd,
            **factory,
        )
        assert handle.helper.identity == native_pin
        assert handle.wrapper_module.__file__.startswith("/proc/self/fd/")
        assert not hasattr(handle.wrapper_module, "build_shared_object")
        assert not hasattr(handle.wrapper_module, "subprocess")
        retained = set(opened)
        assert len(retained) == 5
        assert all(
            flags & os.O_NOFOLLOW
            for _path, flags, _dir_fd in opened.values()
        )
        assert all(
            dir_fd is not None
            for _path, _flags, dir_fd in opened.values()
        )
        assert len(os.listdir("/proc/self/fd")) == before + 5
        handle.close()
        handle.close()
        assert close_count == {descriptor: 1 for descriptor in retained}
        assert len(os.listdir("/proc/self/fd")) == before
    finally:
        real_close(root_fd)


def test_post_verifier_budget_role_factory_retains_closed_fd_vocabulary(
    tmp_path: Path,
    verifier: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    result, _raw = _verify_in_process(verifier, package, pin, native_pin)
    bootstrap, factory = _factory_inputs(package, pin, native_pin, result)
    raw = _canonical(result)
    manifest = json.loads((package / "package-manifest.json").read_bytes())
    sources = {
        record["role"]: record["source_identity"]
        for record in manifest["external_sources"]
    }
    role_sources = {
        logical_role: sources[package_path.removeprefix("payload/")]
        for logical_role, package_path in (
            bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS.items()
        )
    }
    selected_sources = {
        logical_role: sources[package_path.removeprefix("payload/")]
        for logical_role, package_path in (
            bootstrap.PACKAGE_SELECTED_FD_TRANSPORT_PATHS.items()
        )
    }
    replay_path = tmp_path / "package-independent-replay.json"
    replay_path.write_bytes(raw)
    replay_identity = bootstrap.authority.detached_identity(
        bootstrap.authority.snapshot_regular(replay_path)
    )
    root_fd = os.open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    replay_fd = os.open(
        replay_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    module_names = tuple(
        alias
        for role in bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS
        for alias in bootstrap.PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[role]
    )
    for module_name in module_names:
        monkeypatch.delitem(sys.modules, module_name, raising=False)
        parent_name, separator, attribute = module_name.rpartition(".")
        parent_module = sys.modules.get(parent_name) if separator else None
        if parent_module is not None:
            monkeypatch.delattr(parent_module, attribute, raising=False)
    try:
        handle = bootstrap.open_verified_package_budget_roles(
            package_root_fd=root_fd,
            independent_replay_fd=replay_fd,
            independent_replay_identity=replay_identity,
            package=factory["package"],
            independent_result=result,
            verifier_source_identity=factory[
                "verifier_source_identity"
            ],
            native_helper_source_identity=factory[
                "native_helper_source_identity"
            ],
            role_source_identities=role_sources,
            selected_source_identities=selected_sources,
            repository_head=factory["repository_head"],
            run_nonce=factory["run_nonce"],
            manager_epoch=factory["manager_epoch"],
        )
        expected_roles = set(
            bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS
        )
        assert set(handle.role_descriptors()) == expected_roles
        assert len(set(handle.retained_descriptors())) == (
            5 + len(expected_roles) + 4
        )
        selected = handle.selected_fd_transport()
        assert (
            selected["schema_version"]
            == bootstrap.PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA
        )
        assert selected["owner"] == {
            "pid": os.getpid(),
            "pid_starttime": bootstrap._proc_starttime(os.getpid()),  # noqa: SLF001
            "uid": os.getuid(),
        }
        assert set(selected["roles"]) == {
            "authority",
            "loader",
            "native_helper",
            "native_helper_wrapper",
            "python",
        }
        assert (
            selected["roles"]["authority"]["descriptor"]
            == handle.role_descriptors()["ab16-authority-v2"]
        )
        assert all(
            item["proc_fd_path"]
            == f"/proc/{os.getpid()}/fd/{item['descriptor']}"
            for item in selected["roles"].values()
        )
        authority_v2 = handle.load_verified_role("ab16-authority-v2")
        closeout_state = handle.load_verified_role(
            "ab16-outer-closeout-state-v1"
        )
        resource_admission = handle.load_verified_role(
            "ab16-resource-admission-v1"
        )
        launch_validator = handle.load_verified_role(
            "ab16-formal-launch-validator-v1"
        )
        success_verifier = handle.load_verified_role(
            "ab16-formal-success-verifier-v1"
        )
        closeout_helper = handle.load_verified_role(
            "ab16-outer-refunit-closeout-v1"
        )
        guardian = handle.load_verified_role("ab16-outer-guardian-v1")
        budget = handle.load_verified_role("ab16-budget-authority-v1")
        broker = handle.load_verified_role("ab16-budget-broker-v1")
        recovery = handle.load_verified_role("ab16-recovery-closeout-v1")
        closure = handle.load_verified_role("ab16-closure-actor-v1")
        assert broker.budget is budget
        assert broker.guardian is guardian
        assert guardian.authority is authority_v2
        assert guardian.closeout_state is closeout_state
        assert guardian.closeout_helper is closeout_helper
        assert guardian.launch_validator is launch_validator
        assert guardian.success_verifier is success_verifier
        assert success_verifier.resource_admission is resource_admission
        assert recovery.budget is budget
        assert recovery.broker is broker
        assert closure.budget is budget
        assert closure.broker is broker
        with pytest.raises(
            bootstrap.BootstrapError,
            match="not authorized",
        ):
            handle.require_verified_role("ambient-role")
        handle.close()
        handle.close()
        assert all(name not in sys.modules for name in module_names)
    finally:
        os.close(replay_fd)
        os.close(root_fd)


def test_selected_fd_transport_is_openable_from_live_fork_owner_without_path_reopen(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    result, _raw = _verify_in_process(verifier, package, pin, native_pin)
    bootstrap, factory = _factory_inputs(package, pin, native_pin, result)
    manifest = json.loads((package / "package-manifest.json").read_bytes())
    sources = {
        record["role"]: record["source_identity"]
        for record in manifest["external_sources"]
    }
    role_sources = {
        logical_role: sources[package_path.removeprefix("payload/")]
        for logical_role, package_path in (
            bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS.items()
        )
    }
    selected_sources = {
        logical_role: sources[package_path.removeprefix("payload/")]
        for logical_role, package_path in (
            bootstrap.PACKAGE_SELECTED_FD_TRANSPORT_PATHS.items()
        )
    }
    replay_path = tmp_path / "package-independent-replay.json"
    replay_path.write_bytes(_canonical(result))
    replay_identity = bootstrap.authority.detached_identity(
        bootstrap.authority.snapshot_regular(replay_path)
    )
    root_fd = os.open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    replay_fd = os.open(
        replay_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    handle = bootstrap.open_verified_package_budget_roles(
        package_root_fd=root_fd,
        independent_replay_fd=replay_fd,
        independent_replay_identity=replay_identity,
        package=factory["package"],
        independent_result=result,
        verifier_source_identity=factory["verifier_source_identity"],
        native_helper_source_identity=factory[
            "native_helper_source_identity"
        ],
        role_source_identities=role_sources,
        selected_source_identities=selected_sources,
        repository_head=factory["repository_head"],
        run_nonce=factory["run_nonce"],
        manager_epoch=factory["manager_epoch"],
    )
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        os.close(ready_read)
        os.close(release_write)
        code = 2
        try:
            transport = handle.selected_fd_transport()
            os.write(ready_write, _canonical(transport))
            if os.read(release_read, 1) != b"x":
                raise RuntimeError("parent release token drifted")
            handle.close()
            code = 0
        except BaseException:
            code = 2
        finally:
            os.close(ready_write)
            os.close(release_read)
            os._exit(code)
    os.close(ready_write)
    os.close(release_read)
    try:
        raw = bytearray()
        while not raw.endswith(b"\n"):
            block = os.read(ready_read, 65536)
            assert block
            raw.extend(block)
        transport = json.loads(raw)
        assert transport["owner"]["pid"] == pid
        assert (
            transport["owner"]["pid_starttime"]
            == bootstrap._proc_starttime(pid)  # noqa: SLF001
        )
        for role, identity in transport["roles"].items():
            descriptor = os.open(
                identity["proc_fd_path"],
                os.O_RDONLY | os.O_CLOEXEC,
            )
            try:
                observed = os.pread(
                    descriptor,
                    identity["size_bytes"],
                    0,
                )
                assert len(observed) == identity["size_bytes"], role
                assert hashlib.sha256(observed).hexdigest() == identity["sha256"]
                assert stat.S_IMODE(os.fstat(descriptor).st_mode) == identity["mode"]
            finally:
                os.close(descriptor)
        os.write(release_write, b"x")
        waited, status = os.waitpid(pid, 0)
        assert waited == pid
        assert os.waitstatus_to_exitcode(status) == 0
    finally:
        os.close(ready_read)
        os.close(release_write)
        handle.close()
        os.close(replay_fd)
        os.close(root_fd)


def test_formal_loader_builds_native_helper_only_from_fixed_package_fds(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    package, _pin, _native_pin = _write_package(
        campaign / "campaign-authority"
    )
    wrapper_path = package / NATIVE_HELPER_WRAPPER_PACKAGE_PATH
    helper_path = package / NATIVE_HELPER_PACKAGE_PATH

    def mode_identity(path: Path) -> dict[str, object]:
        raw = path.read_bytes()
        return {
            "mode": stat.S_IMODE(path.stat().st_mode),
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

    script = r"""
import importlib.util
import json
import os
import sys
spec = importlib.util.spec_from_file_location("_ab16_selected_loader_test", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
authorization = module.load_selected_native_budget_helper_from_fds(
    campaign_dir=sys.argv[2],
    wrapper_identity=json.loads(sys.argv[3]),
    helper_identity=json.loads(sys.argv[4]),
)
if authorization.wrapper_fd != 6 or authorization.helper_fd != 7:
    raise SystemExit(10)
if authorization.helper.identity["sha256"] != json.loads(sys.argv[4])["sha256"]:
    raise SystemExit(11)
if authorization.helper.final_seal_mask <= 0:
    raise SystemExit(12)
if hasattr(authorization.wrapper_module, "build_shared_object"):
    raise SystemExit(14)
if hasattr(authorization.wrapper_module, "subprocess"):
    raise SystemExit(15)
authorization.close()
for descriptor in (6, 7):
    try:
        os.fstat(descriptor)
    except OSError:
        pass
    else:
        raise SystemExit(13)
"""
    source_fds = [
        os.open(wrapper_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW),
        os.open(helper_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW),
    ]
    high_fds = [
        fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, 64)
        for descriptor in source_fds
    ]
    for descriptor in source_fds:
        os.close(descriptor)
    try:
        actions = [
            (os.POSIX_SPAWN_DUP2, high_fds[0], 6),
            (os.POSIX_SPAWN_DUP2, high_fds[1], 7),
            (os.POSIX_SPAWN_CLOSE, high_fds[0]),
            (os.POSIX_SPAWN_CLOSE, high_fds[1]),
        ]
        pid = os.posix_spawn(
            sys.executable,
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                script,
                str(RESEARCH / "ab16_formal_loader_v1.py"),
                str(campaign),
                json.dumps(
                    mode_identity(wrapper_path),
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                json.dumps(
                    mode_identity(helper_path),
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ],
            {
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin:/bin",
            },
            file_actions=actions,
        )
        waited, status = os.waitpid(pid, 0)
        assert waited == pid
        assert os.waitstatus_to_exitcode(status) == 0
    finally:
        for descriptor in high_fds:
            os.close(descriptor)


def test_post_verifier_factory_rejects_prepass_without_opening_roles(
    tmp_path: Path,
    verifier: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    result, _raw = _verify_in_process(verifier, package, pin, native_pin)
    bootstrap, factory = _factory_inputs(
        package,
        pin,
        native_pin,
        result,
    )
    factory["independent_result"] = {
        **result,
        "status": "FAIL_CLOSED",
    }
    root_fd = os.open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    calls: list[object] = []

    def forbidden_open(path: object, *_args: object, **_kwargs: object) -> int:
        calls.append(path)
        raise AssertionError("package roles opened before verifier PASS")

    monkeypatch.setattr(bootstrap.os, "open", forbidden_open)
    try:
        with pytest.raises(bootstrap.BootstrapError):
            bootstrap.open_verified_package_native_budget_helper(
                package_root_fd=root_fd,
                **factory,
            )
    finally:
        os.close(root_fd)
    assert calls == []


def test_post_verifier_factory_closes_each_owned_fd_once_on_late_error(
    tmp_path: Path,
    verifier: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    result, _raw = _verify_in_process(verifier, package, pin, native_pin)
    bootstrap, factory = _factory_inputs(
        package,
        pin,
        native_pin,
        result,
    )
    real_open = os.open
    real_close = os.close
    opened: list[int] = []
    close_count: dict[int, int] = {}

    def tracked_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        opened.append(descriptor)
        return descriptor

    def tracked_close(descriptor: int) -> None:
        if descriptor in opened:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(bootstrap.os, "open", tracked_open)
    monkeypatch.setattr(bootstrap.os, "close", tracked_close)
    monkeypatch.setattr(
        bootstrap,
        "_package_native_manifest_join",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("late factory fault")
        ),
    )
    root_fd = real_open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    before = len(os.listdir("/proc/self/fd"))
    try:
        with pytest.raises(RuntimeError, match="late factory fault"):
            bootstrap.open_verified_package_native_budget_helper(
                package_root_fd=root_fd,
                **factory,
            )
        assert len(opened) == 5
        assert close_count == {descriptor: 1 for descriptor in opened}
        assert len(os.listdir("/proc/self/fd")) == before
    finally:
        real_close(root_fd)


def test_post_verifier_factory_rejects_symlinked_package_role(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    result, _raw = _verify_in_process(verifier, package, pin, native_pin)
    bootstrap, factory = _factory_inputs(
        package,
        pin,
        native_pin,
        result,
    )
    wrapper = package / NATIVE_HELPER_WRAPPER_PACKAGE_PATH
    outside = tmp_path / "unknown-wrapper.py"
    outside.write_bytes(wrapper.read_bytes())
    wrapper.unlink()
    wrapper.symlink_to(outside)
    root_fd = os.open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    before = len(os.listdir("/proc/self/fd"))
    try:
        with pytest.raises(bootstrap.BootstrapError):
            bootstrap.open_verified_package_native_budget_helper(
                package_root_fd=root_fd,
                **factory,
            )
        assert outside.exists()
        assert len(os.listdir("/proc/self/fd")) == before
    finally:
        os.close(root_fd)


def test_manifest_cannot_self_authorize_forged_verifier_identity(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(tmp_path, forged_verifier_manifest=True)
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin, native_pin)
    assert captured.value.code == "VERIFIER_MANIFEST_DRIFT"


def test_external_verifier_pin_drift_fails_before_package_manifest_trust(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    stale = dict(pin)
    stale["sha256"] = "f" * 64
    with pytest.raises(verifier.PackageVerifierError, match="external pre-registration"):
        _verify_in_process(verifier, package, stale, native_pin)


def test_native_helper_missing_or_role_substitution_fails_closed(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(
        tmp_path,
        native_helper_role="system.substituted_native_helper.bin",
    )
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin, native_pin)
    assert captured.value.code == "NATIVE_HELPER_ROLE_MISSING"

    missing_package, missing_pin, missing_native_pin = _write_package(
        tmp_path / "missing",
    )
    (missing_package / NATIVE_HELPER_PACKAGE_PATH).unlink()
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(
            verifier,
            missing_package,
            missing_pin,
            missing_native_pin,
        )
    assert captured.value.code == "PACKAGE_INCOMPLETE"


def test_native_helper_source_mode_drift_fails_closed(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(
        tmp_path,
        native_helper_source_mode=0o444,
    )
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin, native_pin)
    assert captured.value.code == "NATIVE_HELPER_SOURCE_DRIFT"


def test_final_release_actor_role_substitution_fails_closed(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    package, pin, native_pin = _write_package(
        tmp_path,
        final_release_actor_role="tool.substituted_final_release_actor_v1.py",
    )
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin, native_pin)
    assert captured.value.code == "FINAL_RELEASE_ACTOR_ROLE_MISSING"


def test_native_helper_sha_and_architecture_drift_fail_closed(
    tmp_path: Path,
    verifier: ModuleType,
) -> None:
    raw = bytearray(NATIVE_HELPER_PATH.read_bytes())
    raw[18:20] = (183).to_bytes(2, "little")  # EM_AARCH64
    package, pin, native_pin = _write_package(
        tmp_path,
        native_helper_raw=bytes(raw),
    )
    with pytest.raises(verifier.PackageVerifierError) as captured:
        _verify_in_process(verifier, package, pin, native_pin)
    assert captured.value.code == "NATIVE_HELPER_SOURCE_DRIFT"

    expected = verifier_module_pin()
    expected["sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(verifier.PackageVerifierError) as captured:
        verifier._verify_native_helper_bytes(bytes(raw), expected)
    assert captured.value.code == "NATIVE_HELPER_ELF_DRIFT"


def test_native_helper_expected_pin_has_no_compatibility_default(
    verifier: ModuleType,
) -> None:
    forged = verifier_module_pin()
    forged["sha256"] = "0" * 64
    with pytest.raises(verifier.PackageVerifierError) as captured:
        verifier._validate_expected_native_helper(forged)
    assert captured.value.code == "NATIVE_HELPER_IDENTITY_INVALID"


@pytest.mark.parametrize("node_kind", ["regular", "directory", "symlink", "fifo"])
def test_complete_root_closure_rejects_every_extra_node_type(
    tmp_path: Path,
    verifier: ModuleType,
    node_kind: str,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
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
        _verify_in_process(verifier, package, pin, native_pin)
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
    package, pin, native_pin = _write_package(tmp_path)
    completed, raw = _run_selected_fd(package, pin, native_pin)
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
    package, pin, native_pin = _write_package(tmp_path)
    completed, raw = _run_selected_fd(
        package,
        pin,
        native_pin,
        ambient_origin=tmp_path / "ambient.py",
    )
    assert completed.returncode == 2
    result = json.loads(raw)
    assert result["status"] == "FAIL_CLOSED"
    assert result["error_code"] == "AMBIENT_MODULE_REJECTED"
    assert result["arm_launch_authorized"] is False


def test_selected_fd_rejects_ambient_writable_path_descriptor(
    tmp_path: Path,
) -> None:
    package, pin, native_pin = _write_package(tmp_path)
    writable_path = tmp_path / "ambient-output"
    writable_fd = os.open(writable_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        completed, raw = _run_selected_fd(
            package,
            pin,
            native_pin,
            extra_fd=writable_fd,
        )
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
