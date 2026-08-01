#!/usr/bin/env python3
"""Package role implementing bounded, zero-authority AB16 calibration work."""

from __future__ import annotations

from collections.abc import Mapping
import ctypes
import errno
import fcntl
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import socket
import stat
import sys
from types import ModuleType
from typing import Any, Final, NoReturn, cast


RESULT_SCHEMA: Final = "noncert-cuts-ab16-resource-calibration-workload-result-v1"
GATE_B_FIXTURE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-gate-b-fixture-v1"
)
FORMAL_FIXTURE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-formal-fixture-v1"
)
EXACT_FORMAL_FIXTURE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-formal-fixture-v2"
)
AUTHORITY_SCOPE: Final = "AB16_RESOURCE_CALIBRATION_ONLY"
FALSE_AUTHORIZATIONS: Final = {
    "formal_attempt_consumption_authorized": False,
    "formal_campaign_creation_authorized": False,
    "formal_selection_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_authority_authorized": False,
}
MAX_FIXTURE_BYTES: Final = 4 * 1024 * 1024
MAX_FRAME_BYTES: Final = 4 * 1024 * 1024


class CalibrationWorkloadError(RuntimeError):
    pass


def _fail(detail: str) -> NoReturn:
    raise CalibrationWorkloadError(detail)


