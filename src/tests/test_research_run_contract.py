from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from devtools import research_run_contract as research_contract
from devtools.research_run_contract import (
    ARTIFACT_ROOT_MANIFEST_SCHEMA,
    ArtifactIdentity,
    ExclusiveRunRoot,
    ResearchRunContractError,
    build_artifact_root_manifest,
    canonical_json_bytes,
    make_research_run_config,
    make_research_run_receipt,
    read_stable_snapshot,
    replay_identity_graph,
    run_isolated_replay,
    validate_artifact_root_manifest,
    validate_research_run_config,
    validate_research_run_receipt,
    verify_artifact_root_closure,
)


def _error_code(exc_info: pytest.ExceptionInfo[ResearchRunContractError]) -> str:
    return exc_info.value.code


def _open_fd_count() -> int:
    proc_fd = Path("/proc/self/fd")
    if not proc_fd.is_dir():
        pytest.skip("/proc/self/fd is required for descriptor-leak assertions")
    return len(os.listdir(proc_fd))


def test_canonical_json_bytes_is_utf8_sorted_compact_and_lf_terminated() -> None:
    value = {"z": [None, True, 3], "a": "雪"}
    assert canonical_json_bytes(value) == '{"a":"雪","z":[null,true,3]}\n'.encode()


@pytest.mark.parametrize(
    "value",
    [
        1.0,
        {"value": 1.0},
        {1: "not a string key"},
        ("tuple",),
        b"bytes",
    ],
)
def test_canonical_json_bytes_rejects_values_outside_small_json_domain(value: object) -> None:
    with pytest.raises(ResearchRunContractError) as exc_info:
        canonical_json_bytes(value)
    assert _error_code(exc_info) == "NON_JSON_VALUE"


def test_read_stable_snapshot_binds_actual_bytes_and_expectations(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"actual bytes\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    snapshot = read_stable_snapshot(
        source,
        expected_sha256=digest,
        expected_size_bytes=13,
        max_bytes=13,
    )

    assert snapshot.data == b"actual bytes\n"
    assert snapshot.sha256 == digest
    assert snapshot.size_bytes == 13
    assert snapshot.identity.path == str(source)


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"expected_sha256": "0" * 64}, "SHA256_MISMATCH"),
        ({"expected_size_bytes": 2}, "SIZE_MISMATCH"),
        ({"max_bytes": 2}, "INPUT_TOO_LARGE"),
    ],
)
def test_read_stable_snapshot_rejects_identity_mismatch(
    tmp_path: Path,
    kwargs: dict[str, object],
    code: str,
) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"abc")
    with pytest.raises(ResearchRunContractError) as exc_info:
        read_stable_snapshot(source, **kwargs)
    assert _error_code(exc_info) == code


def test_read_stable_snapshot_rejects_non_regular_and_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"x")
    link = tmp_path / "link"
    link.symlink_to(target)

    with pytest.raises(ResearchRunContractError) as symlink_exc:
        read_stable_snapshot(link)
    assert _error_code(symlink_exc) == "SYMLINK_REJECTED"

    with pytest.raises(ResearchRunContractError) as directory_exc:
        read_stable_snapshot(tmp_path)
    assert _error_code(directory_exc) == "NON_REGULAR_INPUT"


