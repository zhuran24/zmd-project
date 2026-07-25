from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATION = _load(
    "noncert_cuts_ab16_gate_a_validation_v2_tested",
    TOOLS / "gate_a_validation_v2.py",
)


@pytest.mark.parametrize(
    ("mutation", "detail"),
    [
        ("authorization", "arm_launch_authorized"),
        ("authorization", "formal_campaign_creation_authorized"),
        ("authorization", "solver_run_authorized"),
        ("schema", ""),
        ("purpose", ""),
        ("extra", ""),
    ],
)
def test_authority_ready_requires_exact_nonauthorizing_semantics(
    mutation: str,
    detail: str,
) -> None:
    identity = {
        "mode": 0o444,
        "path": "/fixture/authority.json",
        "sha256": "b" * 64,
        "size_bytes": 123,
    }
    digest = "a" * 64
    run_nonce = "drill-fixture-ready"
    record = {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "disposable_drill_ready": True,
        "formal_campaign_created": False,
        "planned_source_set_digest": digest,
        "pre_run_authority_identity": identity,
        "purpose": VALIDATION.drill_authority.RESULT_PURPOSE,
        "run_nonce": run_nonce,
        "schema_version": VALIDATION.drill_authority.RESULT_SCHEMA,
        "selection_identity": identity,
        "status": "PASS",
    }
    assert (
        VALIDATION._validate_authority_ready(  # noqa: SLF001
            record,
            planned_source_set_digest=digest,
            pre_run_identity=identity,
            run_nonce=run_nonce,
            selection_identity=identity,
        )
        == record
    )

    mutated = copy.deepcopy(record)
    if mutation == "authorization":
        mutated["authorizations"][detail] = True
    elif mutation == "schema":
        mutated["schema_version"] = "drifted"
    elif mutation == "purpose":
        mutated["purpose"] = "drifted"
    elif mutation == "extra":
        mutated["unexpected"] = False
    else:  # pragma: no cover - the parameter list is static
        raise AssertionError("unreachable mutation")
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="authority-ready",
    ):
        VALIDATION._validate_authority_ready(  # noqa: SLF001
            mutated,
            planned_source_set_digest=digest,
            pre_run_identity=identity,
            run_nonce=run_nonce,
            selection_identity=identity,
        )


