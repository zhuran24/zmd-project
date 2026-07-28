from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from devtools.research_run_contract import (
    ArtifactIdentity,
    ExclusiveRunRoot,
    ResearchRunContractError,
    canonical_json_bytes,
    make_research_run_config,
    make_research_run_receipt,
    read_stable_snapshot,
    replay_identity_graph,
    run_isolated_replay,
    validate_research_run_config,
    validate_research_run_receipt,
)


def _error_code(exc_info: pytest.ExceptionInfo[ResearchRunContractError]) -> str:
    return exc_info.value.code


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
    script = tmp_path / "replay.py"
    script.write_text(
        "import json, os, sys\n"
        "print(json.dumps({'isolated': sys.flags.isolated, "
        "'pythonpath': os.environ.get('PYTHONPATH'), "
        "'pythonhome': os.environ.get('PYTHONHOME'), "
        "'token': os.environ.get('REPLAY_TOKEN')}))\n",
        encoding="utf-8",
    )

    observation = run_isolated_replay(
        script,
        environment={"REPLAY_TOKEN": "bound"},
        timeout_seconds=10,
    )

    assert observation.returncode == 0
    assert observation.timed_out is False
    assert observation.argv[1] == "-I"
    assert observation.stderr == b""
    output = json.loads(observation.stdout)
    assert output == {
        "isolated": 1,
        "pythonpath": None,
        "pythonhome": None,
        "token": "bound",
    }


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