def test_read_stable_snapshot_detects_same_fd_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"abc")
    original_fstat = os.fstat
    calls = 0

    def drifting_fstat(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        result = original_fstat(descriptor)
        if calls == 2:
            source.write_bytes(b"xyz")
            result = original_fstat(descriptor)
        return result

    monkeypatch.setattr(os, "fstat", drifting_fstat)
    with pytest.raises(ResearchRunContractError) as exc_info:
        read_stable_snapshot(source)
    assert _error_code(exc_info) == "INPUT_CHANGED"


def test_exclusive_run_root_creates_scoped_artifacts_without_overwrite(tmp_path: Path) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    inputs = root.mkdir("inputs")
    assert inputs == tmp_path / "run" / "inputs"

    identity = root.write_json("inputs/config.json", {"b": 2, "a": 1})
    assert Path(identity.path).read_bytes() == b'{"a":1,"b":2}\n'
    assert identity.sha256 == hashlib.sha256(b'{"a":1,"b":2}\n').hexdigest()

    with pytest.raises(ResearchRunContractError) as file_exc:
        root.write_bytes("inputs/config.json", b"replacement")
    assert _error_code(file_exc) == "NO_OVERWRITE_COLLISION"

    with pytest.raises(ResearchRunContractError) as directory_exc:
        root.mkdir("inputs")
    assert _error_code(directory_exc) == "NO_OVERWRITE_COLLISION"

    with pytest.raises(ResearchRunContractError) as root_exc:
        ExclusiveRunRoot.create(tmp_path / "run")
    assert _error_code(root_exc) == "NO_OVERWRITE_COLLISION"


def test_exclusive_run_root_has_one_winner_under_concurrent_create(tmp_path: Path) -> None:
    path = tmp_path / "run"

    def create() -> str:
        try:
            ExclusiveRunRoot.create(path)
        except ResearchRunContractError as exc:
            return exc.code
        return "CREATED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _index: create(), range(2)))
    assert outcomes == ["CREATED", "NO_OVERWRITE_COLLISION"]


@pytest.mark.parametrize("relative", ["../escape", "/absolute", "a/../../escape", "."])
def test_exclusive_run_root_rejects_path_escape(tmp_path: Path, relative: str) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    with pytest.raises(ResearchRunContractError) as exc_info:
        root.write_bytes(relative, b"x")
    assert _error_code(exc_info) == "PATH_ESCAPE"


def test_exclusive_run_root_rejects_symlink_parent(tmp_path: Path) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root.path / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ResearchRunContractError) as exc_info:
        root.write_bytes("linked/escape", b"x")
    assert _error_code(exc_info) == "OUTPUT_PARENT_INVALID"
    assert not (outside / "escape").exists()


def test_exclusive_run_root_detects_replaced_root(tmp_path: Path) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    root.path.rename(tmp_path / "old-run")
    root.path.mkdir()

    with pytest.raises(ResearchRunContractError) as exc_info:
        root.write_bytes("artifact", b"x")
    assert _error_code(exc_info) == "RUN_ROOT_IDENTITY_DRIFT"