def _regular(path: Path, raw: bytes, *, mode: int = 0o444) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(mode)
    return VALIDATION._snapshot_identity(path)  # noqa: SLF001


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict[str, object], Path]:
    repository = tmp_path / "repository"
    repository.mkdir(parents=True)
    python_identity = _regular(
        tmp_path / "tools/python3.13",
        b"fixture python executable\n",
        mode=0o755,
    )
    preflight_identity = _regular(
        tmp_path / "inputs/preflight_gate.py",
        b"raise AssertionError('subprocess must be monkeypatched')\n",
        mode=0o444,
    )
    current_tool = VALIDATION._snapshot_identity(Path(VALIDATION.__file__))  # noqa: SLF001
    authority_ready_identity = _regular(
        tmp_path / "drill/authority/authority-ready.json",
        b'{"status":"PASS"}',
    )
    detached_replay_path = tmp_path / "drill/attempt/detached-replay.json"
    detached_replay_identity = _regular(
        detached_replay_path,
        b'{"status":"PASS"}',
    )
    pre_run_identity = _regular(
        tmp_path / "drill/attempt/pre-run-authority.json",
        b'{"status":"PASS"}',
    )
    history_identity = _regular(
        tmp_path / "drill/authority/history-freeze-replay.json",
        b'{"status":"PASS"}',
    )
    capability_identity = _regular(
        tmp_path / "drill/authority/reference-capability.json",
        b'{"status":"PASS"}',
    )
    capability_transcript_identity = _regular(
        tmp_path / "drill/authority/reference-capability-transcript.json",
        b'{"status":"PASS"}',
    )
    authority = VALIDATION.bootstrap.authority
    manager_path = tmp_path / "tools/systemd"
    sudo_path = tmp_path / "tools/sudo"
    busctl_path = tmp_path / "tools/busctl"
    _regular(manager_path, b"fixture systemd manager\n", mode=0o755)
    _regular(sudo_path, b"fixture sudo\n", mode=0o755)
    _regular(busctl_path, b"fixture busctl\n", mode=0o755)
    full = lambda path: authority.full_identity(  # noqa: E731
        authority.snapshot_regular(path)
    )
    attestor = VALIDATION.bootstrap.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    manager_epoch = {
        "attestation_toolchain": {
            "attestor": full(attestor),
            "python": full(Path(str(python_identity["path"]))),
            "sudo": full(sudo_path),
        },
        "attestor_ast_audit": authority.audit_attestor_source(attestor.read_bytes()),
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": full(manager_path),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": full(busctl_path)},
        "schema": authority.MANAGER_EPOCH_SCHEMA,
    }
    planned_digest = "a" * 64
    pre_run = {
        "history_freeze_replay_identity": history_identity,
        "manager_epoch": manager_epoch,
        "reference_capability_identity": capability_identity,
        "reference_capability_transcript_identity": (capability_transcript_identity),
        "repository_head": HEAD,
        "repository_root": str(repository),
        "tool_identities": {"python3_13": python_identity},
    }
    sources = {
        VALIDATION.PREFLIGHT_SOURCE_ROLE: {
            **preflight_identity,
            "device": 1,
            "inode": 2,
            "mode_octal": f"{preflight_identity['mode']:04o}",
        },
        VALIDATION.TOOL_SOURCE_ROLE: {
            **current_tool,
            "device": 3,
            "inode": 4,
            "mode_octal": f"{current_tool['mode']:04o}",
        },
    }
    evidence: dict[str, object] = {
        "authority_ready_identity": authority_ready_identity,
        "detached_replay_identity": detached_replay_identity,
        "planned_source_set_digest": planned_digest,
        "pre_run": pre_run,
        "pre_run_identity": pre_run_identity,
        "selection_identity": _regular(
            tmp_path / "drill/attempt/selection.json",
            b'{"status":"PASS"}',
        ),
        "sources": sources,
    }

    def replay_drill(_authority_root: Path) -> dict[str, object]:
        for field in ("authority_ready_identity", "detached_replay_identity"):
            expected = evidence[field]
            assert isinstance(expected, dict)
            observed = VALIDATION._snapshot_identity(Path(str(expected["path"])))  # noqa: SLF001
            if observed != expected:
                raise VALIDATION.GateAValidationError(f"{field} byte identity drifted")
        return copy.deepcopy(evidence)

    monkeypatch.setattr(VALIDATION, "_verify_drill", replay_drill)
    monkeypatch.setattr(
        VALIDATION,
        "_reobserve_planned_sources",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        VALIDATION.drill_authority,
        "_observe_repository_head",
        lambda _repository, _sources: HEAD,
    )
    monkeypatch.setattr(
        VALIDATION.drill_authority,
        "_capture_live_manager_epoch",
        lambda _sources: {
            "manager_epoch": copy.deepcopy(manager_epoch),
            "transcript": {},
        },
    )
    return repository, evidence, detached_replay_path


def _record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    exit_code: int,
) -> tuple[Path, Path, dict[str, object]]:
    repository, evidence, detached_replay_path = _fixture(
        tmp_path,
        monkeypatch,
    )
    monkeypatch.setattr(
        VALIDATION.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=exit_code,
            stderr=b"preflight stderr\n" if exit_code else b"",
            stdout=b"preflight stdout\n",
        ),
    )
    output = tmp_path / "full-preflight-a001"
    result = VALIDATION.record_full_preflight(
        authority_root=tmp_path / "drill",
        repository_root=repository,
        output_dir=output,
    )
    return output, detached_replay_path, result


def _runtime_report_source() -> bytes:
    grandchild = """
import json
import os
import sys
import sysconfig
print(json.dumps({
    "base_executable": sys._base_executable,
    "executable": sys.executable,
    "fd_reachable": bool(sys.executable and os.path.exists(sys.executable)),
    "prefix": sys.prefix,
    "exec_prefix": sys.exec_prefix,
    "stdlib": sysconfig.get_path("stdlib"),
}, sort_keys=True))
""".strip()
    child = f"""
import json
import os
import subprocess
import sys
import sysconfig
completed = subprocess.run(
    [sys.executable, "-I", "-c", {grandchild!r}],
    check=True,
    capture_output=True,
    text=True,
)
print(json.dumps({{
    "base_executable": sys._base_executable,
    "executable": sys.executable,
    "fd_reachable": bool(sys.executable and os.path.exists(sys.executable)),
    "grandchild": json.loads(completed.stdout),
    "grandchild_stderr": completed.stderr,
    "prefix": sys.prefix,
    "exec_prefix": sys.exec_prefix,
    "stdlib": sysconfig.get_path("stdlib"),
}}, sort_keys=True))
""".strip()
    source = f"""
import json
import os
import subprocess
import sys
import sysconfig
completed = subprocess.run(
    [sys.executable, "-I", "-c", {child!r}],
    check=True,
    capture_output=True,
    text=True,
)
print(json.dumps({{
    "argv": sys.argv,
    "base_executable": sys._base_executable,
    "child": json.loads(completed.stdout),
    "child_stderr": completed.stderr,
    "executable": sys.executable,
    "fd_reachable": bool(sys.executable and os.path.exists(sys.executable)),
    "pid": os.getpid(),
    "prefix": sys.prefix,
    "exec_prefix": sys.exec_prefix,
    "stdlib": sysconfig.get_path("stdlib"),
}}, sort_keys=True))
""".strip()
    return source.encode()


