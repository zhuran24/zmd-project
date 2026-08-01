from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PRODUCER = _load(
    "noncert_cuts_ab16_gate_a_recovery_inputs_v1_tested",
    TOOLS / "gate_a_recovery_inputs_v1.py",
)
DRILL = _load(
    "noncert_cuts_ab16_disposable_drill_authority_v2_path_map_tested",
    TOOLS / "disposable_drill_authority_v2.py",
)
PINNED = _load(
    "noncert_cuts_ab16_gate_a_pinned_entrypoint_v2_path_map_tested",
    TOOLS / "gate_a_pinned_entrypoint_v2.py",
)


def _file(path: Path, raw: bytes = b"fixture\n", *, executable: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    if executable:
        path.chmod(0o755)
    return path


def _cli_fixture(tmp_path: Path) -> tuple[list[str], dict[str, str], dict[str, str]]:
    repository = tmp_path / "repository"
    strict = {
        "candidate_placements": str(_file(repository / "data/preprocessed/candidate_placements.json")),
        "canonical_rules": str(_file(repository / "rules/canonical_rules.json")),
        "cuts_mandatory_schedule": str(_file(tmp_path / "external/cuts-schedule.md")),
        "history_freeze_manifest": str(_file(tmp_path / "external/history.json")),
        "legacy_control_a002": str(_file(tmp_path / "external/control-a002.json")),
        "mandatory_instances": str(_file(repository / "data/preprocessed/mandatory_exact_instances.json")),
        "preflight_gate": str(_file(repository / "scripts/preflight_gate.py")),
        "project_lock": str(_file(repository / "PROJECT_LOCK.md")),
    }
    system_paths = {
        role: _file(tmp_path / "system" / role, executable=role != "libsystemd")
        for role in sorted(PRODUCER.bootstrap.SYSTEM_TOOL_ROLES)
    }
    system = {role: str(path) for role, path in system_paths.items()}
    output = tmp_path / "gate-a-sibling-recovery"
    command = [
        sys.executable,
        "-I",
        "-B",
        str(TOOLS / "gate_a_recovery_inputs_v1.py"),
        "--output-dir",
        str(output),
        "--repository-root",
        str(repository),
        "--history-freeze-manifest",
        strict["history_freeze_manifest"],
        "--cuts-mandatory-schedule",
        strict["cuts_mandatory_schedule"],
        "--legacy-control-a002",
        strict["legacy_control_a002"],
        "--attestor-python",
        system["attestor_python"],
        "--python3-13",
        system["python3_13"],
        "--busctl",
        system["busctl"],
        "--git",
        system["git"],
        "--libsystemd",
        system["libsystemd"],
        "--sudo",
        system["sudo"],
        "--systemctl",
        system["systemctl"],
        "--systemd-run",
        system["systemd_run"],
    ]
    return command, strict, system


def _bytecode_cache_snapshot() -> tuple[tuple[str, str], ...]:
    cache = TOOLS / "__pycache__"
    if cache.is_symlink():
        return (("__pycache__", f"symlink:{os.readlink(cache)}"),)
    if not cache.exists():
        return ()
    rows: list[tuple[str, str]] = []
    for path in sorted((cache, *cache.rglob("*"))):
        relative = path.relative_to(TOOLS).as_posix()
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            rows.append((relative, f"symlink:{os.readlink(path)}"))
        elif stat.S_ISDIR(metadata.st_mode):
            rows.append((relative, "directory"))
        elif stat.S_ISREG(metadata.st_mode):
            rows.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
        else:
            rows.append((relative, f"special:{stat.S_IFMT(metadata.st_mode):o}"))
    return tuple(rows)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def test_real_cli_publishes_exact_canonical_path_maps_and_observation(
    tmp_path: Path,
) -> None:
    command, expected_strict, expected_system = _cli_fixture(tmp_path)
    assert command[:4] == [
        sys.executable,
        "-I",
        "-B",
        str(TOOLS / "gate_a_recovery_inputs_v1.py"),
    ]
    bytecode_before = _bytecode_cache_snapshot()
    completed = subprocess.run(command, check=False, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode()
    assert _bytecode_cache_snapshot() == bytecode_before

    recovery = tmp_path / "gate-a-sibling-recovery"
    output = recovery / "input-authority-a001"
    strict_raw = (output / "strict-inputs.json").read_bytes()
    system_raw = (output / "system-tools.json").read_bytes()
    observation_raw = (output / "planned-source-observation.json").read_bytes()
    observation = json.loads(observation_raw)

    assert strict_raw == _canonical(expected_strict)
    assert system_raw == _canonical(expected_system)
    assert observation_raw == _canonical(observation)
    assert not strict_raw.endswith(b"\n")
    assert not system_raw.endswith(b"\n")
    assert not observation_raw.endswith(b"\n")
    assert set(path.name for path in output.iterdir()) == {
        "planned-source-observation.json",
        "strict-inputs.json",
        "system-tools.json",
    }
    assert list(recovery.iterdir()) == [output]

    result = json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["authorizations"] == {
        "arm_launch_authorized": False,
        "formal_campaign_creation_authorized": False,
        "solver_run_authorized": False,
    }
    assert result["planned_source_count"] == len(observation["planned_source_identities"])
    assert result["recovery_dir"] == str(recovery)
    assert result["input_authority_dir"] == str(output)
    assert "script.gate_a_recovery_inputs_v1" in observation["planned_source_identities"]
    for filename, field in (
        ("strict-inputs.json", "strict_inputs_identity"),
        ("system-tools.json", "system_tools_identity"),
        (
            "planned-source-observation.json",
            "planned_source_observation_identity",
        ),
    ):
        raw = (output / filename).read_bytes()
        assert result[field] == {
            "mode": 0o444,
            "path": str(output / filename),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

    assert DRILL._strict_path_map(  # noqa: SLF001
        output / "strict-inputs.json",
        "strict input path map",
    ) == {role: Path(path) for role, path in expected_strict.items()}
    assert DRILL._strict_path_map(  # noqa: SLF001
        output / "system-tools.json",
        "system tool path map",
    ) == {role: Path(path) for role, path in expected_system.items()}
    assert (
        PINNED._planned_sources(  # noqa: SLF001
            observation_raw,
            expected_set_digest=observation["planned_source_set_digest"],
        )
        == observation["planned_source_identities"]
    )

    trailing = tmp_path / "strict-inputs-with-lf.json"
    trailing.write_bytes(strict_raw + b"\n")
    with pytest.raises(Exception, match="not canonical JSON"):
        DRILL._strict_path_map(trailing, "strict input path map")  # noqa: SLF001
    with pytest.raises(Exception, match="not canonical strict JSON"):
        PINNED._planned_sources(  # noqa: SLF001
            observation_raw + b"\n",
            expected_set_digest=observation["planned_source_set_digest"],
        )
    whitespace = tmp_path / "strict-inputs-with-leading-space.json"
    whitespace.write_bytes(b" " + strict_raw)
    with pytest.raises(Exception, match="not canonical JSON"):
        DRILL._strict_path_map(whitespace, "strict input path map")  # noqa: SLF001
    duplicate = tmp_path / "strict-inputs-with-duplicate-key.json"
    first_role, first_path = next(iter(expected_strict.items()))
    duplicate.write_bytes(
        ("{" + json.dumps(first_role) + ":" + json.dumps(first_path) + "," + strict_raw.decode()[1:]).encode()
    )
    with pytest.raises(Exception, match=r"duplicate (JSON )?key"):
        DRILL._strict_path_map(duplicate, "strict input path map")  # noqa: SLF001

    assert PRODUCER.lifecycle.canonical_json_bytes({"domain": "path-map"}) == (b'{"domain":"path-map"}')
    assert (
        PRODUCER.bootstrap.authority.canonical_json({"domain": "path-preregistration"})
        == b'{"domain":"path-preregistration"}\n'
    )

    DRILL._reobserve_sources(  # noqa: SLF001
        strict_input_paths=expected_strict,
        system_tool_paths=expected_system,
        expected=observation["planned_source_identities"],
        expected_digest=observation["planned_source_set_digest"],
    )
    Path(expected_strict["canonical_rules"]).write_bytes(b"mutated fixture\n")
    with pytest.raises(Exception, match="drifted"):
        DRILL._reobserve_sources(  # noqa: SLF001
            strict_input_paths=expected_strict,
            system_tool_paths=expected_system,
            expected=observation["planned_source_identities"],
            expected_digest=observation["planned_source_set_digest"],
        )


def test_real_cli_is_no_overwrite(tmp_path: Path) -> None:
    command, _strict, _system = _cli_fixture(tmp_path)
    first = subprocess.run(command, check=False, capture_output=True)
    assert first.returncode == 0, first.stderr.decode()
    output = tmp_path / "gate-a-sibling-recovery/input-authority-a001"
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}

    second = subprocess.run(command, check=False, capture_output=True)
    assert second.returncode == 2
    failure = json.loads(second.stderr)
    assert failure["status"] == "FAIL_CLOSED"
    assert "already exists" in failure["detail"]
    assert before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}


def test_real_cli_rejects_symlinked_output_parent(tmp_path: Path) -> None:
    command, _strict, _system = _cli_fixture(tmp_path)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    output_index = command.index("--output-dir") + 1
    command[output_index] = str(linked_parent / "gate-a-sibling-recovery")

    completed = subprocess.run(command, check=False, capture_output=True)
    assert completed.returncode == 2
    assert json.loads(completed.stderr)["status"] == "FAIL_CLOSED"
    assert list(real_parent.iterdir()) == []


def test_publish_rejects_role_drift_before_consuming_directory(
    tmp_path: Path,
) -> None:
    _command, strict, system = _cli_fixture(tmp_path)
    strict.pop("candidate_placements")
    output = tmp_path / "role-drift"
    with pytest.raises(
        PRODUCER.RecoveryInputError,
        match="exact registered roles",
    ):
        PRODUCER.publish_recovery_inputs(
            output_dir=output,
            strict_input_paths=strict,
            system_tool_paths=system,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    ("target", "mutation"),
    (
        ("strict", "extra_role"),
        ("strict", "non_string_role"),
        ("strict", "non_path_value"),
        ("system", "missing_role"),
        ("system", "extra_role"),
        ("system", "non_path_value"),
    ),
)
def test_publish_rejects_exact_map_schema_drift_before_output(
    tmp_path: Path,
    target: str,
    mutation: str,
) -> None:
    _command, strict, system = _cli_fixture(tmp_path)
    selected: object = strict if target == "strict" else system
    assert type(selected) is dict
    if mutation == "missing_role":
        selected.pop(next(iter(selected)))
    elif mutation == "extra_role":
        selected["unexpected"] = str(tmp_path / "unexpected")
    elif mutation == "non_string_role":
        selected[7] = selected.pop(next(iter(selected)))  # type: ignore[index]
    elif mutation == "non_path_value":
        selected[next(iter(selected))] = True
    else:
        raise AssertionError("unknown mutation")

    output = tmp_path / f"{target}-{mutation}"
    with pytest.raises(PRODUCER.RecoveryInputError):
        PRODUCER.publish_recovery_inputs(
            output_dir=output,
            strict_input_paths=strict,
            system_tool_paths=system,
        )
    assert not output.exists()