def _canonical(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail(f"canonical JSON failed: {exc}")


def _strict_json(raw: bytes, label: str) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> NoReturn:
        _fail(f"{label}: non-integer JSON value {value!r}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"{label}: malformed JSON: {exc}")
    if type(value) is not dict or _canonical(value) != raw:
        _fail(f"{label}: JSON is not canonical")
    return cast(dict[str, object], value)


def _read_fd(descriptor: int, limit: int, label: str) -> bytes:
    metadata = os.fstat(descriptor)
    flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
    if (
        flags & os.O_ACCMODE != os.O_RDONLY
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size <= 0
        or metadata.st_size > limit
    ):
        _fail(f"{label}: retained descriptor identity is invalid")
    raw = bytearray()
    offset = 0
    while offset < metadata.st_size:
        block = os.pread(descriptor, min(1024 * 1024, metadata.st_size - offset), offset)
        if not block:
            _fail(f"{label}: retained descriptor short read")
        raw.extend(block)
        offset += len(block)
    if os.pread(descriptor, 1, metadata.st_size):
        _fail(f"{label}: retained descriptor grew")
    after = os.fstat(descriptor)
    if (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        _fail(f"{label}: retained descriptor drifted")
    return bytes(raw)


def _read_anonymous_fd(descriptor: int, limit: int, label: str) -> bytes:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 0
        or metadata.st_size <= 0
        or metadata.st_size > limit
    ):
        _fail(f"{label}: anonymous descriptor identity is invalid")
    raw = bytearray()
    offset = 0
    while offset < metadata.st_size:
        block = os.pread(descriptor, min(1024 * 1024, metadata.st_size - offset), offset)
        if not block:
            _fail(f"{label}: anonymous descriptor short read")
        raw.extend(block)
        offset += len(block)
    if os.pread(descriptor, 1, metadata.st_size):
        _fail(f"{label}: anonymous descriptor grew")
    return bytes(raw)


def _relative(value: object, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label}: path is not text")
    path = cast(str, value)
    if (
        not path
        or path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        _fail(f"{label}: unsafe package-relative path")
    return path


def _open_member(root_fd: int, relative: str) -> int:
    parts = _relative(relative, "package member").split("/")
    flags_dir = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directories = [os.dup(root_fd)]
    result = -1
    primary: BaseException | None = None
    try:
        for part in parts[:-1]:
            directories.append(
                os.open(part, flags_dir, dir_fd=directories[-1])
            )
        result = os.open(
            parts[-1],
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directories[-1],
        )
    except BaseException as exc:
        primary = exc
    for descriptor in reversed(directories):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "package member directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    "package member descriptor cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return result


def _member_bytes(
    root_fd: int,
    receipt: Mapping[str, object],
    relative: str,
    *,
    label: str,
    limit: int = 64 * 1024 * 1024,
) -> bytes:
    identities = receipt.get("member_identities")
    if type(identities) is not dict or relative not in identities:
        _fail(f"{label}: member is absent from the closed package")
    expected = cast(dict[str, object], identities)[relative]
    descriptor = _open_member(root_fd, relative)
    try:
        raw = _read_fd(descriptor, limit, label)
    finally:
        os.close(descriptor)
    if expected != {
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }:
        _fail(f"{label}: member byte identity drifted")
    return raw


def _load_member_module(
    root_fd: int,
    receipt: Mapping[str, object],
    relative: str,
    *,
    module_name: str,
) -> ModuleType:
    raw = _member_bytes(root_fd, receipt, relative, label=module_name)
    descriptor = _open_member(root_fd, relative)
    try:
        if hashlib.sha256(_read_fd(descriptor, len(raw), module_name)).digest() != hashlib.sha256(raw).digest():
            _fail(f"{module_name}: retained member changed before execution")
        origin = f"/proc/self/fd/{descriptor}"
        spec = importlib.util.spec_from_loader(
            module_name,
            SourceFileLoader(module_name, origin),
            origin=origin,
        )
        if spec is None or spec.loader is None:
            _fail(f"{module_name}: cannot build module spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        os.close(descriptor)


def _write_frame(descriptor: int, value: object) -> None:
    raw = _canonical(value)
    if len(raw) > MAX_FRAME_BYTES:
        _fail("workload result exceeds fixed frame limit")
    payload = len(raw).to_bytes(4, "big") + raw
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            _fail("workload result pipe made no progress")
        offset += written


def _gate_b_workload(
    fixture: Mapping[str, object],
    *,
    package_root_fd: int,
    package_receipt: Mapping[str, object],
) -> dict[str, object]:
    expected = {
        "gate_b_module_member",
        "native_helper_binary_member",
        "native_helper_wrapper_member",
        "package_verifier_member",
        "planned_source_identities",
        "planned_source_observation",
        "planned_source_set_digest",
        "schema_version",
        "stage",
    }
    if set(fixture) != expected or fixture.get("schema_version") != GATE_B_FIXTURE_SCHEMA:
        _fail("Gate-B calibration fixture shape differs")
    if fixture.get("stage") != "GATE_B_QUALIFICATION":
        _fail("Gate-B calibration fixture stage differs")
    gate_module = _load_member_module(
        package_root_fd,
        package_receipt,
        _relative(fixture["gate_b_module_member"], "Gate-B module"),
        module_name="_ab16_gate_b_qualification_calibration_role",
    )
    package_verifier = _load_member_module(
        package_root_fd,
        package_receipt,
        _relative(fixture["package_verifier_member"], "package verifier"),
        module_name="_ab16_package_independent_verifier_calibration_role",
    )
    native_wrapper = _load_member_module(
        package_root_fd,
        package_receipt,
        _relative(
            fixture["native_helper_wrapper_member"],
            "native helper wrapper",
        ),
        module_name="_ab16_native_budget_helper_gate_b_calibration_role",
    )
    native_binary_fd = _open_member(
        package_root_fd,
        _relative(
            fixture["native_helper_binary_member"],
            "native helper binary",
        ),
    )
    try:
        helper = native_wrapper.NativeBudgetHelper(
            native_binary_fd,
            expected_identity=native_wrapper.expected_package_identity(),
        )
        helper.install_no_filesystem_writes_landlock()
    finally:
        os.close(native_binary_fd)
    identities = fixture["planned_source_identities"]
    if type(identities) is not dict or not identities:
        _fail("Gate-B planned source identities are absent")
    observed: dict[str, object] = {}
    checksum_lines: list[str] = []
    for label, raw_identity in sorted(cast(dict[str, object], identities).items()):
        if type(raw_identity) is not dict or set(raw_identity) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            _fail(f"Gate-B source identity {label!r} is malformed")
        identity = cast(dict[str, object], raw_identity)
        relative = _relative(identity["path"], f"Gate-B source {label}")
        raw = _member_bytes(
            package_root_fd,
            package_receipt,
            relative,
            label=f"Gate-B source {label}",
        )
        current = {
            "path": relative,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        if current != identity:
            _fail(f"Gate-B source identity {label!r} drifted")
        observed[label] = current
        checksum_lines.append(f"{current['sha256']}  {relative}\n")
    digest = hashlib.sha256(_canonical(observed)).hexdigest()
    if digest != fixture["planned_source_set_digest"]:
        _fail("Gate-B planned source-set digest drifted")
    observation_raw = _canonical(fixture["planned_source_observation"])
    parsed_observation = gate_module._strict_unterminated_json(  # noqa: SLF001
        observation_raw[:-1],
        "calibration planned-source observation",
    )
    if parsed_observation != {
        "planned_source_identities": observed,
        "planned_source_set_digest": digest,
    }:
        _fail("Gate-B planned-source observation differs")
    parsed_sums = package_verifier._parse_sha256sums(  # noqa: SLF001
        "".join(sorted(checksum_lines, key=lambda row: row.partition("  ")[2])).encode(
            "utf-8"
        )
    )
    if parsed_sums != {
        cast(str, identity["path"]): cast(str, identity["sha256"])
        for identity in cast(dict[str, dict[str, object]], identities).values()
    }:
        _fail("Gate-B package-verifier checksum arithmetic differs")
    return {
        "bounded_operations": {
            "gate_b_strict_parser": True,
            "package_verifier_checksum_parser": True,
            "planned_source_bytes": len(observed),
            "planned_source_set_digest": digest,
        },
        "stage": "GATE_B_QUALIFICATION",
        "status": "PASS_NO_AUTHORITY_PUBLICATION",
    }


class _CalibrationBudgetBackend:
    def __init__(
        self,
        *,
        socket_fd: int,
        helper: Any,
        arm_slot: str,
        segment_maximum: int,
        artifact_maxima: Mapping[str, Mapping[str, object]] | None = None,
        attempt_root: Path | None = None,
    ) -> None:
        self.socket_fd = socket_fd
        self.helper = helper
        self.arm_slot = arm_slot
        self.segment_maximum = segment_maximum
        self.sequence: dict[str, int] = {}
        self.artifact_maxima = (
            {}
            if artifact_maxima is None
            else {
                str(label): {
                    "artifact_class": value["artifact_class"],
                    "maximum_bytes": value["maximum_bytes"],
                }
                for label, value in artifact_maxima.items()
            }
        )
        self.attempt_root = (
            Path("/ab16-calibration/formal/attempt")
            if attempt_root is None
            else Path(os.path.abspath(attempt_root))
        )
        binding_bytes = _canonical(
            {
                "arm_slot": arm_slot,
                "artifact_maxima": self.artifact_maxima,
                "kind": "AB16_RESOURCE_CALIBRATION_ONLY",
            }
        )
        self._authority_binding = {
            "arm_allocation_id": hashlib.sha256(binding_bytes).hexdigest(),
            "arm_allocation_identity": {
                "sha256": hashlib.sha256(binding_bytes).hexdigest(),
                "size_bytes": len(binding_bytes),
            },
            "arm_slot": arm_slot,
            "broker_nonce": "ab16-calibration-broker-v1",
            "broker_socket_fd": socket_fd,
            "filesystem_write_confinement": "landlock-read-only-worker-v1",
            "formal_budget_authority_identity": {
                "path": "/ab16-calibration/no-authority-budget-binding.json",
                "sha256": hashlib.sha256(binding_bytes).hexdigest(),
                "size_bytes": len(binding_bytes),
            },
            "next_sequence": 1,
        }

    @property
    def authority_binding(self) -> Mapping[str, object]:
        return dict(self._authority_binding)

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        value = self.artifact_maxima.get(label)
        if (
            type(value) is not dict
            or value.get("artifact_class") != artifact_class
            or type(value.get("maximum_bytes")) is not int
            or cast(int, value["maximum_bytes"]) <= 0
        ):
            _fail(f"formal calibration artifact allocation differs: {label}")
        return cast(int, value["maximum_bytes"])

    def _sealed_payload(self, raw: bytes, *, label: str) -> int:
        if not raw:
            _fail(f"formal calibration empty payload: {label}")
        descriptor = self.helper.create_memfd("ab16-calibration-payload")
        try:
            if os.pwrite(descriptor, raw, 0) != len(raw):
                _fail(f"formal calibration payload short write: {label}")
            os.fsync(descriptor)
            if self.helper.has_writable_mapping(descriptor):
                _fail(f"formal calibration payload has writable mapping: {label}")
            if (
                self.helper.install_final_seals(descriptor)
                != self.helper.final_seal_mask
                or self.helper.get_seals(descriptor)
                != self.helper.final_seal_mask
            ):
                _fail(f"formal calibration payload seal failed: {label}")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]:
        if (
            type(raw) is not bytes
            or len(raw) > maximum_bytes
            or maximum_bytes
            != self.maximum_bytes(label, artifact_class=artifact_class)
        ):
            _fail(f"formal calibration publication allocation differs: {label}")
        absolute = Path(os.path.abspath(path))
        try:
            relative = absolute.relative_to(self.attempt_root).as_posix()
        except ValueError:
            _fail(f"formal calibration target escaped the attempt root: {label}")
        descriptor = self._sealed_payload(raw, label=label)
        try:
            request = {
                "absolute_path": str(absolute),
                "artifact_class": artifact_class,
                "kind": "regular",
                "label": label,
                "maximum_bytes": maximum_bytes,
                "relative_path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
            _send_message(self.socket_fd, request, descriptor, self.helper)
            response = _receive_json(self.socket_fd)
        finally:
            os.close(descriptor)
        result = response.get("result")
        if (
            response.get("status") != "PUBLISHED"
            or type(result) is not dict
            or result
            != {
                "path": str(absolute),
                "sha256": request["sha256"],
                "size_bytes": len(raw),
            }
        ):
            _fail(f"formal calibration publication acknowledgement differs: {label}")
        return cast(dict[str, object], result)

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> Mapping[str, object]:
        expected = self.sequence.get(channel, 0)
        expected_maximum = self.segment_maximum
        channel_label = "bounded proxy ledger segment"
        if self.artifact_maxima:
            channel_label = (
                "compile attach journal segment"
                if channel.endswith("-compile-journal")
                else (
                    "cut ledger segment"
                    if channel.endswith("-cut-ledger")
                    else (
                        "runtime cut segment"
                        if channel.endswith("-runtime-cuts")
                        else ""
                    )
                )
            )
            if not channel_label:
                _fail("formal calibration append channel differs")
            expected_maximum = self.maximum_bytes(
                channel_label,
                artifact_class="ledger",
            )
        if (
            sequence != expected
            or arm_slot != self.arm_slot
            or artifact_class != "ledger"
            or maximum_bytes != expected_maximum
            or not raw
            or len(raw) > maximum_bytes
        ):
            _fail("formal calibration immutable append request differs")
        descriptor = self.helper.create_memfd("ab16-calibration-ledger")
        try:
            if os.pwrite(descriptor, raw, 0) != len(raw):
                _fail("formal calibration memfd short write")
            os.fsync(descriptor)
            if self.helper.has_writable_mapping(descriptor):
                _fail("formal calibration ledger memfd has writable mapping")
            if self.helper.install_final_seals(descriptor) != self.helper.final_seal_mask:
                _fail("formal calibration ledger memfd seal failed")
            request = {
                "arm_slot": self.arm_slot,
                "artifact_class": artifact_class,
                "channel": channel,
                "kind": "append",
                "label": channel_label,
                "maximum_bytes": maximum_bytes,
                "sequence": sequence,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
            _send_message(self.socket_fd, request, descriptor, self.helper)
            response = _receive_json(self.socket_fd)
        finally:
            os.close(descriptor)
        raw_result = response.get("result")
        if type(raw_result) is not dict:
            _fail("formal calibration broker acknowledgement lacks a result")
        response_result = cast(dict[str, object], raw_result)
        if (
            response.get("status") != "PUBLISHED"
            or type(response_result.get("path")) is not str
            or response_result != {
            "path": response_result["path"],
            "sha256": request["sha256"],
            "size_bytes": len(raw),
            }
        ):
            _fail("formal calibration broker acknowledgement differs")
        self.sequence[channel] = sequence + 1
        return response_result

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]:
        if maximum_bytes != self.maximum_bytes(label, artifact_class="model"):
            _fail(f"formal calibration model allocation differs: {label}")
        absolute = Path(os.path.abspath(path))
        try:
            relative = absolute.relative_to(self.attempt_root).as_posix()
        except ValueError:
            _fail(f"formal calibration model escaped the attempt root: {label}")
        descriptor = self.helper.create_memfd("ab16-calibration-model")
        try:
            _soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
            if hard != resource.RLIM_INFINITY and maximum_bytes > hard:
                _fail("formal calibration model maximum exceeds RLIMIT_FSIZE")
            resource.setrlimit(resource.RLIMIT_FSIZE, (maximum_bytes, hard))
            exported = getattr(model, "export_to_file", None)
            if exported is None or exported(f"/proc/self/fd/{descriptor}") is not True:
                _fail("formal calibration model export failed")
            size = os.fstat(descriptor).st_size
            if size <= 0 or size > maximum_bytes:
                _fail("formal calibration model export size differs")
            if self.helper.has_writable_mapping(descriptor):
                _fail("formal calibration model memfd has writable mapping")
            if (
                self.helper.install_final_seals(descriptor)
                != self.helper.final_seal_mask
                or self.helper.get_seals(descriptor)
                != self.helper.final_seal_mask
            ):
                _fail("formal calibration model final seal mask differs")
            digest = _hash_fd(descriptor, size)
            request = {
                "absolute_path": str(absolute),
                "artifact_class": "model",
                "kind": "model",
                "label": label,
                "maximum_bytes": maximum_bytes,
                "relative_path": relative,
                "sha256": digest,
                "size_bytes": size,
            }
            _send_message(self.socket_fd, request, descriptor, self.helper)
            response = _receive_json(self.socket_fd)
        finally:
            os.close(descriptor)
        result = response.get("result")
        if (
            response.get("status") != "PUBLISHED"
            or type(result) is not dict
            or result
            != {
                "path": str(absolute),
                "sha256": digest,
                "size_bytes": size,
            }
        ):
            _fail("formal calibration model acknowledgement differs")
        return cast(dict[str, object], result)


def _send_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            _fail("calibration socket short write")
        offset += written


def _send_message(socket_fd: int, value: object, payload_fd: int, helper: Any) -> None:
    raw = _canonical(value)
    _send_all(socket_fd, len(raw).to_bytes(4, "big") + raw)
    helper.send_fd(socket_fd, payload_fd)


def _read_exact(descriptor: int, size: int) -> bytes:
    result = b""
    while len(result) < size:
        chunk = os.read(descriptor, size - len(result))
        if not chunk:
            _fail("calibration socket closed")
        result += chunk
    return result


def _receive_json(socket_fd: int) -> dict[str, object]:
    size = int.from_bytes(_read_exact(socket_fd, 4), "big")
    if size <= 0 or size > MAX_FRAME_BYTES:
        _fail("calibration socket frame size differs")
    return _strict_json(_read_exact(socket_fd, size), "calibration socket frame")


def _rename_noreplace(parent_fd: int, source: str, target: str) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = library.renameat2
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        parent_fd,
        os.fsencode(source),
        parent_fd,
        os.fsencode(target),
        1,
    ) != 0:
        number = ctypes.get_errno()
        if number == errno.EEXIST:
            _fail(f"calibration no-overwrite collision: {target}")
        _fail(f"calibration renameat2 failed: errno={number}")


class _CalibrationBroker:
    def __init__(
        self,
        *,
        root_fd: int,
        helper: Any,
        aggregate_budget: int,
        exact_organic: bool = False,
        arm_slot: str | None = None,
        artifact_maxima: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self.root_fd = root_fd
        self.helper = helper
        self.aggregate_budget = aggregate_budget
        self.reserved = 0
        self.ordinal = 0
        self.arm_slot = arm_slot
        self.artifact_maxima = (
            {}
            if artifact_maxima is None
            else {
                label: {
                    "artifact_class": value["artifact_class"],
                    "maximum_bytes": value["maximum_bytes"],
                }
                for label, value in artifact_maxima.items()
            }
        )
        self.channel_sequences: dict[str, int] = {}
        directories = (
            (
                "attempt",
                "attempt/checkpoint",
                "attempt/checkpoint/runtime-cuts",
                "attempt/ledger",
                "attempt/ledger/compile-attach-journal",
                "attempt/ledger/cut-ledger",
                "attempt/replays",
                "attempt/runtime",
                "ledger",
                "models",
            )
            if exact_organic
            else ("ledger", "models")
        )
        for directory in directories:
            self._mkdir_relative(directory)
        os.fsync(root_fd)

    def _mkdir_relative(self, relative: str) -> None:
        current = os.dup(self.root_fd)
        primary: BaseException | None = None
        try:
            for part in relative.split("/"):
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
                child = os.open(
                    part,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=current,
                )
                os.close(current)
                current = child
        except BaseException as exc:
            primary = exc
        try:
            os.close(current)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(f"calibration broker mkdir cleanup failed: {close_error}")
        if primary is not None:
            raise primary

    def _open_relative_parent(self, relative: str) -> tuple[int, str]:
        parts = relative.split("/")
        if (
            not parts
            or any(part in {"", ".", ".."} for part in parts)
            or relative.startswith("/")
        ):
            _fail(f"calibration broker relative target is unsafe: {relative!r}")
        descriptor = os.dup(self.root_fd)
        try:
            for part in parts[:-1]:
                child = os.open(
                    part,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor, parts[-1]

    def _publish_payload(
        self,
        *,
        relative: str,
        receipt_path: str,
        raw: bytes,
        maximum: int,
        digest: str,
    ) -> dict[str, object]:
        if (
            maximum <= 0
            or not raw
            or len(raw) > maximum
            or hashlib.sha256(raw).hexdigest() != digest
            or self.reserved + maximum > self.aggregate_budget
        ):
            _fail("calibration broker payload exceeds aggregate budget")
        self.reserved += maximum
        parent_fd, target = self._open_relative_parent(relative)
        staging = f".{target}.calibration-staging"
        output = -1
        try:
            output = os.open(
                staging,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            os.posix_fallocate(output, 0, maximum)
            if os.pwrite(output, raw, 0) != len(raw):
                _fail("calibration broker staging short write")
            os.ftruncate(output, len(raw))
            os.fsync(output)
            os.fchmod(output, 0o400)
            os.fsync(output)
            _rename_noreplace(parent_fd, staging, target)
            os.fsync(parent_fd)
        finally:
            if output >= 0:
                os.close(output)
            os.close(parent_fd)
        return {
            "path": receipt_path,
            "sha256": digest,
            "size_bytes": len(raw),
        }

    def publish_regular(
        self,
        request: Mapping[str, object],
        descriptor: int,
    ) -> dict[str, object]:
        maximum = request.get("maximum_bytes")
        size = request.get("size_bytes")
        digest = request.get("sha256")
        relative = request.get("relative_path")
        absolute = request.get("absolute_path")
        artifact_class = request.get("artifact_class")
        label = request.get("label")
        cap = self.artifact_maxima.get(cast(str, label))
        if (
            request.get("kind") not in {"model", "regular"}
            or type(maximum) is not int
            or type(size) is not int
            or type(digest) is not str
            or type(relative) is not str
            or type(absolute) is not str
            or type(artifact_class) is not str
            or type(label) is not str
            or (
                self.artifact_maxima
                and (
                    type(cap) is not dict
                    or cap.get("artifact_class") != artifact_class
                    or cap.get("maximum_bytes") != maximum
                )
            )
            or size <= 0
            or size > maximum
            or self.helper.get_seals(descriptor) != self.helper.final_seal_mask
            or self.helper.has_writable_mapping(descriptor)
        ):
            _fail("calibration broker regular request differs")
        raw = _read_anonymous_fd(descriptor, maximum, "broker regular payload")
        if len(raw) != size:
            _fail("calibration broker regular payload size differs")
        return self._publish_payload(
            relative=relative,
            receipt_path=absolute,
            raw=raw,
            maximum=maximum,
            digest=digest,
        )

    def publish(self, request: Mapping[str, object], descriptor: int) -> dict[str, object]:
        maximum = request.get("maximum_bytes")
        size = request.get("size_bytes")
        digest = request.get("sha256")
        artifact_class = request.get("artifact_class")
        channel = request.get("channel")
        label = request.get("label")
        sequence = request.get("sequence")
        cap = self.artifact_maxima.get(cast(str, label))
        if (
            type(maximum) is not int
            or type(size) is not int
            or type(digest) is not str
            or artifact_class != "ledger"
            or type(channel) is not str
            or type(label) is not str
            or type(sequence) is not int
            or request.get("kind") not in {None, "append"}
            or maximum <= 0
            or size <= 0
            or size > maximum
            or self.reserved + maximum > self.aggregate_budget
            or self.helper.get_seals(descriptor) != self.helper.final_seal_mask
            or self.helper.has_writable_mapping(descriptor)
            or (
                self.artifact_maxima
                and (
                    type(cap) is not dict
                    or request.get("arm_slot") != self.arm_slot
                    or cap.get("artifact_class") != artifact_class
                    or cap.get("maximum_bytes") != maximum
                    or label
                    not in {
                        "compile attach journal segment",
                        "cut ledger segment",
                        "runtime cut segment",
                    }
                    or sequence != self.channel_sequences.get(channel, 0)
                )
            )
        ):
            _fail("calibration broker request exceeds fixed aggregate budget")
        raw = _read_anonymous_fd(descriptor, maximum, "broker payload")
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            _fail("calibration broker payload identity differs")
        self.ordinal += 1
        target = f"segment-{self.ordinal:08d}.bin"
        self.channel_sequences[channel] = sequence + 1
        parent = (
            "attempt/ledger/compile-attach-journal"
            if channel.endswith("-compile-journal")
            else (
                "attempt/ledger/cut-ledger"
                if channel.endswith("-cut-ledger")
                else (
                    "attempt/checkpoint/runtime-cuts"
                    if channel.endswith("-runtime-cuts")
                    else "ledger"
                )
            )
        )
        return self._publish_payload(
            relative=f"{parent}/{target}",
            receipt_path=f"{parent}/{target}",
            raw=raw,
            maximum=maximum,
            digest=digest,
        )

    def publish_model(self, descriptor: int, *, maximum: int) -> dict[str, object]:
        metadata = os.fstat(descriptor)
        if (
            metadata.st_size <= 0
            or metadata.st_size > maximum
            or self.reserved + maximum > self.aggregate_budget
            or self.helper.get_seals(descriptor) != self.helper.final_seal_mask
            or self.helper.has_writable_mapping(descriptor)
        ):
            _fail("calibration model exceeds aggregate budget")
        self.reserved += maximum
        raw = _read_anonymous_fd(descriptor, maximum, "calibration model")
        digest = hashlib.sha256(raw).hexdigest()
        model_fd = os.open(
            "models",
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self.root_fd,
        )
        staging = ".organic-arm-model.staging"
        output = -1
        try:
            output = os.open(
                staging,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=model_fd,
            )
            os.posix_fallocate(output, 0, maximum)
            if os.pwrite(output, raw, 0) != len(raw):
                _fail("calibration model staging short write")
            os.ftruncate(output, len(raw))
            os.fsync(output)
            os.fchmod(output, 0o400)
            os.fsync(output)
            _rename_noreplace(model_fd, staging, "organic-arm-model.pb")
            os.fsync(model_fd)
        finally:
            if output >= 0:
                os.close(output)
            os.close(model_fd)
        return {
            "path": "models/organic-arm-model.pb",
            "sha256": digest,
            "size_bytes": len(raw),
        }


def _formal_worker(
    fixture: Mapping[str, object],
    *,
    socket_fd: int,
    helper: Any,
) -> dict[str, object]:
    # Imports occur from the retained package-root PathFinder surface installed
    # by the loader.  They are completed before close_range/Landlock.
    from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
        AB16BudgetedCutLedgerWriter,
        AB16BudgetedCutManager,
    )
    from ortools.sat.python import cp_model

    for module in (
        sys.modules[
            "docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1"
        ],
        sys.modules["src.cuts.ledger"],
        sys.modules["src.models.cut_manager"],
    ):
        origin = str(getattr(module, "__file__", ""))
        if not origin.startswith("/proc/self/fd/"):
            _fail(f"formal calibration imported an ambient project module: {origin}")
    variables = fixture["variable_count"]
    segment_maximum = fixture["ledger_segment_maximum_bytes"]
    model_maximum = fixture["model_maximum_bytes"]
    if (
        type(variables) is not int
        or not 2 <= variables <= 256
        or type(segment_maximum) is not int
        or not 4096 <= segment_maximum <= 1024 * 1024
        or type(model_maximum) is not int
        or not 1024 * 1024 <= model_maximum <= 64 * 1024 * 1024
    ):
        _fail("formal calibration fixture workload bounds differ")
    helper.close_range_allowlist([0, 1, 2, socket_fd])
    helper.install_no_filesystem_writes_landlock()

    backend = _CalibrationBudgetBackend(
        socket_fd=socket_fd,
        helper=helper,
        arm_slot="calibration-arm",
        segment_maximum=segment_maximum,
    )
    ledger = AB16BudgetedCutLedgerWriter(
        Path("/landlock-denied"),
        scope_id="calibration-scope",
        writer_id="calibration-writer",
        immutable_budget=backend,
        budget_channel="calibration-cut-ledger",
        budget_segment_max_bytes=segment_maximum,
        budget_arm_slot="calibration-arm",
    )
    manager = AB16BudgetedCutManager(
        Path("/landlock-denied"),
        solve_mode="exploratory",
        immutable_budget=backend,
        budget_channel="calibration-runtime-cuts",
        budget_segment_max_bytes=segment_maximum,
        budget_arm_slot="calibration-arm",
    )
    ledger.append(
        "GENERATED",
        {"calibration_only": True, "ordinal": 1},
    )
    manager.add_cut(
        [{"instance_id": "calibration", "pose_id": "0"}],
        "bounded calibration cut",
        "resource calibration",
    )

    model = cp_model.CpModel()
    choices = [model.new_bool_var(f"x_{index}") for index in range(variables)]
    model.add_exactly_one(choices)
    model.maximize(sum((index + 1) * choice for index, choice in enumerate(choices)))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.solve(model)
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        _fail(f"formal calibration CP-SAT status differs: {solver.status_name(status)}")

    model_fd = helper.create_memfd("ab16-calibration-model")
    try:
        sentinel = b"AB16_O_TRUNC_SENTINEL"
        if os.pwrite(model_fd, sentinel, 0) != len(sentinel):
            _fail("formal calibration model sentinel short write")
        _soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        if hard != resource.RLIM_INFINITY and model_maximum > hard:
            _fail("formal calibration model limit exceeds RLIMIT_FSIZE")
        resource.setrlimit(resource.RLIMIT_FSIZE, (model_maximum, hard))
        if model.export_to_file(f"/proc/self/fd/{model_fd}") is not True:
            _fail("formal calibration model export failed")
        model_size = os.fstat(model_fd).st_size
        if (
            model_size <= 0
            or model_size > model_maximum
            or os.pread(model_fd, len(sentinel), 0).startswith(sentinel)
        ):
            _fail("formal calibration O_TRUNC/export contract differs")
        if helper.has_writable_mapping(model_fd):
            _fail("formal calibration model memfd has writable mapping")
        if helper.install_final_seals(model_fd) != helper.final_seal_mask:
            _fail("formal calibration model seal failed")
        request = {
            "artifact_class": "model",
            "maximum_bytes": model_maximum,
            "sha256": _hash_fd(model_fd, model_size),
            "size_bytes": model_size,
        }
        _send_message(socket_fd, request, model_fd, helper)
        response = _receive_json(socket_fd)
    finally:
        os.close(model_fd)
    ledger.seal({"calibration_only": True})
    return {
        "cut_manager_segments": len(manager.immutable_segment_records),
        "ledger_segments": len(ledger.immutable_segment_records),
        "model_publication": response["result"],
        "ortools_status": solver.status_name(status),
        "selected_index": next(index for index, choice in enumerate(choices) if solver.value(choice)),
    }


class _LazyCalibrationLedger:
    """Create the package-pinned immutable adapter only after construction begins."""

    def __init__(
        self,
        *,
        backend: _CalibrationBudgetBackend,
        arm_slot: str,
        segment_maximum: int,
    ) -> None:
        self.backend = backend
        self.arm_slot = arm_slot
        self.segment_maximum = segment_maximum
        self._delegate: Any | None = None

    def _get(self) -> Any:
        if self._delegate is None:
            from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
                AB16BudgetedCutLedgerWriter,
            )

            self._delegate = AB16BudgetedCutLedgerWriter(
                Path("/ab16-calibration/formal/attempt/ledger"),
                scope_id=self.arm_slot,
                writer_id="ab16-resource-calibration-v1",
                genesis_context={
                    "arm_slot": self.arm_slot,
                    "authority_scope": AUTHORITY_SCOPE,
                },
                immutable_budget=self.backend,
                budget_channel=f"arm-{self.arm_slot}-cut-ledger",
                budget_segment_max_bytes=self.segment_maximum,
                budget_arm_slot=self.arm_slot,
            )
        return self._delegate

    def append(self, event: str, payload: Mapping[str, object]) -> None:
        self._get().append(event, payload)

    def seal(self, payload: Mapping[str, object]) -> None:
        self._get().seal(payload)

    @property
    def immutable_segment_records(self) -> object:
        return self._get().immutable_segment_records


def _exact_formal_worker(
    fixture: Mapping[str, object],
    *,
    socket_fd: int,
    helper: Any,
    package_root_fd: int,
    package_receipt: Mapping[str, object],
) -> dict[str, object]:
    import docs.research.noncert_cuts_ab16_20260724.organic_arm_runner_v1 as organic

    origin = str(getattr(organic, "__file__", ""))
    repository = cast(dict[str, object], package_receipt["repository_snapshot"])
    repository_prefix = cast(str, repository["repository_prefix"])
    retained_repository = Path(f"/proc/self/fd/{package_root_fd}") / repository_prefix
    expected_runner = (
        retained_repository
        / "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py"
    )
    if Path(origin).resolve() != expected_runner.resolve():
        _fail("exact formal calibration imported an ambient organic runner")
    artifact_maxima = fixture["artifact_maxima"]
    runtime_parameters = fixture["runtime_parameters"]
    enabled_families = fixture["enabled_families"]
    arm_slot = fixture["arm_slot"]
    aggregate = fixture["aggregate_budget_bytes"]
    if (
        type(artifact_maxima) is not dict
        or set(artifact_maxima) != set(organic.BUDGET_ARTIFACT_CLASS_BY_LABEL)
        or type(runtime_parameters) is not dict
        or type(enabled_families) is not list
        or enabled_families
        != ["region_capacity", "shape_packing_hall", "power_hitting_set"]
        or arm_slot != "bundle-ab-treatment"
        or type(aggregate) is not int
        or aggregate <= 0
    ):
        _fail("exact formal calibration fixture boundary differs")
    checked_maxima = cast(dict[str, Mapping[str, object]], artifact_maxima)
    for label, artifact_class in organic.BUDGET_ARTIFACT_CLASS_BY_LABEL.items():
        cap = checked_maxima.get(label)
        if (
            type(cap) is not dict
            or set(cap) != {"artifact_class", "maximum_bytes"}
            or cap["artifact_class"] != artifact_class
            or type(cap["maximum_bytes"]) is not int
            or cast(int, cap["maximum_bytes"]) <= 0
            or cast(int, cap["maximum_bytes"]) > aggregate
        ):
            _fail(f"exact formal calibration cap differs: {label}")
    segment_maximum = cast(
        int,
        checked_maxima["cut ledger segment"]["maximum_bytes"],
    )
    attempt_root = Path("/ab16-calibration/formal/attempt")
    backend = _CalibrationBudgetBackend(
        socket_fd=socket_fd,
        helper=helper,
        arm_slot=cast(str, arm_slot),
        segment_maximum=segment_maximum,
        artifact_maxima=checked_maxima,
        attempt_root=attempt_root,
    )
    ledger = _LazyCalibrationLedger(
        backend=backend,
        arm_slot=cast(str, arm_slot),
        segment_maximum=segment_maximum,
    )
    runner_member = cast(
        dict[str, object],
        cast(dict[str, object], package_receipt["member_identities"])[
            f"{repository_prefix}/docs/research/noncert_cuts_ab16_20260724/"
            "organic_arm_runner_v1.py"
        ],
    )
    execution_source = {
        "execution_working_directory": str(retained_repository),
        "live_source_provenance_root": "/ab16-calibration/no-live-checkout",
        "module_origin_receipt_path": str(
            attempt_root / "supervisor-module-origin-receipt.json"
        ),
        "runner_snapshot_member_identity": {
            **runner_member,
            "path": str(expected_runner),
        },
        "sealed_snapshot_execution_root": str(retained_repository),
    }
    organic._assert_initial_import_boundary(execution_source)
    helper.close_range_allowlist([0, 1, 2, socket_fd, package_root_fd])
    helper.install_no_filesystem_writes_landlock()
    context = organic.ArmContext(
        attempt_dir=attempt_root,
        budget_backend=backend,
        enabled_families=tuple(cast(list[str], enabled_families)),
        ledger=ledger,
        manifest={"runtime_parameters": runtime_parameters},
        repository_root=retained_repository,
        execution_source=execution_source,
        live_source_provenance_root=Path(
            "/ab16-calibration/no-live-checkout"
        ),
        selection={"slot": arm_slot},
        workers=1,
    )
    hooks = organic.ProductionArmHooks()
    previous_attach = os.environ.pop(organic.ATTACH_ENV, None)
    journal: Any | None = None
    failure: BaseException | None = None
    try:
        runtime = hooks.construct(context)
        journal = organic.HashChainJournal(
            attempt_root / "compile-attach-journal.jsonl",
            genesis={
                "arm_slot": arm_slot,
                "authority_scope": AUTHORITY_SCOPE,
            },
            budget_backend=backend,
            budget_channel=f"arm-{arm_slot}-compile-journal",
            budget_segment_max_bytes=cast(
                int,
                checked_maxima["compile attach journal segment"]["maximum_bytes"],
            ),
            budget_arm_slot=cast(str, arm_slot),
        )

        class AdaptiveNoAuthorityRecorder(organic.CompileAttachRecorder):
            def authorize_first_attach_solution(
                self,
                solution: Mapping[str, object],
            ) -> str:
                if not self._solution_authorized:
                    self._expected_solution_digest = organic.semantic_digest(
                        organic._json_projection(
                            solution,
                            "calibration first attach solution",
                        )
                    )
                return super().authorize_first_attach_solution(solution)

        recorder = AdaptiveNoAuthorityRecorder(
            journal,
            expected_solution_digest="0" * 64,
            require_model_evidence=True,
        )
        os.environ[organic.ATTACH_ENV] = "1"
        outcome = hooks.run_attach_phase(runtime, context, recorder)
        recorder.finalize()
        ledger.seal(
            {
                "authority_scope": AUTHORITY_SCOPE,
                "calibration_completed": True,
            }
        )
        journal.seal()
        return {
            "arm_slot": arm_slot,
            "compiled_cut_count": recorder.compiled_count,
            "controller_status": outcome.raw_solver_status,
            "hook_count": recorder.hook_count,
            "ledger_segment_count": len(
                cast(list[dict[str, object]], ledger.immutable_segment_records)
            ),
            "stage": "FORMAL_ORGANIC_ARM",
            "status": "PASS_EXACT_PRODUCTION_CALL_GRAPH_NO_AUTHORITY",
        }
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if failure is not None and journal is not None:
            try:
                journal.abort()
            except BaseException as cleanup_error:
                failure.add_note(
                    "exact formal calibration journal cleanup failed: "
                    f"{cleanup_error}"
                )
        if previous_attach is None:
            os.environ.pop(organic.ATTACH_ENV, None)
        else:
            os.environ[organic.ATTACH_ENV] = previous_attach


def _hash_fd(descriptor: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        block = os.pread(descriptor, min(1024 * 1024, size - offset), offset)
        if not block:
            _fail("retained descriptor short hash read")
        digest.update(block)
        offset += len(block)
    return digest.hexdigest()


def _formal_workload(
    fixture: Mapping[str, object],
    *,
    package_root_fd: int,
    package_receipt: Mapping[str, object],
    stage_root_fd: int,
) -> dict[str, object]:
    schema = fixture.get("schema_version")
    exact_organic = schema == EXACT_FORMAL_FIXTURE_SCHEMA
    expected = (
        {
            "aggregate_budget_bytes",
            "arm_slot",
            "artifact_maxima",
            "enabled_families",
            "native_helper_binary_member",
            "native_helper_wrapper_member",
            "runtime_parameters",
            "schema_version",
            "stage",
            "workload_kind",
        }
        if exact_organic
        else {
            "aggregate_budget_bytes",
            "ledger_segment_maximum_bytes",
            "model_maximum_bytes",
            "native_helper_binary_member",
            "native_helper_wrapper_member",
            "schema_version",
            "stage",
            "variable_count",
        }
    )
    if (
        set(fixture) != expected
        or schema not in {EXACT_FORMAL_FIXTURE_SCHEMA, FORMAL_FIXTURE_SCHEMA}
        or (
            exact_organic
            and fixture.get("workload_kind")
            != "EXACT_ORGANIC_PRODUCTION_CALL_GRAPH_V1"
        )
    ):
        _fail("formal calibration fixture shape differs")
    if fixture.get("stage") != "FORMAL_ORGANIC_ARM":
        _fail("formal calibration fixture stage differs")
    aggregate = fixture["aggregate_budget_bytes"]
    if (
        type(aggregate) is not int
        or aggregate < 8 * 1024 * 1024
        or aggregate > (32 * 1024**3 if exact_organic else 128 * 1024 * 1024)
    ):
        _fail("formal calibration aggregate budget differs")
    checked_artifact_maxima: dict[str, Mapping[str, object]] = {}
    checked_arm_slot: str | None = None
    if exact_organic:
        import docs.research.noncert_cuts_ab16_20260724.organic_arm_runner_v1 as organic

        repository = cast(dict[str, object], package_receipt["repository_snapshot"])
        expected_origin = (
            Path(f"/proc/self/fd/{package_root_fd}")
            / cast(str, repository["repository_prefix"])
            / "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py"
        )
        if Path(cast(str, organic.__file__)).resolve() != expected_origin.resolve():
            _fail("formal calibration broker imported an ambient organic runner")
        raw_maxima = fixture["artifact_maxima"]
        raw_slot = fixture["arm_slot"]
        if (
            type(raw_maxima) is not dict
            or set(raw_maxima) != set(organic.BUDGET_ARTIFACT_CLASS_BY_LABEL)
            or raw_slot != "bundle-ab-treatment"
            or fixture["enabled_families"]
            != ["region_capacity", "shape_packing_hall", "power_hitting_set"]
        ):
            _fail("exact formal calibration fixture boundary differs")
        try:
            organic._runtime_parameters(fixture["runtime_parameters"])
        except BaseException as exc:
            _fail(f"exact formal runtime parameters differ: {exc}")
        for label, artifact_class in organic.BUDGET_ARTIFACT_CLASS_BY_LABEL.items():
            raw_cap = cast(dict[str, object], raw_maxima)[label]
            if (
                type(raw_cap) is not dict
                or set(raw_cap) != {"artifact_class", "maximum_bytes"}
                or raw_cap["artifact_class"] != artifact_class
                or type(raw_cap["maximum_bytes"]) is not int
                or cast(int, raw_cap["maximum_bytes"]) <= 0
                or cast(int, raw_cap["maximum_bytes"]) > aggregate
            ):
                _fail(f"exact formal calibration cap differs: {label}")
            checked_artifact_maxima[label] = cast(
                Mapping[str, object],
                raw_cap,
            )
        checked_arm_slot = cast(str, raw_slot)
    wrapper = _load_member_module(
        package_root_fd,
        package_receipt,
        _relative(fixture["native_helper_wrapper_member"], "native helper wrapper"),
        module_name="_ab16_native_budget_helper_calibration_role",
    )
    binary_relative = _relative(
        fixture["native_helper_binary_member"],
        "native helper binary",
    )
    binary_fd = _open_member(package_root_fd, binary_relative)
    helper = wrapper.NativeBudgetHelper(
        binary_fd,
        expected_identity=wrapper.expected_package_identity(),
    )
    pair_parent, pair_child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_STREAM | socket.SOCK_CLOEXEC,
    )
    pid = os.fork()
    if pid == 0:
        pair_parent.close()
        try:
            result = (
                _exact_formal_worker(
                    fixture,
                    socket_fd=pair_child.fileno(),
                    helper=helper,
                    package_root_fd=package_root_fd,
                    package_receipt=package_receipt,
                )
                if exact_organic
                else _formal_worker(
                    fixture,
                    socket_fd=pair_child.fileno(),
                    helper=helper,
                )
            )
            _send_all(
                pair_child.fileno(),
                len(_canonical({"action": "WORKER_COMPLETE", "result": result})).to_bytes(4, "big")
                + _canonical({"action": "WORKER_COMPLETE", "result": result}),
            )
            os._exit(0)
        except BaseException as exc:
            try:
                failure = _canonical(
                    {
                        "action": "WORKER_FAILED",
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                )
                _send_all(
                    pair_child.fileno(),
                    len(failure).to_bytes(4, "big") + failure,
                )
            except BaseException:
                pass
            os._exit(2)
    pair_child_close_attempted = False
    pair_parent_close_attempted = False
    binary_fd_close_attempted = False
    worker_waited = False
    worker_result: dict[str, object] | None = None
    calibration_broker: _CalibrationBroker | None = None
    primary: BaseException | None = None
    try:
        pair_child_close_attempted = True
        pair_child.close()
        calibration_broker = _CalibrationBroker(
            root_fd=stage_root_fd,
            helper=helper,
            aggregate_budget=aggregate,
            exact_organic=exact_organic,
            arm_slot=checked_arm_slot,
            artifact_maxima=checked_artifact_maxima,
        )
        while worker_result is None:
            request = _receive_json(pair_parent.fileno())
            if request.get("action") == "WORKER_FAILED":
                _fail(
                    "formal calibration worker failed: "
                    f"{request.get('detail')}",
                )
            if request.get("action") == "WORKER_COMPLETE":
                worker_result = cast(dict[str, object], request["result"])
                break
            received = helper.recv_fd(pair_parent.fileno())
            try:
                if request.get("kind") == "append" or (
                    request.get("kind") is None
                    and request.get("artifact_class") == "ledger"
                ):
                    result = calibration_broker.publish(request, received)
                elif request.get("kind") in {"model", "regular"}:
                    result = calibration_broker.publish_regular(
                        request,
                        received,
                    )
                elif request.get("artifact_class") == "model":
                    maximum = request.get("maximum_bytes")
                    if type(maximum) is not int:
                        _fail("calibration model maximum is malformed")
                    result = calibration_broker.publish_model(
                        received,
                        maximum=maximum,
                    )
                else:
                    _fail("calibration broker artifact class differs")
            finally:
                os.close(received)
            response = {"result": result, "status": "PUBLISHED"}
            _send_all(
                pair_parent.fileno(),
                len(_canonical(response)).to_bytes(4, "big") + _canonical(response),
            )
        waited, status = os.waitpid(pid, 0)
        worker_waited = True
        if waited != pid or os.waitstatus_to_exitcode(status) != 0:
            _fail("formal calibration worker failed closed")
    except BaseException as exc:
        primary = exc
    finally:
        cleanup_actions: list[tuple[str, object]] = []
        if not pair_child_close_attempted:
            pair_child_close_attempted = True
            cleanup_actions.append(
                ("calibration worker child socket", pair_child.close)
            )
        if not pair_parent_close_attempted:
            pair_parent_close_attempted = True
            cleanup_actions.append(
                ("calibration worker parent control", pair_parent.close)
            )
        if not binary_fd_close_attempted:
            binary_fd_close_attempted = True
            cleanup_actions.append(
                (
                    "calibration native-helper binary descriptor",
                    lambda: os.close(binary_fd),
                )
            )
        for label, raw_cleanup in cleanup_actions:
            cleanup = cast(Any, raw_cleanup)
            try:
                cleanup()
            except BaseException as cleanup_error:
                if primary is None:
                    primary = cleanup_error
                else:
                    primary.add_note(
                        f"{label} cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
        if not worker_waited:
            try:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                while True:
                    try:
                        waited, _status = os.waitpid(pid, 0)
                        break
                    except InterruptedError:
                        continue
                if waited != pid:
                    _fail("calibration cleanup reaped a different child")
                worker_waited = True
            except BaseException as cleanup_error:
                if primary is None:
                    primary = cleanup_error
                else:
                    primary.add_note(
                        "calibration exact-child cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
    if primary is not None:
        raise primary
    assert worker_result is not None
    assert calibration_broker is not None
    return {
        "bounded_operations": worker_result,
        "budget": {
            "aggregate_budget_bytes": aggregate,
            "reserved_bytes": calibration_broker.reserved,
        },
        "stage": "FORMAL_ORGANIC_ARM",
        "status": (
            "PASS_EXACT_PRODUCTION_CALL_GRAPH_NO_AUTHORITY"
            if exact_organic
            else "PASS_NO_AUTHORITY_PUBLICATION"
        ),
        "workload_kind": (
            "EXACT_ORGANIC_PRODUCTION_CALL_GRAPH_V1"
            if exact_organic
            else "BOUNDED_PROXY_V1"
        ),
    }


def run_from_retained_package(
    *,
    stage: str,
    package_root_fd: int,
    package_receipt: Mapping[str, object],
    fixture_fd: int,
    stage_root_fd: int,
    result_fd: int,
) -> dict[str, object]:
    fixture = _strict_json(
        _read_fd(fixture_fd, MAX_FIXTURE_BYTES, "calibration fixture"),
        "calibration fixture",
    )
    if stage == "GATE_B_QUALIFICATION":
        stage_result = _gate_b_workload(
            fixture,
            package_root_fd=package_root_fd,
            package_receipt=package_receipt,
        )
    elif stage == "FORMAL_ORGANIC_ARM":
        stage_result = _formal_workload(
            fixture,
            package_root_fd=package_root_fd,
            package_receipt=package_receipt,
            stage_root_fd=stage_root_fd,
        )
    else:
        _fail(f"unknown calibration workload stage: {stage!r}")
    result: dict[str, object] = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "result": stage_result,
        "schema_version": RESULT_SCHEMA,
        "status": "PASS_NO_AUTHORITY",
        "workload_fidelity": {
            "class": (
                "EXACT_GATE_B_QUALIFICATION_NO_PUBLICATION"
                if stage == "GATE_B_QUALIFICATION"
                else (
                    "EXACT_FORMAL_ORGANIC_ARM_PRODUCTION_CALL_GRAPH"
                    if fixture.get("schema_version")
                    == EXACT_FORMAL_FIXTURE_SCHEMA
                    else "FORMAL_BOUNDED_PROXY_NO_ORGANIC_ARM"
                )
            ),
            "launch_admissible": (
                stage == "GATE_B_QUALIFICATION"
                or (
                    stage == "FORMAL_ORGANIC_ARM"
                    and fixture.get("schema_version")
                    == EXACT_FORMAL_FIXTURE_SCHEMA
                )
            ),
        },
    }
    _write_frame(result_fd, result)
    return result