def _assert_runtime_report(report: dict[str, object], *, expected_prefix: str) -> None:
    executable = report["executable"]
    assert isinstance(executable, str) and executable.startswith(expected_prefix)
    assert report["base_executable"] == executable
    assert report["fd_reachable"] is True
    for field in ("prefix", "exec_prefix", "stdlib"):
        value = report[field]
        assert isinstance(value, str) and Path(value).is_absolute()
        assert Path(value).is_dir()


def test_same_fd_python_supports_two_nested_python_launches(
    tmp_path: Path,
) -> None:
    python_path = Path(sys.executable).resolve()
    python_identity = VALIDATION._snapshot_identity(python_path)  # noqa: SLF001
    script_path = tmp_path / "nested_preflight.py"
    script_identity = _regular(
        script_path,
        _runtime_report_source(),
    )

    completed = VALIDATION._run_same_fd_python_script(  # noqa: SLF001
        python_identity=python_identity,
        script_identity=script_identity,
        repository=tmp_path,
        forwarded=("--fixture-full",),
        environment=os.environ,
        timeout_seconds=20,
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    assert b"Could not find platform dependent libraries" not in completed.stderr
    report = json.loads(completed.stdout)
    expected_prefix = f"/proc/{report['pid']}/fd/"
    assert report["argv"] == [str(script_path), "--fixture-full"]
    _assert_runtime_report(report, expected_prefix=expected_prefix)
    child = report["child"]
    assert isinstance(child, dict)
    _assert_runtime_report(child, expected_prefix=expected_prefix)
    assert child["grandchild_stderr"] == ""
    grandchild = child["grandchild"]
    assert isinstance(grandchild, dict)
    _assert_runtime_report(grandchild, expected_prefix=expected_prefix)
    assert report["child_stderr"] == ""


@pytest.mark.parametrize("python_fd_mode", ["wrong", "closed"])
def test_loader_rejects_wrong_or_closed_python_fd(
    tmp_path: Path,
    python_fd_mode: str,
) -> None:
    python_path = Path(sys.executable).resolve()
    python_identity = VALIDATION._snapshot_identity(python_path)  # noqa: SLF001
    script_path = tmp_path / "loader_fixture.py"
    script_path.write_bytes(b"print('must not run')\n")
    script_path.chmod(0o444)
    script_identity = VALIDATION._snapshot_identity(script_path)  # noqa: SLF001
    python_fd = os.open(
        python_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    script_fd = os.open(
        script_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    closed_fd = os.open(
        script_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    os.close(closed_fd)
    supplied_python_fd = script_fd if python_fd_mode == "wrong" else closed_fd
    argv = [
        str(python_path),
        "-I",
        "-c",
        VALIDATION._SCRIPT_LOADER,  # noqa: SLF001
        str(supplied_python_fd),
        str(script_fd),
        str(python_path),
        str(python_identity["mode"]),
        str(python_identity["size_bytes"]),
        str(python_identity["sha256"]),
        str(script_path),
        str(script_identity["mode"]),
        str(script_identity["size_bytes"]),
        str(script_identity["sha256"]),
    ]
    try:
        completed = subprocess.run(
            argv,
            check=False,
            close_fds=True,
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(python_fd, script_fd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    finally:
        os.close(script_fd)
        os.close(python_fd)
    assert completed.returncode != 0
    assert b"must not run" not in completed.stdout
    assert b"Could not find platform dependent libraries" not in completed.stderr


def test_same_fd_runner_rejects_script_identity_drift(
    tmp_path: Path,
) -> None:
    python_identity = VALIDATION._snapshot_identity(  # noqa: SLF001
        Path(sys.executable).resolve()
    )
    script_path = tmp_path / "drifted.py"
    script_identity = _regular(script_path, b"print('original')\n")
    script_path.chmod(0o644)
    script_path.write_bytes(b"print('mutated')\n")
    script_path.chmod(0o444)

    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="preflight script identity drifted",
    ):
        VALIDATION._run_same_fd_python_script(  # noqa: SLF001
            python_identity=python_identity,
            script_identity=script_identity,
            repository=tmp_path,
            forwarded=(),
            environment=os.environ,
            timeout_seconds=20,
        )


def test_failed_full_preflight_is_immutable_and_cannot_finalize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=1)
    receipt = json.loads((output / "receipt.json").read_text())
    assert result["status"] == "FAIL_CLOSED"
    assert receipt["status"] == "FAIL_CLOSED"
    assert receipt["exit_code"] == 1
    assert receipt["timed_out"] is False
    assert receipt["authorizations"] == {
        "formal_campaign_creation_authorized": False,
        "organic_arm_launch_authorized": False,
        "solver_run_authorized": False,
    }

    gate_a_path = tmp_path / "gate-a-should-not-exist.json"
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="not an exact PASS",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-fail",
            target_campaign_dir=tmp_path / "run-fixture-fail",
            run_nonce="run-fixture-fail",
        )
    assert not gate_a_path.exists()
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="no-overwrite",
    ):
        VALIDATION.record_full_preflight(
            authority_root=tmp_path / "drill",
            repository_root=tmp_path / "repository",
            output_dir=output,
        )


def test_successful_full_preflight_finalizes_only_nonauthorizing_gate_a(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=0)
    assert result["status"] == "PASS"
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["schema_version"] == VALIDATION.PREFLIGHT_SCHEMA
    assert receipt["command"] == {
        "argv": [
            receipt["python_identity"]["path"],
            "-I",
            receipt["preflight_script_identity"]["path"],
            "--full",
        ],
        "execution_strategy": VALIDATION.PREFLIGHT_EXECUTION_STRATEGY,
        "loader_identity": VALIDATION._loader_identity(),  # noqa: SLF001
    }
    gate_a_path = tmp_path / "gate-a-pass.json"
    final = VALIDATION.finalize_gate_a(
        authority_root=tmp_path / "drill",
        preflight_receipt=output / "receipt.json",
        output_path=gate_a_path,
        approval_id="gate-a-fixture-pass",
        target_campaign_dir=tmp_path / "run-fixture-pass",
        run_nonce="run-fixture-pass",
    )
    gate_a = final["gate_a"]
    assert final["status"] == "PASS"
    assert gate_a["decision"] == "PASS"
    assert gate_a["offline_candidate_only"] is True
    assert gate_a["arm_launch_authorized"] is False
    assert gate_a["formal_campaign_creation_authorized"] is False
    assert json.loads(gate_a_path.read_text()) == gate_a
    VALIDATION.bootstrap._validate_gate_a(gate_a)  # noqa: SLF001

    with pytest.raises(
        VALIDATION.bootstrap.authority.AuthorityError,
        match="overwrite",
    ) as collision:
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-pass",
            target_campaign_dir=tmp_path / "run-fixture-pass",
            run_nonce="run-fixture-pass",
        )
    assert collision.value.code == "NO_OVERWRITE_COLLISION"


@pytest.mark.parametrize("mutation", ["strategy", "loader", "argv"])
def test_finalize_rejects_preflight_execution_chain_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    output, _, result = _record(tmp_path, monkeypatch, exit_code=0)
    assert result["status"] == "PASS"
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if mutation == "strategy":
        receipt["command"]["execution_strategy"] = "same-fd-python-and-script-compile-exec-v1"
    elif mutation == "loader":
        receipt["command"]["loader_identity"]["sha256"] = "0" * 64
    elif mutation == "argv":
        receipt["command"]["argv"][0] = "/mutable/python3.13"
    else:  # pragma: no cover - the parameter list is static
        raise AssertionError("unreachable mutation")
    receipt_path.chmod(0o644)
    receipt_path.write_bytes(VALIDATION.verifier.canonical_json_bytes(receipt))
    receipt_path.chmod(0o444)

    gate_a_path = tmp_path / f"gate-a-{mutation}.json"
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="tool/command identity drifted",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=receipt_path,
            output_path=gate_a_path,
            approval_id=f"gate-a-fixture-{mutation}",
            target_campaign_dir=tmp_path / f"run-fixture-{mutation}",
            run_nonce=f"run-fixture-{mutation}",
        )
    assert not gate_a_path.exists()


def test_detached_replay_mutation_blocks_finalize_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, detached_replay_path, result = _record(
        tmp_path,
        monkeypatch,
        exit_code=0,
    )
    assert result["status"] == "PASS"
    detached_replay_path.chmod(0o644)
    detached_replay_path.write_bytes(b'{"status":"MUTATED"}')
    detached_replay_path.chmod(0o444)

    gate_a_path = tmp_path / "gate-a-mutation.json"
    with pytest.raises(
        VALIDATION.GateAValidationError,
        match="detached_replay_identity byte identity drifted",
    ):
        VALIDATION.finalize_gate_a(
            authority_root=tmp_path / "drill",
            preflight_receipt=output / "receipt.json",
            output_path=gate_a_path,
            approval_id="gate-a-fixture-mutation",
            target_campaign_dir=tmp_path / "run-fixture-mutation",
            run_nonce="run-fixture-mutation",
        )
    assert not gate_a_path.exists()