def test_exclusive_run_root_fstat_failure_is_stable_and_fd_neutral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    original_fstat = os.fstat
    calls = 0

    def failing_fstat(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        raise OSError(errno.EIO, "injected run-root fstat failure")

    before = _open_fd_count()
    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", failing_fstat)
        with pytest.raises(ResearchRunContractError) as exc_info:
            root._open_root()
    after = _open_fd_count()

    assert calls == 1
    assert _error_code(exc_info) == "RUN_ROOT_OPEN_FAILED"
    assert after - before == 0
    assert original_fstat is os.fstat


@pytest.mark.parametrize(
    ("root_form", "failing_call"),
    [("path", 1), ("exclusive_run_root", 2)],
)
def test_artifact_root_fstat_failure_is_stable_and_fd_neutral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    root_form: str,
    failing_call: int,
) -> None:
    root = ExclusiveRunRoot.create(tmp_path / root_form)
    root.write_json("config.json", {"schema": "fixture"})
    root_argument: ExclusiveRunRoot | Path = (
        root if root_form == "exclusive_run_root" else root.path
    )
    original_fstat = os.fstat
    calls = 0

    def failing_fstat(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == failing_call:
            raise OSError(errno.EIO, "injected artifact-root fstat failure")
        return original_fstat(descriptor)

    before = _open_fd_count()
    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", failing_fstat)
        with pytest.raises(ResearchRunContractError) as exc_info:
            build_artifact_root_manifest(root_argument)
    after = _open_fd_count()

    assert calls == failing_call
    assert _error_code(exc_info) == "ARTIFACT_ROOT_OPEN_FAILED"
    assert after - before == 0


def test_common_root_open_paths_are_fd_neutral_under_repetition(
    tmp_path: Path,
) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    root.write_json("config.json", {"schema": "fixture"})
    manifest = build_artifact_root_manifest(root)

    before = _open_fd_count()
    for _iteration in range(32):
        descriptor = root._open_root()
        os.close(descriptor)
        assert build_artifact_root_manifest(root.path) == manifest
        assert build_artifact_root_manifest(root) == manifest
        verify_artifact_root_closure(root.path, manifest, receipt_present=False)
        verify_artifact_root_closure(root, manifest, receipt_present=False)
    after = _open_fd_count()

    assert after - before == 0


def test_common_post_open_validation_failures_are_fd_neutral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[tuple[str, int]] = []

    signature_root = ExclusiveRunRoot.create(tmp_path / "root-signature")
    original_signature = research_contract._stat_signature

    def failing_root_signature(_item: os.stat_result) -> tuple[int, ...]:
        raise RuntimeError("injected root signature failure")

    before = _open_fd_count()
    with monkeypatch.context() as patch:
        patch.setattr(
            research_contract,
            "_stat_signature",
            failing_root_signature,
        )
        with pytest.raises(RuntimeError, match="injected root signature failure"):
            build_artifact_root_manifest(signature_root.path)
    observations.append(("root_signature", _open_fd_count() - before))

    capability_root = ExclusiveRunRoot.create(tmp_path / "capability")
    original_directory_flags = research_contract._directory_open_flags
    capability_calls = 0

    def failing_second_capability_check() -> int:
        nonlocal capability_calls
        capability_calls += 1
        if capability_calls == 2:
            raise ResearchRunContractError(
                "INJECTED_CAPABILITY_FAILURE",
                "injected post-open capability failure",
            )
        return original_directory_flags()

    before = _open_fd_count()
    with monkeypatch.context() as patch:
        patch.setattr(
            research_contract,
            "_directory_open_flags",
            failing_second_capability_check,
        )
        with pytest.raises(ResearchRunContractError) as capability_exc:
            build_artifact_root_manifest(capability_root.path)
    assert _error_code(capability_exc) == "INJECTED_CAPABILITY_FAILURE"
    assert capability_calls == 2
    observations.append(("second_capability_check", _open_fd_count() - before))

    child_root = ExclusiveRunRoot.create(tmp_path / "child-signature")
    child_root.mkdir("child")
    signature_calls = 0
    child_faults = 0

    def failing_child_signature(item: os.stat_result) -> tuple[int, ...]:
        nonlocal child_faults, signature_calls
        signature_calls += 1
        if child_faults == 0 and signature_calls == 2:
            child_faults += 1
            raise RuntimeError("injected child signature failure")
        return original_signature(item)

    before = _open_fd_count()
    with monkeypatch.context() as patch:
        patch.setattr(
            research_contract,
            "_stat_signature",
            failing_child_signature,
        )
        with pytest.raises(RuntimeError, match="injected child signature failure"):
            build_artifact_root_manifest(child_root.path)
    assert child_faults == 1
    assert signature_calls >= 2
    observations.append(("child_signature", _open_fd_count() - before))

    assert observations == [
        ("root_signature", 0),
        ("second_capability_check", 0),
        ("child_signature", 0),
    ]


def test_artifact_root_manifest_has_unambiguous_pre_and_completed_states(
    tmp_path: Path,
) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    root.mkdir("inputs")
    root.write_bytes("inputs/source.bin", b"source")
    root.mkdir("empty")
    root.write_json("config.json", {"schema": "fixture"})

    manifest = build_artifact_root_manifest(root)

    assert manifest == {
        "schema": ARTIFACT_ROOT_MANIFEST_SCHEMA,
        "entries": [
            {"path": "config.json", "type": "regular_file"},
            {"path": "empty", "type": "directory"},
            {"path": "inputs", "type": "directory"},
            {"path": "inputs/source.bin", "type": "regular_file"},
        ],
    }
    verify_artifact_root_closure(root, manifest, receipt_present=False)
    root.write_json("receipt.json", {"schema": "fixture_receipt"})
    verify_artifact_root_closure(root, manifest, receipt_present=True)


@pytest.mark.parametrize(
    "path",
    [
        "receipt.json",
        "receipt.json/descendant",
        "../escape",
        "/absolute",
        "nested/../escape",
        "windows\\separator",
    ],
)
def test_artifact_root_manifest_rejects_reserved_or_escaping_paths(path: str) -> None:
    manifest = {
        "schema": ARTIFACT_ROOT_MANIFEST_SCHEMA,
        "entries": [{"path": path, "type": "regular_file"}],
    }
    with pytest.raises(ResearchRunContractError) as exc_info:
        validate_artifact_root_manifest(manifest)
    assert _error_code(exc_info) in {
        "ARTIFACT_ROOT_MANIFEST_INVALID",
        "ARTIFACT_ROOT_PATH_ESCAPE",
        "ARTIFACT_ROOT_RECEIPT_RESERVED",
    }


def test_artifact_root_manifest_rejects_unsorted_duplicate_and_missing_parent() -> None:
    invalid_entries = (
        [
            {"path": "z", "type": "regular_file"},
            {"path": "a", "type": "regular_file"},
        ],
        [
            {"path": "same", "type": "regular_file"},
            {"path": "same", "type": "regular_file"},
        ],
        [{"path": "missing/child", "type": "regular_file"}],
    )
    for entries in invalid_entries:
        with pytest.raises(ResearchRunContractError) as exc_info:
            validate_artifact_root_manifest(
                {
                    "schema": ARTIFACT_ROOT_MANIFEST_SCHEMA,
                    "entries": entries,
                }
            )
        assert _error_code(exc_info) == "ARTIFACT_ROOT_MANIFEST_INVALID"


@pytest.mark.parametrize("pollution_kind", ["file", "directory", "symlink", "fifo"])
def test_artifact_root_closure_rejects_every_unregistered_node_type(
    tmp_path: Path,
    pollution_kind: str,
) -> None:
    root = ExclusiveRunRoot.create(tmp_path / "run")
    root.write_bytes("registered", b"bound")
    manifest = build_artifact_root_manifest(root)
    pollution = root.path / "unregistered"
    if pollution_kind == "file":
        pollution.write_bytes(b"extra")
    elif pollution_kind == "directory":
        pollution.mkdir()
    elif pollution_kind == "symlink":
        pollution.symlink_to(root.path / "registered")
    else:
        os.mkfifo(pollution)

    with pytest.raises(ResearchRunContractError) as exc_info:
        verify_artifact_root_closure(root, manifest, receipt_present=False)

    expected = {
        "file": "ARTIFACT_ROOT_CLOSURE_MISMATCH",
        "directory": "ARTIFACT_ROOT_CLOSURE_MISMATCH",
        "symlink": "ARTIFACT_ROOT_SYMLINK_REJECTED",
        "fifo": "ARTIFACT_ROOT_SPECIAL_NODE_REJECTED",
    }
    assert _error_code(exc_info) == expected[pollution_kind]


def test_artifact_root_completed_state_requires_one_regular_terminal_receipt(
    tmp_path: Path,
) -> None:
    missing_root = ExclusiveRunRoot.create(tmp_path / "missing")
    manifest = build_artifact_root_manifest(missing_root)
    with pytest.raises(ResearchRunContractError) as missing_exc:
        verify_artifact_root_closure(missing_root, manifest, receipt_present=True)
    assert _error_code(missing_exc) == "ARTIFACT_ROOT_CLOSURE_MISMATCH"

    directory_root = ExclusiveRunRoot.create(tmp_path / "directory")
    directory_manifest = build_artifact_root_manifest(directory_root)
    directory_root.mkdir("receipt.json")
    with pytest.raises(ResearchRunContractError) as directory_exc:
        verify_artifact_root_closure(
            directory_root,
            directory_manifest,
            receipt_present=True,
        )
    assert _error_code(directory_exc) == "ARTIFACT_ROOT_CLOSURE_MISMATCH"

    symlink_root = ExclusiveRunRoot.create(tmp_path / "symlink")
    symlink_manifest = build_artifact_root_manifest(symlink_root)
    (symlink_root.path / "receipt.json").symlink_to(tmp_path / "missing-target")
    with pytest.raises(ResearchRunContractError) as symlink_exc:
        verify_artifact_root_closure(
            symlink_root,
            symlink_manifest,
            receipt_present=True,
        )
    assert _error_code(symlink_exc) == "ARTIFACT_ROOT_SYMLINK_REJECTED"


@pytest.mark.parametrize("operation", ["build", "verify"])
@pytest.mark.parametrize(
    "pollution_kind",
    ["regular_file", "directory", "symlink", "fifo", "pyc"],
)
def test_artifact_root_walker_rejects_persistent_late_mutation_in_completed_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    pollution_kind: str,
) -> None:
    root = ExclusiveRunRoot.create(tmp_path / f"{operation}-{pollution_kind}")
    root.mkdir("a_early")
    root.write_bytes("a_early/registered", b"bound")
    root.mkdir("z_trigger")
    manifest = (
        build_artifact_root_manifest(root)
        if operation == "verify"
        else None
    )
    early = root.path / "a_early"
    pollution = early / (
        "late.cpython-999.pyc" if pollution_kind == "pyc" else "late"
    )
    original_open = os.open
    injected = False

    def injecting_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal injected
        if not injected and path == "z_trigger" and dir_fd is not None:
            injected = True
            if pollution_kind in {"regular_file", "pyc"}:
                pollution.write_bytes(b"persistent late pollution")
            elif pollution_kind == "directory":
                pollution.mkdir()
            elif pollution_kind == "symlink":
                pollution.symlink_to(early / "registered")
            else:
                os.mkfifo(pollution)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", injecting_open)

    with pytest.raises(ResearchRunContractError):
        if operation == "build":
            build_artifact_root_manifest(root)
        else:
            assert manifest is not None
            verify_artifact_root_closure(
                root,
                manifest,
                receipt_present=False,
            )

    assert injected
    assert os.path.lexists(pollution)


