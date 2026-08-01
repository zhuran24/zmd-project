from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
WRAPPER = RESEARCH / "ab16_native_budget_helper_v1.py"
SOURCE = RESEARCH / "ab16_native_budget_helper_v1.c"
PREBUILT = RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"
PROVENANCE = (
    RESEARCH / "ab16_native_budget_helper_x86_64_v1.provenance.json"
)
BUDGET_SOURCE = RESEARCH / "ab16_budget_authority_v1.py"
PINNED_PYTHON = ROOT / ".venv-uvbolt-backup/bin/python3.13"
COMPILER = Path("/usr/bin/gcc")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_ab16_native_budget_helper_test", WRAPPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_budget() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_ab16_budget_authority_e2e_test", BUDGET_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _helper_from_retained_member(module: ModuleType, path: Path) -> object:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        return module.NativeBudgetHelper(
            descriptor,
            expected_identity=module.expected_package_identity(),
        )
    finally:
        os.close(descriptor)


def test_prebuilt_helper_and_planning_provenance_are_exact() -> None:
    module = _load()
    expected = module.expected_package_identity()
    raw = PREBUILT.read_bytes()
    metadata = PREBUILT.stat(follow_symlinks=False)
    assert {
        "mode": metadata.st_mode & 0o7777,
        "nlink": metadata.st_nlink,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    } == {
        "mode": 0o555,
        "nlink": 1,
        "sha256": expected["sha256"],
        "size_bytes": expected["size_bytes"],
    }
    descriptor = os.open(PREBUILT, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        assert module.snapshot_retained_package_member(descriptor) == expected
    finally:
        os.close(descriptor)

    provenance_raw = PROVENANCE.read_bytes()
    provenance = json.loads(provenance_raw)
    assert provenance_raw == (
        json.dumps(
            provenance,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert provenance["schema"] == (
        "noncert-cuts-ab16-native-budget-helper-provisioning-provenance-v1"
    )
    assert provenance["planning_only"] is True
    assert provenance["authority_receipt"] is False
    assert provenance["self_attesting"] is False
    assert provenance["substitutes_for_direct_binary_verification"] is False
    assert provenance["host"] == {"machine": "x86_64", "platform": "linux"}
    assert provenance["binary"] == {
        "build_id_sha1": expected["build_id_sha1"],
        "byte_order": "little",
        "elf_abi": "SYSV",
        "elf_class": "ELF64",
        "elf_machine": 62,
        "elf_type": 3,
        "elf_version": 1,
        "mode": 0o555,
        "path": PREBUILT.name,
        "sha256": expected["sha256"],
        "size_bytes": expected["size_bytes"],
    }
    assert provenance["build"]["source"] == {
        "mode": 0o644,
        "nlink": 1,
        "path": SOURCE.name,
        "sha256": "251414a4f1e7934a343329ae8461936ddc823a45302645f878f5ecc0a906a60a",
        "size_bytes": 8286,
    }
    assert provenance["build"]["compiler"] == {
        "mode": 0o755,
        "nlink": 3,
        "path": "/usr/bin/gcc",
        "sha256": "25bc8289ab5f2c036d74a4234a5f5a8be87e7cc0d61a919268d6f9febb61fbbb",
        "size_bytes": 2451072,
    }
    assert provenance["build"]["argv"] == [
        "/usr/bin/gcc",
        "-shared",
        "-fPIC",
        "-O2",
        "-std=c17",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wl,-z,relro,-z,now",
        "-o",
        "<same-directory-hidden-staging>",
        "<ab16_native_budget_helper_v1.c>",
    ]


def test_authority_flow_never_invokes_native_build_surface() -> None:
    for name in (
        "ab16_campaign_bootstrap_v2.py",
        "ab16_gate_b_qualification_v1.py",
        "gate_a_recovery_inputs_v1.py",
        "package_independent_verifier_v1.py",
        "ab16_authority_v2.py",
        "ab16_budget_broker_v1.py",
        "ab16_formal_campaign_v1.py",
        "organic_arm_runner_v1.py",
    ):
        source = (RESEARCH / name).read_text(encoding="utf-8")
        assert "build_shared_object(" not in source
        assert "ab16_native_budget_helper_v1.c" not in source
        assert '"/usr/bin/gcc"' not in source


@pytest.fixture()
def built_helper(tmp_path: Path) -> tuple[ModuleType, Path, dict[str, object]]:
    module = _load()
    output = tmp_path / "ab16-native-helper.so"
    identity = module.build_shared_object(
        source=SOURCE,
        output=output,
        compiler=COMPILER,
    )
    return module, output, identity


def test_build_is_no_overwrite_and_atomically_consumes_success_staging(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
) -> None:
    module, output, identity = built_helper
    assert identity == module.snapshot_regular(output, executable=True)
    assert not (output.parent / f".{output.name}.build-staging").exists()
    with pytest.raises(module.NativeBudgetHelperError) as captured:
        module.build_shared_object(source=SOURCE, output=output, compiler=COMPILER)
    assert captured.value.code == "NATIVE_HELPER_NO_OVERWRITE"


def test_identity_pin_and_scm_rights_round_trip(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
) -> None:
    module, output, identity = built_helper
    helper = _helper_from_retained_member(module, output)
    descriptor = helper.create_memfd("ab16-test")
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        os.write(descriptor, b"model")
        helper.send_fd(left.fileno(), descriptor)
        received = helper.recv_fd(right.fileno())
        try:
            assert os.pread(received, 5, 0) == b"model"
        finally:
            os.close(received)
    finally:
        left.close()
        right.close()
        os.close(descriptor)
    forged = module.expected_package_identity()
    forged["sha256"] = "0" * 64
    descriptor = os.open(output, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    with pytest.raises(module.NativeBudgetHelperError) as captured:
        module.NativeBudgetHelper(descriptor, expected_identity=forged)
    os.close(descriptor)
    assert captured.value.code == "NATIVE_HELPER_PIN_MISMATCH"
    with pytest.raises(module.NativeBudgetHelperError) as captured:
        module.NativeBudgetHelper(
            output,
            expected_identity=module.expected_package_identity(),
        )
    assert captured.value.code == "NATIVE_HELPER_AMBIENT_LOAD_FORBIDDEN"


def _run_isolated(script: str, *, helper_path: Path, helper_identity: dict[str, object]) -> subprocess.CompletedProcess[bytes]:
    environment = {
        "AB16_HELPER_IDENTITY": json.dumps(
            _load().expected_package_identity(),
            sort_keys=True,
            separators=(",", ":"),
        ),
        "AB16_HELPER_PATH": str(helper_path),
        "AB16_WRAPPER_PATH": str(WRAPPER),
        "HOME": str(ROOT),
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }
    return subprocess.run(
        [str(PINNED_PYTHON), "-I", "-B", "-c", script],
        cwd="/",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )


def test_real_landlock_ortools_o_trunc_then_final_seals(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
) -> None:
    _, helper_path, helper_identity = built_helper
    script = r"""
import hashlib, importlib.util, json, os, resource, sys
from pathlib import Path
from ortools.sat.python import cp_model

spec = importlib.util.spec_from_file_location("_native", os.environ["AB16_WRAPPER_PATH"])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
identity = json.loads(os.environ["AB16_HELPER_IDENTITY"])
helper_fd = os.open(os.environ["AB16_HELPER_PATH"], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
helper = module.NativeBudgetHelper(helper_fd, expected_identity=identity)
os.close(helper_fd)
fd = helper.create_memfd("ab16-ortools")
try:
    os.write(fd, b"stale-bytes-that-must-be-truncated")
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    helper.close_range_allowlist([1, 2, fd])
    helper.install_no_filesystem_writes_landlock()
    model = cp_model.CpModel()
    x = model.new_bool_var("x")
    model.add(x == 1)
    ok = model.export_to_file(f"/proc/self/fd/{fd}")
    if ok is not True:
        raise SystemExit("EXPORT_FAILED")
    raw = os.pread(fd, os.fstat(fd).st_size, 0)
    if raw.startswith(b"stale-bytes"):
        raise SystemExit("O_TRUNC_NOT_OBSERVED")
    if helper.has_writable_mapping(fd):
        raise SystemExit("WRITABLE_MAPPING")
    seals = helper.install_final_seals(fd)
    if helper.get_seals(fd) != seals:
        raise SystemExit("SEAL_QUERY_DRIFT")
    try:
        os.open("/tmp/ab16-landlock-write-must-fail", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except PermissionError:
        pass
    else:
        raise SystemExit("LANDLOCK_WRITE_ALLOWED")
    print(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw), "seals": seals}))
finally:
    os.close(fd)
"""
    completed = _run_isolated(script, helper_path=helper_path, helper_identity=helper_identity)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    result = json.loads(completed.stdout)
    assert result["size_bytes"] > 0
    assert len(result["sha256"]) == 64
    assert all(character in "0123456789abcdef" for character in result["sha256"])
    assert result["seals"] > 0


def test_real_landlock_blocks_restored_baseline_workspace_but_not_broker_child(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
    tmp_path: Path,
) -> None:
    _, helper_path, _helper_identity = built_helper
    worker_tmp = tmp_path / "formal-ab16/artifacts/prospective/baseline/tmp"
    checkpoint = (
        tmp_path / "formal-ab16/artifacts/prospective/baseline/checkpoint"
    )
    cut_channel = checkpoint / "benders-cuts"
    worker_tmp.mkdir(parents=True)
    cut_channel.mkdir(parents=True)
    worker_tmp.chmod(0o500)
    checkpoint.chmod(0o500)
    script = r"""
import importlib.util, json, os, socket, sys

spec = importlib.util.spec_from_file_location("_native", os.environ["AB16_WRAPPER_PATH"])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
helper_fd = os.open(os.environ["AB16_HELPER_PATH"], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
helper = module.NativeBudgetHelper(
    helper_fd,
    expected_identity=json.loads(os.environ["AB16_HELPER_IDENTITY"]),
)
os.close(helper_fd)
worker, broker = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
pid = os.fork()
if pid == 0:
    worker.close()
    try:
        if broker.recv(1) != b"C":
            os._exit(111)
        os.chmod(os.environ["AB16_TMP"], 0o700)
        os.chmod(os.environ["AB16_CHECKPOINT"], 0o700)
        broker.sendall(b"C")
        if broker.recv(1) != b"P":
            os._exit(112)
        target = os.path.join(os.environ["AB16_CUT_CHANNEL"], "segment-00000000.bin")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        os.write(fd, b"broker-segment\n")
        os.fsync(fd)
        os.close(fd)
        broker.sendall(b"P")
        os._exit(0)
    except BaseException:
        os._exit(113)
broker.close()
helper.close_range_allowlist([1, 2, worker.fileno()])
helper.install_no_filesystem_writes_landlock()
worker.sendall(b"C")
if worker.recv(1) != b"C":
    raise SystemExit("BROKER_CHMOD_FAILED")
for parent in (os.environ["AB16_TMP"], os.environ["AB16_CHECKPOINT"]):
    try:
        fd = os.open(
            os.path.join(parent, "worker-write-forbidden"),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
    except PermissionError:
        pass
    else:
        os.close(fd)
        raise SystemExit("LANDLOCK_RESTORED_MODE_WRITE_ALLOWED")
worker.sendall(b"P")
if worker.recv(1) != b"P":
    raise SystemExit("BROKER_PUBLICATION_FAILED")
worker.close()
waited, status = os.waitpid(pid, 0)
if waited != pid or status != 0:
    raise SystemExit("BROKER_CHILD_FAILED")
print(json.dumps({"status": "PASS"}))
"""
    environment = {
        "AB16_CHECKPOINT": str(checkpoint),
        "AB16_CUT_CHANNEL": str(cut_channel),
        "AB16_HELPER_IDENTITY": json.dumps(
            _load().expected_package_identity(),
            sort_keys=True,
            separators=(",", ":"),
        ),
        "AB16_HELPER_PATH": str(helper_path),
        "AB16_TMP": str(worker_tmp),
        "AB16_WRAPPER_PATH": str(WRAPPER),
        "HOME": str(ROOT),
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }
    completed = subprocess.run(
        [str(PINNED_PYTHON), "-I", "-B", "-c", script],
        cwd="/",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert json.loads(completed.stdout) == {"status": "PASS"}
    assert (cut_channel / "segment-00000000.bin").read_bytes() == b"broker-segment\n"
    assert not (worker_tmp / "worker-write-forbidden").exists()
    assert not (checkpoint / "worker-write-forbidden").exists()


def test_close_range_keeps_only_exact_allowlist(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
) -> None:
    module, output, identity = built_helper
    helper = _helper_from_retained_member(module, output)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    retained = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    discarded = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        try:
            parent.close()
            helper.close_range_allowlist([child.fileno(), retained])
            os.fstat(retained)
            try:
                os.fstat(discarded)
            except OSError:
                child.sendall(b"PASS")
            else:
                child.sendall(b"DISCARDED_FD_SURVIVED")
        except BaseException as exc:
            try:
                child.sendall(f"FAIL:{type(exc).__name__}:{exc}".encode())
            except BaseException:
                pass
        finally:
            os._exit(0)
    child.close()
    try:
        assert parent.recv(4096) == b"PASS"
        _, status = os.waitpid(pid, 0)
        assert status == 0
    finally:
        parent.close()
        os.close(retained)
        os.close(discarded)


def test_tiny_ortools_sealed_memfd_to_budgeted_no_replace_publish(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
    tmp_path: Path,
) -> None:
    module, helper_path, helper_identity = built_helper
    helper = _helper_from_retained_member(module, helper_path)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    environment = {
        "AB16_BROKER_SOCKET_FD": str(child.fileno()),
        "AB16_HELPER_IDENTITY": json.dumps(
            module.expected_package_identity(),
            sort_keys=True,
            separators=(",", ":"),
        ),
        "AB16_HELPER_PATH": str(helper_path),
        "AB16_WRAPPER_PATH": str(WRAPPER),
        "HOME": str(ROOT),
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }
    script = r"""
import importlib.util, json, os, resource, sys
from ortools.sat.python import cp_model

spec = importlib.util.spec_from_file_location("_native", os.environ["AB16_WRAPPER_PATH"])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
helper_fd = os.open(os.environ["AB16_HELPER_PATH"], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
helper = module.NativeBudgetHelper(
    helper_fd,
    expected_identity=json.loads(os.environ["AB16_HELPER_IDENTITY"]),
)
os.close(helper_fd)
broker = int(os.environ["AB16_BROKER_SOCKET_FD"])
model_fd = helper.create_memfd("ab16-budget-e2e")
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
helper.close_range_allowlist([2, broker, model_fd])
helper.install_no_filesystem_writes_landlock()
model = cp_model.CpModel()
x = model.new_bool_var("x")
model.add(x == 1)
if model.export_to_file(f"/proc/self/fd/{model_fd}") is not True:
    raise SystemExit(120)
size = os.fstat(model_fd).st_size
if size <= 0 or size > 1024 * 1024 or helper.has_writable_mapping(model_fd):
    raise SystemExit(121)
helper.install_final_seals(model_fd)
helper.send_fd(broker, model_fd)
os.close(model_fd)
os.close(broker)
"""
    process = subprocess.Popen(
        [str(PINNED_PYTHON), "-I", "-B", "-c", script],
        cwd="/",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        pass_fds=(child.fileno(),),
    )
    child.close()
    received = -1
    try:
        received = helper.recv_fd(parent.fileno())
        stderr = process.communicate(timeout=30)[1]
        assert process.returncode == 0, stderr.decode("utf-8", "replace")
        assert helper.get_seals(received) & helper.final_seal_mask == helper.final_seal_mask
        size = os.fstat(received).st_size
        raw = os.pread(received, size, 0)
        assert raw and len(raw) == size

        budget = _load_budget()
        with budget.FormalBudgetBroker.create(
            tmp_path / "formal-root",
            category_limits={"model": 1024 * 1024},
        ) as broker:
            broker.register_directory("models")
            record = broker.publish_bytes(
                "models/tiny.pbtxt",
                raw,
                maximum_bytes=1024 * 1024,
                artifact_class="model",
            )
            assert record["sha256"] == hashlib.sha256(raw).hexdigest()
            closure = broker.snapshot_root_closure()
            assert broker.verify_root_closure(closure) == closure
            with pytest.raises(budget.BudgetContractError) as captured:
                broker.publish_bytes(
                    "models/tiny.pbtxt",
                    raw,
                    maximum_bytes=1,
                    artifact_class="model",
                )
            assert captured.value.code in {"PAYLOAD_EXCEEDS_MAXIMUM", "ROOT_BUDGET_EXCEEDED"}
    finally:
        parent.close()
        if received >= 0:
            os.close(received)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_rlimit_fsize_reports_sigxfsz_or_efbig(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
) -> None:
    _, helper_path, helper_identity = built_helper
    script = r"""
import importlib.util, json, os, resource, signal, sys
spec = importlib.util.spec_from_file_location("_native", os.environ["AB16_WRAPPER_PATH"])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
helper_fd = os.open(os.environ["AB16_HELPER_PATH"], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
helper = module.NativeBudgetHelper(
    helper_fd,
    expected_identity=json.loads(os.environ["AB16_HELPER_IDENTITY"]),
)
os.close(helper_fd)
fd = helper.create_memfd("ab16-limit")
seen = []
signal.signal(signal.SIGXFSZ, lambda *_: seen.append("SIGXFSZ"))
try:
    resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))
    try:
        written = os.write(fd, b"x" * 8192)
        if written != 8192:
            seen.append("SHORT_WRITE")
        os.write(fd, b"x")
    except OSError as exc:
        if exc.errno != 27:
            raise
        seen.append("EFBIG")
    if not seen:
        raise SystemExit("LIMIT_NOT_ENFORCED")
    print(json.dumps(seen))
finally:
    os.close(fd)
"""
    completed = _run_isolated(script, helper_path=helper_path, helper_identity=helper_identity)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert set(json.loads(completed.stdout)) & {"SIGXFSZ", "EFBIG", "SHORT_WRITE"}


def test_seal_fails_while_writable_mapping_exists(
    built_helper: tuple[ModuleType, Path, dict[str, object]],
) -> None:
    module, output, identity = built_helper
    helper = _helper_from_retained_member(module, output)
    descriptor = helper.create_memfd("ab16-mapped")
    import mmap

    os.ftruncate(descriptor, 4096)
    mapping = mmap.mmap(descriptor, 4096, access=mmap.ACCESS_WRITE)
    try:
        assert helper.has_writable_mapping(descriptor) is True
        with pytest.raises(module.NativeBudgetHelperError) as captured:
            helper.install_final_seals(descriptor)
        assert captured.value.code == "NATIVE_MEMFD_SEAL_FAILED"
    finally:
        mapping.close()
        os.close(descriptor)
