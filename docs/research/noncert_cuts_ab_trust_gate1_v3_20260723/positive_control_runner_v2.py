#!/usr/bin/env python3
"""Library-only contract for future pre-injection binary authority export.

The helper never constructs or runs a solver.  A future paired arm may call
``export_binary_prestate`` after it already has a model and retained response
text.  The arm selector is mandatory so an accidental standalone invocation
cannot create evidence outside a registered paired launch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Mapping, Protocol

from google.protobuf import text_format
from ortools.sat import cp_model_pb2


_ARMS = frozenset({"control", "treatment"})
_SELECTION_SCHEMA = "noncert-cuts-gate1-launch-selection-v3"
_PAIRED_PURPOSE = "paired_arm_launch"
_CONTRACT = {
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "kill_mode": "control-group",
    "send_sigkill": True,
    "runtime_max_seconds": 1500,
    "internal_timeout_seconds": 1470,
}


class ExportableCpModel(Protocol):
    def export_to_file(self, file: str) -> bool: ...


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_chain(path: Path) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError as exc:
            raise ValueError(f"missing path component: {current}") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink path component rejected: {current}")


def _identity_from_bytes(path: Path, raw: bytes) -> dict[str, object]:
    return {
        "path": str(_absolute(path)),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    absolute = _absolute(path)
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite output: {absolute}")
    _reject_symlink_chain(absolute.parent)
    if not absolute.parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(absolute, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short authority write")
            view = view[written:]
        os.fsync(fd)
        descriptor = os.fstat(fd)
        named = os.lstat(absolute)
        if (
            not stat.S_ISREG(descriptor.st_mode)
            or stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or descriptor.st_dev != named.st_dev
            or descriptor.st_ino != named.st_ino
            or descriptor.st_size != len(raw)
        ):
            raise RuntimeError(f"exclusive output pathname drifted: {absolute}")
    finally:
        os.close(fd)
    return _identity_from_bytes(absolute, raw)


def _snapshot_exported_model(path: Path) -> tuple[bytes, dict[str, object]]:
    """Snapshot one official export through one O_NOFOLLOW descriptor."""

    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(absolute, flags)
    except OSError as exc:
        raise RuntimeError(f"cannot snapshot exported model: {exc}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError("exported model is not a regular file")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError("exported model truncated during snapshot")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise RuntimeError("exported model grew during snapshot")
        after = os.fstat(fd)
        named = os.lstat(absolute)
        stable = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in stable):
            raise RuntimeError("exported model changed during snapshot")
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or named.st_dev != after.st_dev
            or named.st_ino != after.st_ino
        ):
            raise RuntimeError("exported model pathname changed during snapshot")
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise RuntimeError("exported model snapshot length drifted")
    return raw, _identity_from_bytes(absolute, raw)


def _is_sha256(value: object) -> bool:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_json(raw: bytes) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"launch selection contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"launch selection contains invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("launch selection is not strict UTF-8 JSON") from exc


def _snapshot_regular(path: Path) -> tuple[bytes, dict[str, object]]:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(absolute, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("launch selection is not a regular file")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("launch selection truncated during snapshot")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ValueError("launch selection grew during snapshot")
        after = os.fstat(descriptor)
        named = os.lstat(absolute)
        stable = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in stable):
            raise ValueError("launch selection changed during snapshot")
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or named.st_dev != after.st_dev
            or named.st_ino != after.st_ino
        ):
            raise ValueError("launch selection pathname changed during snapshot")
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    return raw, _identity_from_bytes(absolute, raw)


def _strict_identity(value: object, field: str) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"path", "size_bytes", "sha256"}
        or type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
        or not _is_sha256(value["sha256"])
    ):
        raise ValueError(f"{field} must be a strict file identity")
    return {
        "path": str(value["path"]),
        "size_bytes": int(value["size_bytes"]),
        "sha256": str(value["sha256"]),
    }


def _identity_map(value: object, field: str) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{field} must be a non-empty mapping")
    result: dict[str, dict[str, object]] = {}
    for role, identity in value.items():
        if type(role) is not str or not role:
            raise ValueError(f"{field} contains an invalid role")
        result[role] = _strict_identity(identity, f"{field}.{role}")
    return result


def _validate_direct_selection(value: object) -> dict[str, object]:
    top_keys = {
        "schema",
        "created_at_utc",
        "purpose",
        "run_nonce",
        "package_id",
        "selection_id",
        "repository_head",
        "contract",
        "qualification_receipt_identity",
        "tools",
        "inputs",
        "arm_directories_absent_at_creation",
        "arm_launch",
        "terminal_observer_tool_role",
        "arms",
    }
    if not isinstance(value, Mapping) or set(value) != top_keys:
        raise ValueError("direct launch selection key set drifted")
    selection = dict(value)
    if (
        selection["schema"] != _SELECTION_SCHEMA
        or selection["purpose"] != _PAIRED_PURPOSE
        or type(selection["run_nonce"]) is not str
        or not selection["run_nonce"]
        or not _is_sha256(selection["package_id"])
        or not _is_sha256(selection["selection_id"])
        or type(selection["repository_head"]) is not str
        or len(selection["repository_head"]) != 40
        or selection["contract"] != _CONTRACT
        or selection["arm_directories_absent_at_creation"] is not True
        or selection["arm_launch"] is not True
    ):
        raise ValueError("direct launch selection semantics drifted")
    _strict_identity(
        selection["qualification_receipt_identity"],
        "selection.qualification_receipt_identity",
    )
    tools = _identity_map(selection["tools"], "selection.tools")
    _identity_map(selection["inputs"], "selection.inputs")
    if selection["terminal_observer_tool_role"] not in tools:
        raise ValueError("terminal observer role is not selection-bound")
    arms = selection["arms"]
    if not isinstance(arms, Mapping) or set(arms) != _ARMS:
        raise ValueError("direct launch selection arms drifted")
    for label in sorted(_ARMS):
        arm = arms[label]
        expected = {
            "arm",
            "attempt_dir",
            "unit_name",
            "result_path",
            "raw_output_path",
            "terminal_envelope_path",
            "runner_tool_role",
            "recorder_tool_role",
        }
        if not isinstance(arm, Mapping) or set(arm) != expected:
            raise ValueError(f"direct launch selection arm {label} key set drifted")
        attempt = Path(str(arm["attempt_dir"]))
        paths = [Path(str(arm[name])) for name in ("result_path", "raw_output_path", "terminal_envelope_path")]
        if (
            arm["arm"] != label
            or not attempt.is_absolute()
            or any(not path.is_absolute() or not path.absolute().is_relative_to(attempt.absolute()) for path in paths)
            or type(arm["unit_name"]) is not str
            or not arm["unit_name"].endswith(".service")
            or arm["runner_tool_role"] not in tools
            or arm["recorder_tool_role"] not in tools
        ):
            raise ValueError(f"direct launch selection arm {label} semantics drifted")
    body = dict(selection)
    selection_id = body.pop("selection_id")
    if hashlib.sha256(_canonical_bytes(body)).hexdigest() != selection_id:
        raise ValueError("direct launch selection digest mismatch")
    return selection


def _require_launch_selection(
    selection_path: Path,
    *,
    expected_identity: Mapping[str, object],
    expected_arm: object,
    expected_unit_name: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if expected_arm not in _ARMS or not expected_unit_name:
        raise ValueError("arm must explicitly select control or treatment")
    raw, observed_identity = _snapshot_regular(selection_path)
    detached_identity = _strict_identity(expected_identity, "expected selection identity")
    if observed_identity != detached_identity:
        raise ValueError("direct launch selection detached identity drifted")
    selection = _validate_direct_selection(_strict_json(raw))
    arm = dict(selection["arms"][str(expected_arm)])
    if arm["unit_name"] != expected_unit_name:
        raise ValueError("direct launch selection arm/unit binding drifted")
    tools = selection["tools"]
    _, current_runner = _snapshot_regular(Path(__file__))
    helper_matches = [
        (role, identity)
        for role, identity in tools.items()
        if identity["size_bytes"] == current_runner["size_bytes"] and identity["sha256"] == current_runner["sha256"]
    ]
    if len(helper_matches) != 1 or helper_matches[0][1] != current_runner:
        raise ValueError("binary helper tool identity must appear exactly once")
    helper_role, helper_identity = helper_matches[0]
    if arm["runner_tool_role"] == helper_role:
        raise ValueError("binary helper cannot masquerade as the selected arm runner")
    arm_runner_identity = tools[arm["runner_tool_role"]]
    binding = {
        "purpose": _PAIRED_PURPOSE,
        "arm_launch": True,
        "arm": str(expected_arm),
        "unit_name": expected_unit_name,
        "attempt_dir": arm["attempt_dir"],
        "run_nonce": selection["run_nonce"],
        "package_id": selection["package_id"],
        "selection_id": selection["selection_id"],
        "selection_identity": observed_identity,
        "runner_tool_role": arm["runner_tool_role"],
        "runner_identity": arm_runner_identity,
        "binary_helper_tool_role": helper_role,
        "binary_helper_identity": helper_identity,
    }
    return selection, arm, binding


def export_binary_prestate(
    *,
    model: ExportableCpModel,
    solver_response_text: str,
    output_parent: Path,
    attempt_name: str,
    arm: str,
    unit_name: str,
    selection_path: Path,
    expected_selection_identity: Mapping[str, object],
) -> dict[str, object]:
    """Export canonical model/response bytes into a new immutable attempt.

    ``CpModel.export_to_file`` selects binary output because the target suffix
    is ``.pb``, never ``.txt``.  The response is parsed by the official
    protobuf text parser and serialized deterministically.  The caller remains
    responsible for placing this helper before injection in a paired arm.
    """

    _selection, selected_arm, launch_selection = _require_launch_selection(
        selection_path,
        expected_identity=expected_selection_identity,
        expected_arm=arm,
        expected_unit_name=unit_name,
    )
    if type(solver_response_text) is not str or not solver_response_text.strip():
        raise ValueError("solver_response_text must be non-empty official response text")
    if (
        type(attempt_name) is not str
        or not attempt_name
        or attempt_name in {".", ".."}
        or "/" in attempt_name
        or "\\" in attempt_name
    ):
        raise ValueError("attempt_name must be one safe path component")
    parent = _absolute(output_parent)
    _reject_symlink_chain(parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("output_parent must be an existing non-symlink directory")
    if parent != _absolute(Path(str(selected_arm["attempt_dir"]))):
        raise ValueError("binary export parent differs from selected arm attempt directory")
    attempt = parent / attempt_name
    try:
        os.mkdir(attempt, 0o700)
    except FileExistsError as exc:
        raise FileExistsError(f"refusing to reuse binary export attempt: {attempt}") from exc

    model_path = attempt / "pre-injection-model.pb"
    response_path = attempt / "pre-injection-response.pb"
    manifest_path = attempt / "binary-export-manifest.json"
    if model_path.suffix == ".txt":
        raise AssertionError("binary model export target must not use .txt")
    exported = model.export_to_file(str(model_path))
    if exported is not True:
        raise RuntimeError("CpModel.export_to_file reported failure")
    model_raw, model_identity = _snapshot_exported_model(model_path)
    parsed_model = cp_model_pb2.CpModelProto()
    consumed = parsed_model.ParseFromString(model_raw)
    parsed_model.DiscardUnknownFields()
    if consumed != len(model_raw) or parsed_model.SerializeToString(deterministic=True) != model_raw:
        raise RuntimeError("exported model is not canonical binary CpModelProto")

    response = cp_model_pb2.CpSolverResponse()
    try:
        text_format.Parse(solver_response_text, response)
    except text_format.ParseError as exc:
        raise ValueError("solver response text is not an official CpSolverResponse") from exc
    response_raw = response.SerializeToString(deterministic=True)
    if not response_raw:
        raise ValueError("refusing to export an empty solver response")
    response_identity = _write_exclusive(response_path, response_raw)
    manifest = {
        "schema_version": 1,
        "contract": "positive_control_binary_prestate_v1",
        "arm": arm,
        "paired_arm_launch": launch_selection,
        "phase": "pre_injection",
        "model": model_identity,
        "response": response_identity,
        "claim_boundary": {
            "established": ["pre-injection model and retained response bytes exported"],
            "not_established": [
                "solver execution by this helper",
                "cut application",
                "cut soundness",
                "runtime usefulness",
            ],
        },
    }
    manifest_raw = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    manifest_identity = _write_exclusive(manifest_path, manifest_raw)
    return {**manifest, "manifest": manifest_identity}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        choices=sorted(_ARMS),
        required=True,
    )
    parser.add_argument("--unit-name", required=True)
    parser.add_argument("--launch-selection-path", type=Path, required=True)
    parser.add_argument("--launch-selection-size", type=int, required=True)
    parser.add_argument("--launch-selection-sha256", required=True)
    args = parser.parse_args()
    _selection, _selected_arm, binding = _require_launch_selection(
        args.launch_selection_path,
        expected_identity={
            "path": str(_absolute(args.launch_selection_path)),
            "size_bytes": args.launch_selection_size,
            "sha256": args.launch_selection_sha256,
        },
        expected_arm=args.arm,
        expected_unit_name=args.unit_name,
    )
    print(
        json.dumps(
            {
                "status": "CONTRACT_ONLY",
                "arm": args.arm,
                "paired_arm_launch": binding,
                "solver_started": False,
                "export_performed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