def test_artifact_root_builder_rejects_ancestor_symlink_swap_between_check_and_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked_parent = tmp_path / "checked-parent"
    checked_parent.mkdir()
    requested_root = checked_parent / "run"
    requested_root.mkdir()
    (requested_root / "inside").write_bytes(b"checked tree")

    outside_parent = tmp_path / "outside-parent"
    outside_parent.mkdir()
    outside_root = outside_parent / "run"
    outside_root.mkdir()
    (outside_root / "outside").write_bytes(b"must not be enumerated")

    displaced_parent = tmp_path / "checked-parent-before-swap"
    original_open = os.open
    swapped = False

    def swapping_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if (
            not swapped
            and (
                (
                    dir_fd is None
                    and os.path.abspath(os.fspath(path)) == str(requested_root)
                )
                or (
                    dir_fd is not None
                    and os.fspath(path) == checked_parent.name
                )
            )
        ):
            checked_parent.rename(displaced_parent)
            checked_parent.symlink_to(outside_parent, target_is_directory=True)
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)

    with pytest.raises(ResearchRunContractError):
        build_artifact_root_manifest(requested_root)

    assert swapped
    assert checked_parent.is_symlink()
    assert (displaced_parent / "run" / "inside").read_bytes() == b"checked tree"
    assert (outside_root / "outside").read_bytes() == b"must not be enumerated"


def test_config_and_receipt_envelopes_leave_payload_opaque(tmp_path: Path) -> None:
    config = make_research_run_config(
        experiment_id="example",
        payload={"experiment_owned": ["meaning", 7]},
    )
    assert validate_research_run_config(config) == config

    config_path = tmp_path / "config.json"
    config_path.write_bytes(canonical_json_bytes(config))
    config_identity = read_stable_snapshot(config_path).identity
    artifact_path = tmp_path / "artifact.bin"
    artifact_path.write_bytes(b"result")
    artifact_identity = read_stable_snapshot(artifact_path).identity
    receipt = make_research_run_receipt(
        experiment_id="example",
        config_identity=config_identity,
        artifacts={"result": artifact_identity},
        payload={"status_word": "experiment-defined"},
    )
    assert validate_research_run_receipt(receipt) == receipt


def test_envelope_validators_reject_extra_common_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "config"
    config_path.write_bytes(b"x")
    identity = read_stable_snapshot(config_path).identity
    config = make_research_run_config(experiment_id="example", payload={})
    config["unexpected"] = None
    receipt = make_research_run_receipt(
        experiment_id="example",
        config_identity=identity,
        artifacts={},
        payload={},
    )
    receipt["unexpected"] = None

    with pytest.raises(ResearchRunContractError) as config_exc:
        validate_research_run_config(config)
    assert _error_code(config_exc) == "CONFIG_ENVELOPE_INVALID"
    with pytest.raises(ResearchRunContractError) as receipt_exc:
        validate_research_run_receipt(receipt)
    assert _error_code(receipt_exc) == "RECEIPT_ENVELOPE_INVALID"


def test_replay_identity_graph_verifies_bytes_and_hashes_canonical_graph(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    identities = {
        "second": read_stable_snapshot(second).identity,
        "first": read_stable_snapshot(first).identity,
    }

    replay = replay_identity_graph(identities)

    assert replay.snapshots["first"].data == b"one"
    graph_without_digest = {
        "schema": "artifact_identity_graph_v1",
        "artifacts": {
            label: identities[label].as_dict()
            for label in sorted(identities)
        },
    }
    assert replay.graph_sha256 == hashlib.sha256(
        canonical_json_bytes(graph_without_digest)
    ).hexdigest()

    first.write_bytes(b"tampered")
    with pytest.raises(ResearchRunContractError) as exc_info:
        replay_identity_graph(identities)
    assert _error_code(exc_info) in {"SHA256_MISMATCH", "SIZE_MISMATCH"}


def test_run_isolated_replay_uses_dash_i_and_exact_environment(tmp_path: Path) -> None:
    imported = tmp_path / "copied_gate.py"
    imported.write_text("VALUE = 7\n", encoding="utf-8")
    script = tmp_path / "replay.py"
    script.write_text(
        "import importlib.util, json, os, sys\n"
        "spec = importlib.util.spec_from_file_location('_copied_gate', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "print(json.dumps({'isolated': sys.flags.isolated, "
        "'ignore_environment': sys.flags.ignore_environment, "
        "'dont_write_bytecode': sys.flags.dont_write_bytecode, "
        "'runtime_dont_write_bytecode': sys.dont_write_bytecode, "
        "'pythonpath': os.environ.get('PYTHONPATH'), "
        "'pythonhome': os.environ.get('PYTHONHOME'), "
        "'token': os.environ.get('REPLAY_TOKEN'), "
        "'imported_value': module.VALUE, "
        "'stdin': sys.stdin.buffer.read().decode()}))\n",
        encoding="utf-8",
    )

    observation = run_isolated_replay(
        script,
        arguments=(str(imported),),
        environment={"REPLAY_TOKEN": "bound"},
        timeout_seconds=10,
    )

    assert observation.returncode == 0
    assert observation.timed_out is False
    assert observation.argv[1:3] == ("-I", "-B")
    assert observation.stderr == b""
    output = json.loads(observation.stdout)
    assert output == {
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "imported_value": 7,
        "isolated": 1,
        "pythonpath": None,
        "pythonhome": None,
        "runtime_dont_write_bytecode": True,
        "stdin": "",
        "token": "bound",
    }
    assert list(tmp_path.rglob("__pycache__")) == []
    assert list(tmp_path.rglob("*.pyc")) == []


def test_isolated_process_contract_rejects_environment_only_bytecode_suppression(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = tmp_path / "contract_probe.py"
    script.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(project_root)!r})\n"
        "from devtools.research_run_contract import "
        "ResearchRunContractError, require_isolated_python_process\n"
        "try:\n"
        "    require_isolated_python_process()\n"
        "except ResearchRunContractError as exc:\n"
        "    print(json.dumps({'code': exc.code}))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(9)\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(script)],
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "code": "PYTHON_PROCESS_CONTRACT_INVALID"
    }
    assert list(tmp_path.rglob("__pycache__")) == []


def test_isolated_process_contract_accepts_dash_i_dash_b(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = tmp_path / "contract_probe.py"
    script.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(project_root)!r})\n"
        "from devtools.research_run_contract import require_isolated_python_process\n"
        "print(json.dumps(require_isolated_python_process(), sort_keys=True))\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(script)],
        env={},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    contract = json.loads(completed.stdout)
    assert contract["required_argv_flags"] == ["-I", "-B"]
    assert contract["observed"] == {
        "isolated": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
        "dont_write_bytecode_flag": 1,
        "dont_write_bytecode_runtime": True,
    }
    assert list(tmp_path.rglob("__pycache__")) == []


@pytest.mark.parametrize("forbidden", ["PYTHONPATH", "PYTHONHOME"])
def test_run_isolated_replay_rejects_python_path_environment(
    tmp_path: Path,
    forbidden: str,
) -> None:
    script = tmp_path / "replay.py"
    script.write_text("", encoding="utf-8")
    with pytest.raises(ResearchRunContractError) as exc_info:
        run_isolated_replay(script, environment={forbidden: "unsafe"})
    assert _error_code(exc_info) == "REPLAY_ENVIRONMENT_INVALID"


@pytest.mark.parametrize("timeout", [0, -1, math.inf, math.nan])
def test_run_isolated_replay_rejects_invalid_timeout(tmp_path: Path, timeout: float) -> None:
    script = tmp_path / "replay.py"
    script.write_text("", encoding="utf-8")
    with pytest.raises(ResearchRunContractError) as exc_info:
        run_isolated_replay(script, timeout_seconds=timeout)
    assert _error_code(exc_info) == "REPLAY_TIMEOUT_INVALID"


def test_run_isolated_replay_preserves_raw_nonzero_observation(tmp_path: Path) -> None:
    script = tmp_path / "replay.py"
    script.write_text(
        "import sys\nsys.stdout.buffer.write(b'out')\nsys.stderr.buffer.write(b'err')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    observation = run_isolated_replay(script)
    assert observation.returncode == 7
    assert observation.timed_out is False
    assert observation.stdout == b"out"
    assert observation.stderr == b"err"
