#!/usr/bin/env python3
"""Two-gate bootstrap for one prospective non-certified-cuts AB16 campaign.

Gate A can create only an offline, non-authorizing candidate that freezes the
planned external source set.  A distinct Gate B must bind the exact Gate-A
receipt and candidate bytes before this module may call the unchanged Gate-1
v4 authority API.  The resulting root therefore retains the complete Gate-1
four-unit suite, continuation slot, common-prestate/bindings paths, and the
reserved prospective AB16 topology.

This module creates authority bytes only.  It never starts a unit, solver, arm,
or experiment.
"""

from __future__ import annotations

import argparse
import atexit
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import threading
import types
from typing import Any
import unicodedata
import zipfile


V4_RESEARCH_DIR = Path(__file__).resolve().parents[1] / "noncert_cuts_ab_trust_gate1_v4_20260724"
V4_AUTHORITY_PATH = V4_RESEARCH_DIR / "campaign_authority_v4.py"


GATE_A_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-a-receipt-v2"
CANDIDATE_SCHEMA = "noncert-cuts-ab16-bootstrap-offline-candidate-v2"
GATE_B_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-b-approval-v4"
GATE_B_EPOCH_SCHEMA = "noncert-cuts-ab16-gate-b-epoch-observation-v3"
CAPTURE_SCHEMA = "noncert-cuts-ab16-bootstrap-manager-capture-v2"
RESULT_SCHEMA = "noncert-cuts-ab16-campaign-bootstrap-result-v3"
PATH_PREREGISTRATION_SCHEMA = "noncert-cuts-ab16-path-preregistration-v4"
FINAL_FULL_PREFLIGHT_SCHEMA = "noncert-cuts-ab16-gate-a-full-preflight-receipt-v3"
REPOSITORY_SNAPSHOT_SCHEMA = "noncert-cuts-ab16-repository-snapshot-v1"
SNAPSHOT_MATERIALIZATION_SCHEMA = "noncert-cuts-ab16-repository-snapshot-materialization-v1"
EXTERNAL_PLATFORM_SCHEMA = "noncert-cuts-ab16-external-platform-assumptions-v2"

GATE_A_PURPOSE = "AB16_OFFLINE_SOURCE_SET_PREFLIGHT"
CANDIDATE_PURPOSE = "AB16_OFFLINE_NONAUTHORIZING_CANDIDATE"
GATE_B_PURPOSE = "AB16_FORMAL_CAMPAIGN_IDENTITY_CREATION"
GATE_B_EPOCH_PURPOSE = "AB16_GATE_B_MANAGER_EPOCH_OBSERVATION"
FINAL_FULL_PREFLIGHT_PURPOSE = "AB16_GATE_A_FULL_PREFLIGHT"
PATH_PREREGISTRATION_PURPOSE = "prospective_noncert_cuts_ab16_path_authority"
FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY = "same-fd-python-prefix-and-nested-executable-v2"
FINAL_FULL_PREFLIGHT_TIMEOUT_SCALE = "12"
FINAL_FULL_PREFLIGHT_KEYS = {
    "authorizations",
    "authority_ready_identity",
    "command",
    "detached_replay_identity",
    "duration_monotonic_ns",
    "exit_code",
    "finished_at_utc",
    "planned_source_set_digest",
    "pre_run_authority_identity",
    "preflight_script_identity",
    "preflight_timeout_scale",
    "purpose",
    "python_identity",
    "repository_head",
    "repository_root",
    "runner_tool_identity",
    "schema_version",
    "started_at_utc",
    "status",
    "stderr_identity",
    "stdout_identity",
    "timed_out",
}

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_NONCE_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{4,123}\Z")
APPROVAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{5,127}\Z")

GATE_B_OWNER_EXECUTION_STRATEGY = "persistent-owner-sealed-fd-oexcl-bootstrap-handoff-v1"
GATE_B_HANDOFF_REQUEST_SCHEMA = "noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v1"
GATE_B_HANDOFF_RESPONSE_SCHEMA = "noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v1"
GATE_B_QUALIFICATION_LOCK_PATHS = (
    "/tmp/zmd-pj-codex-heavy-validation.lock",
    "/run/user/1000/zmd_pj_prod_scale_solver.lock",
    "/run/user/1000/zmd-pj-prod-scale-solve.lock",
)
GATE_B_RETAINED_FD_ROLES = (
    "lock",
    "mechanical_publisher",
    "output_directory",
    "rendered_record",
    "renderer_source",
    "request",
)
SELECTED_BYTE_EXECUTION_STRATEGY = "selected-byte-python-loader-fd-v1"
OWNER_PUBLISH_EXECUTION_STRATEGY = "sealed-memfd-dirfd-oexcl-v1"

# These literals are part of the explicitly declared AB16 external-platform
# boundary.  Their canonical UTF-8 bytes are recorded in the sealed package.
# They do not parse campaign authority and do not replace the package verifier.
SELECTED_BYTE_LAUNCH_V1 = r"""
import hashlib
import json
import os
import stat
import sys

def fail(code):
    os.write(2, (code + "\n").encode("ascii"))
    raise SystemExit(125)

def read_selected(fd, expected, label):
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != expected["mode"]
        or before.st_size != expected["size_bytes"]
    ):
        fail(label + "_METADATA")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    after = os.fstat(fd)
    signature = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    if (
        any(getattr(before, field) != getattr(after, field) for field in signature)
        or size != expected["size_bytes"]
        or digest.hexdigest() != expected["sha256"]
    ):
        fail(label + "_IDENTITY")

if len(sys.argv) < 4:
    fail("ARGV")
transport = sys.argv[1]
try:
    expected = json.loads(sys.argv[2])
except Exception:
    fail("IDENTITY_JSON")
if set(expected) != {"authority", "loader", "python"}:
    fail("IDENTITY_KEYS")
if transport == "systemd-openfile":
    if (
        os.environ.get("LISTEN_PID") != str(os.getpid())
        or os.environ.get("LISTEN_FDS") != "3"
        or os.environ.get("LISTEN_FDNAMES") != "ab16-python:ab16-loader:ab16-authority"
    ):
        fail("OPENFILE_ENV")
elif transport != "direct":
    fail("TRANSPORT")
read_selected(3, expected["python"], "PYTHON")
read_selected(4, expected["loader"], "LOADER")
read_selected(5, expected["authority"], "AUTHORITY")
clean = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}
try:
    os.execve(
        "/proc/self/fd/3",
        [
            expected["python"]["path"],
            "-I",
            "-B",
            "/proc/self/fd/4",
            "--loader-identity",
            json.dumps(expected["loader"], sort_keys=True, separators=(",", ":")),
            "--authority-fd",
            "5",
            "--authority-identity",
            json.dumps(expected["authority"], sort_keys=True, separators=(",", ":")),
            *sys.argv[3:],
        ],
        clean,
    )
except Exception as exc:
    os.write(2, ("EXEC_FAILED:" + type(exc).__name__ + "\n").encode("ascii"))
    raise SystemExit(126)
""".strip()

OWNER_OEXCL_PUBLISH_V1 = r"""
import fcntl
import hashlib
import os
import stat
import sys

basename = sys.argv[1]
if len(sys.argv) == 2:
    source_fd, directory_fd, result_fd = 4, 5, 6
elif len(sys.argv) == 5:
    try:
        source_fd, directory_fd, result_fd = map(int, sys.argv[2:5])
    except ValueError:
        raise SystemExit(125)
else:
    raise SystemExit(125)
required_seals = 0x0001 | 0x0002 | 0x0004 | 0x0008
if not basename or "/" in basename or basename in {".", ".."}:
    raise SystemExit(125)
before = os.fstat(source_fd)
if (
    not stat.S_ISREG(before.st_mode)
    or before.st_nlink != 0
    or fcntl.fcntl(source_fd, 1034) & required_seals != required_seals
):
    raise SystemExit(125)
os.lseek(source_fd, 0, os.SEEK_SET)
raw = bytearray()
while True:
    chunk = os.read(source_fd, 1024 * 1024)
    if not chunk:
        break
    raw.extend(chunk)
after = os.fstat(source_fd)
signature = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid", "st_size", "st_mtime_ns", "st_ctime_ns")
if (
    any(getattr(before, field) != getattr(after, field) for field in signature)
    or len(raw) != before.st_size
    or fcntl.fcntl(source_fd, 1034) & required_seals != required_seals
):
    raise SystemExit(125)
# The final name is visible but remains non-ready until the sealed source
# bytes are durable and the publisher flips the mode to the fixed 0444 state.
fd = os.open(
    basename,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
    0o600,
    dir_fd=directory_fd,
)
try:
    view = memoryview(raw)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write")
        view = view[written:]
    os.fsync(fd)
    os.fchmod(fd, 0o444)
    os.fsync(fd)
finally:
    os.close(fd)
os.fsync(directory_fd)
check_fd = os.open(basename, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
try:
    check_before = os.fstat(check_fd)
    observed = bytearray()
    while True:
        chunk = os.read(check_fd, 1024 * 1024)
        if not chunk:
            break
        observed.extend(chunk)
    check_after = os.fstat(check_fd)
finally:
    os.close(check_fd)
if (
    any(getattr(check_before, field) != getattr(check_after, field) for field in signature)
    or bytes(observed) != bytes(raw)
    or len(observed) != check_before.st_size
    or not stat.S_ISREG(check_after.st_mode)
    or stat.S_IMODE(check_after.st_mode) != 0o444
    or check_after.st_nlink != 1
):
    raise SystemExit(125)
frame = "OK " + hashlib.sha256(raw).hexdigest() + " " + str(len(raw)) + "\n"
os.write(result_fd, frame.encode("ascii"))
""".strip()

GATE_B_OWNER_DRIVER_V1 = r"""
import hashlib
import json
import os
import stat
import sys

clean = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}
if dict(os.environ) != clean or len(sys.argv) < 4:
    raise SystemExit(125)
try:
    expected = json.loads(sys.argv[1])
    python_fd = int(sys.argv[2])
    owner_source_fd = int(sys.argv[3])
except Exception:
    raise SystemExit(125)
if (
    set(expected) != {"owner_source", "python"}
    or json.dumps(expected, ensure_ascii=False, separators=(",", ":"), sort_keys=True) != sys.argv[1]
):
    raise SystemExit(125)

def signature(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )

def selected(fd, identity, label):
    if (
        not isinstance(identity, dict)
        or set(identity) != {"mode", "path", "sha256", "size_bytes"}
        or not isinstance(identity["mode"], int)
        or not isinstance(identity["path"], str)
        or os.path.abspath(identity["path"]) != identity["path"]
        or not isinstance(identity["sha256"], str)
        or len(identity["sha256"]) != 64
        or any(ch not in "0123456789abcdef" for ch in identity["sha256"])
        or not isinstance(identity["size_bytes"], int)
        or identity["size_bytes"] < 0
    ):
        raise SystemExit(125)
    try:
        named = os.stat(identity["path"], follow_symlinks=False)
        before = os.fstat(fd)
    except OSError:
        raise SystemExit(125)
    if (
        not stat.S_ISREG(named.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or stat.S_IMODE(before.st_mode) != identity["mode"]
        or before.st_size != identity["size_bytes"]
        or signature(named) != signature(before)
    ):
        raise SystemExit(125)
    os.lseek(fd, 0, os.SEEK_SET)
    raw = bytearray()
    remaining = before.st_size
    while remaining:
        chunk = os.read(fd, min(1024 * 1024, remaining))
        if not chunk:
            raise SystemExit(125)
        raw.extend(chunk)
        remaining -= len(chunk)
    if os.read(fd, 1):
        raise SystemExit(125)
    after = os.fstat(fd)
    final_named = os.stat(identity["path"], follow_symlinks=False)
    if (
        signature(before) != signature(after)
        or signature(after) != signature(final_named)
        or len(raw) != identity["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != identity["sha256"]
    ):
        raise SystemExit(125)
    return bytes(raw), signature(after)

_python, python_signature = selected(python_fd, expected["python"], "python")
if signature(os.stat("/proc/self/exe")) != python_signature:
    raise SystemExit(125)
_owner_source, _owner_source_signature = selected(
    owner_source_fd,
    expected["owner_source"],
    "owner_source",
)
try:
    os.execve(
        "/proc/self/fd/" + str(python_fd),
        [
            expected["python"]["path"],
            "-I",
            "-B",
            "/proc/self/fd/" + str(owner_source_fd),
            "owner",
            *sys.argv[4:],
        ],
        clean,
    )
except Exception:
    raise SystemExit(126)
""".strip()

# This external owner is entered by exec, so the actor PID/starttime observed
# before admission remains the actor through selection.  It owns only the
# canonical render/validate/mechanical-publication protocol.  It has no
# supervisor, lock, unit, baseline, arm, or experiment capability.
FORMAL_LAUNCH_OWNER_DRIVER_V1 = r"""
import ctypes
import fcntl
import hashlib
import json
import os
import re
import socket
import stat
import sys

python_fd, publisher_fd, context_fd, control_fd = 3, 4, 5, 6
required_seals = 0x0001 | 0x0002 | 0x0004 | 0x0008
clean = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}
max_frame = 16 * 1024 * 1024
request_schema = "noncert-cuts-ab16-formal-launch-owner-request-v1"
response_schema = "noncert-cuts-ab16-formal-launch-owner-response-v1"
owner_role = "AB16_OWNER_FORMAL_LAUNCH_PUBLISHER_V1"
session_pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")

def canonical_text(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

def canonical(value):
    return canonical_text(value).encode("utf-8") + b"\n"

def pairs_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

def parse_canonical(raw, label):
    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError("invalid constant " + token)
            ),
        )
    except Exception:
        raise RuntimeError(label + "_JSON")
    if not isinstance(value, dict) or canonical(value) != raw:
        raise RuntimeError(label + "_CANONICAL")
    return value

def parse_argument(raw, label):
    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError("invalid constant " + token)
            ),
        )
    except Exception:
        raise RuntimeError(label + "_JSON")
    if not isinstance(value, dict) or canonical_text(value).encode("utf-8") != raw:
        raise RuntimeError(label + "_CANONICAL")
    return value

def message_identity(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

def signature(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )

def validate_message_identity(value, label):
    if (
        not isinstance(value, dict)
        or set(value) != {"sha256", "size_bytes"}
        or not isinstance(value["sha256"], str)
        or len(value["sha256"]) != 64
        or any(ch not in "0123456789abcdef" for ch in value["sha256"])
        or not isinstance(value["size_bytes"], int)
        or value["size_bytes"] <= 0
    ):
        raise RuntimeError(label + "_IDENTITY")
    return value

def validate_mode_identity(value, label):
    if (
        not isinstance(value, dict)
        or set(value) != {"mode", "path", "sha256", "size_bytes"}
        or not isinstance(value["mode"], int)
        or value["mode"] < 0
        or value["mode"] & ~0o7777
        or not isinstance(value["path"], str)
        or os.path.abspath(value["path"]) != value["path"]
        or not isinstance(value["sha256"], str)
        or len(value["sha256"]) != 64
        or any(ch not in "0123456789abcdef" for ch in value["sha256"])
        or not isinstance(value["size_bytes"], int)
        or value["size_bytes"] <= 0
    ):
        raise RuntimeError(label + "_IDENTITY")
    return value

def read_sealed(fd, expected, label):
    expected = validate_message_identity(expected, label)
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 0
        or fcntl.fcntl(fd, 1034) & required_seals != required_seals
        or before.st_size != expected["size_bytes"]
    ):
        raise RuntimeError(label + "_METADATA")
    os.lseek(fd, 0, os.SEEK_SET)
    raw = bytearray()
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        raw.extend(chunk)
    after = os.fstat(fd)
    if (
        signature(before) != signature(after)
        or fcntl.fcntl(fd, 1034) & required_seals != required_seals
        or message_identity(raw) != expected
    ):
        raise RuntimeError(label + "_DRIFT")
    return bytes(raw)

def read_named_selected(fd, expected, label):
    expected = validate_mode_identity(expected, label)
    try:
        named_before = os.stat(expected["path"], follow_symlinks=False)
        before = os.fstat(fd)
    except OSError:
        raise RuntimeError(label + "_STAT")
    if (
        not stat.S_ISREG(named_before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or signature(named_before) != signature(before)
        or stat.S_IMODE(before.st_mode) != expected["mode"]
        or before.st_size != expected["size_bytes"]
    ):
        raise RuntimeError(label + "_METADATA")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    after = os.fstat(fd)
    named_after = os.stat(expected["path"], follow_symlinks=False)
    if (
        signature(before) != signature(after)
        or signature(after) != signature(named_after)
        or size != expected["size_bytes"]
        or digest.hexdigest() != expected["sha256"]
    ):
        raise RuntimeError(label + "_DRIFT")

def open_selected(expected, label):
    expected = validate_mode_identity(expected, label)
    fd = os.open(expected["path"], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        read_named_selected(fd, expected, label)
    except BaseException:
        os.close(fd)
        raise
    return fd

def sealed_memfd(name, raw):
    libc = ctypes.CDLL(None, use_errno=True)
    create = libc.memfd_create
    create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    create.restype = ctypes.c_int
    fd = int(create(name.encode("ascii"), 0x0001 | 0x0002))
    if fd < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short memfd write")
            view = view[written:]
        os.lseek(fd, 0, os.SEEK_SET)
        fcntl.fcntl(fd, 1033, required_seals)
        if fcntl.fcntl(fd, 1034) & required_seals != required_seals:
            raise OSError("memfd sealing failed")
        return fd
    except BaseException:
        os.close(fd)
        raise

def wait_child(pid):
    waited, status = os.waitpid(pid, 0)
    if waited != pid:
        raise RuntimeError("CHILD_IDENTITY")
    return os.waitstatus_to_exitcode(status)

def read_bounded(fd, limit):
    raw = bytearray()
    while True:
        chunk = os.read(fd, min(1024 * 1024, limit + 1 - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
        if len(raw) > limit:
            raise RuntimeError("CHILD_OUTPUT_LIMIT")
    return bytes(raw)

def selected_child(role, role_argv, payload_fd):
    loader_fd = open_selected(selected["loader"], "LOADER")
    authority_fd = open_selected(selected["authority"], "AUTHORITY")
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    try:
        pid = os.fork()
        if pid == 0:
            try:
                os.close(read_fd)
                os.dup2(python_fd, 3, inheritable=True)
                os.dup2(loader_fd, 4, inheritable=True)
                os.dup2(authority_fd, 5, inheritable=True)
                os.dup2(payload_fd, 6, inheritable=True)
                os.dup2(write_fd, 1, inheritable=True)
                os.execve(
                    "/proc/self/fd/3",
                    [
                        selected["python"]["path"],
                        "-I",
                        "-B",
                        "-c",
                        selected_literal,
                        "direct",
                        selected_argument,
                        "--campaign-dir",
                        context["campaign_dir"],
                        "--role",
                        role,
                        "--",
                        *role_argv,
                    ],
                    clean,
                )
            except BaseException:
                os._exit(126)
        os.close(write_fd)
        write_fd = -1
        output = read_bounded(read_fd, max_frame)
        result = wait_child(pid)
        if result != 0:
            raise RuntimeError("SELECTED_" + role.upper().replace("-", "_") + "_FAILED")
        return output
    finally:
        for fd in (loader_fd, authority_fd, read_fd, write_fd):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

def publisher_child(rendered_fd, directory_fd, basename):
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    try:
        pid = os.fork()
        if pid == 0:
            try:
                os.close(read_fd)
                os.dup2(python_fd, 3, inheritable=True)
                os.dup2(rendered_fd, 4, inheritable=True)
                os.dup2(directory_fd, 5, inheritable=True)
                os.dup2(write_fd, 6, inheritable=True)
                os.execve(
                    "/proc/self/fd/3",
                    [
                        selected["python"]["path"],
                        "-I",
                        "-B",
                        "-c",
                        publisher_source,
                        basename,
                    ],
                    clean,
                )
            except BaseException:
                os._exit(126)
        os.close(write_fd)
        write_fd = -1
        result_frame = read_bounded(read_fd, 512)
        result = wait_child(pid)
        if result != 0:
            raise RuntimeError("PUBLISH_FAILED_OR_UNCERTAIN")
        return result_frame
    finally:
        for fd in (read_fd, write_fd):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

def readback(directory_fd, basename, output_path, rendered):
    fd = os.open(
        basename,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=directory_fd,
    )
    try:
        before = os.fstat(fd)
        raw = read_bounded(fd, max_frame)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (
        signature(before) != signature(after)
        or not stat.S_ISREG(after.st_mode)
        or stat.S_IMODE(after.st_mode) != 0o444
        or after.st_nlink != 1
        or raw != rendered
    ):
        raise RuntimeError("PUBLISH_READBACK")
    return {
        "path": output_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }

def process_starttime(pid):
    raw = open("/proc/" + str(pid) + "/stat", "rb", buffering=0).read()
    marker = raw.rfind(b") ")
    if marker < 0:
        raise RuntimeError("PROCESS_STAT")
    fields = raw[marker + 2:].split()
    if len(fields) <= 19:
        raise RuntimeError("PROCESS_STAT")
    return int(fields[19])

def send(value):
    control.send(canonical(value))

def stop(code):
    try:
        send(
            {
                "code": code,
                "schema_version": response_schema,
                "status": "FAIL_CLOSED",
            }
        )
    except BaseException:
        pass
    os.write(2, (code + "\n").encode("ascii", "replace"))
    raise SystemExit(125)

if dict(os.environ) != clean or len(sys.argv) != 4:
    raise SystemExit(125)
session_id = sys.argv[1]
if session_pattern.fullmatch(session_id) is None:
    raise SystemExit(125)
try:
    expected_context_identity = parse_argument(
        sys.argv[2].encode("utf-8"),
        "CONTEXT_IDENTITY",
    )
    expected_driver_identity = parse_argument(
        sys.argv[3].encode("utf-8"),
        "DRIVER_IDENTITY",
    )
    validate_message_identity(expected_context_identity, "CONTEXT")
    validate_message_identity(expected_driver_identity, "DRIVER")
    context_raw = read_sealed(
        context_fd,
        expected_context_identity,
        "CONTEXT",
    )
    context = parse_canonical(context_raw, "CONTEXT")
    if context.get("formal_launch_owner_driver_identity") != expected_driver_identity:
        raise RuntimeError("DRIVER_CONTEXT_JOIN")
    publisher_expected = validate_message_identity(
        context.get("mechanical_oexcl_publisher_identity"),
        "PUBLISHER",
    )
    publisher_raw = read_sealed(publisher_fd, publisher_expected, "PUBLISHER")
    publisher_source = publisher_raw.decode("utf-8")
    outer_spec = context.get("outer_spec")
    if not isinstance(outer_spec, dict):
        raise RuntimeError("OUTER_SPEC")
    selected_argv = outer_spec.get("selected_byte_argv")
    if (
        not isinstance(selected_argv, list)
        or len(selected_argv) < 7
        or selected_argv[:4] != ["/proc/self/fd/3", "-I", "-B", "-c"]
        or selected_argv[5] != "systemd-openfile"
        or not isinstance(selected_argv[4], str)
        or not isinstance(selected_argv[6], str)
    ):
        raise RuntimeError("SELECTED_ARGV")
    selected_literal = selected_argv[4]
    if message_identity(selected_literal.encode("utf-8")) != validate_message_identity(
        context.get("selected_byte_launch_identity"),
        "SELECTED_LITERAL",
    ):
        raise RuntimeError("SELECTED_LITERAL_JOIN")
    selected_argument = selected_argv[6]
    selected = parse_argument(
        selected_argument.encode("utf-8"),
        "SELECTED_IDENTITIES",
    )
    if set(selected) != {"authority", "loader", "python"}:
        raise RuntimeError("SELECTED_IDENTITY_KEYS")
    for name in ("authority", "loader", "python"):
        selected[name] = validate_mode_identity(selected[name], name.upper())
    if {
        key: selected["python"][key]
        for key in ("path", "sha256", "size_bytes")
    } != context.get("python_identity"):
        raise RuntimeError("PYTHON_CONTEXT_JOIN")
    read_named_selected(python_fd, selected["python"], "PYTHON")
    if signature(os.stat("/proc/self/exe")) != signature(os.fstat(python_fd)):
        raise RuntimeError("PYTHON_RUNTIME")
    for field in (
        "campaign_dir",
        "formal_admission_path",
        "formal_selection_path",
        "formal_attempt_dir",
        "guardian_ready_path",
    ):
        value = context.get(field)
        if not isinstance(value, str) or os.path.abspath(value) != value:
            raise RuntimeError("CONTEXT_PATH_" + field.upper())
    control = socket.socket(fileno=control_fd)
    if control.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET:
        raise RuntimeError("CONTROL_SOCKET")
except BaseException as exc:
    os.write(2, ("STARTUP_" + type(exc).__name__ + ":" + str(exc) + "\n").encode("ascii", "replace"))
    raise SystemExit(125)

actor = {
    "pid": os.getpid(),
    "role": owner_role,
    "session_id": session_id,
    "starttime": process_starttime(os.getpid()),
}
send(
    {
        "actor": actor,
        "schema_version": response_schema,
        "status": "READY",
    }
)

for expected_sequence, expected_kind in ((1, "admission"), (2, "selection")):
    try:
        request_raw = control.recv(max_frame + 1)
        if not request_raw or len(request_raw) > max_frame:
            stop("REQUEST_SIZE")
        request = parse_canonical(request_raw, "REQUEST")
        if (
            set(request) != {"draft", "kind", "schema_version", "sequence"}
            or request["schema_version"] != request_schema
            or request["sequence"] != expected_sequence
            or request["kind"] != expected_kind
            or not isinstance(request["draft"], dict)
        ):
            stop("REQUEST_SEQUENCE")
        draft = request["draft"]
        publisher = draft.get("publisher")
        if (
            not isinstance(publisher, dict)
            or publisher.get("actor") != actor
        ):
            stop("ACTOR_IDENTITY")
        prerequisites = (
            []
            if expected_kind == "admission"
            else [
                "--admission",
                context["formal_admission_path"],
                "--guardian-ready",
                context["guardian_ready_path"],
                "--attempt-consumption",
                os.path.join(
                    context["formal_attempt_dir"],
                    "attempt-consumption.json",
                ),
            ]
        )
        draft_fd = sealed_memfd(
            "ab16-formal-" + expected_kind + "-draft",
            canonical(draft),
        )
        try:
            rendered = selected_child(
                "formal-launch-authority",
                [
                    "--campaign-dir",
                    context["campaign_dir"],
                    "--draft",
                    "/proc/self/fd/6",
                    "--kind",
                    expected_kind,
                    *prerequisites,
                ],
                draft_fd,
            )
        finally:
            os.close(draft_fd)
        rendered_record = parse_canonical(rendered, "RENDERED")
        if rendered_record.get("publisher", {}).get("actor") != actor:
            stop("RENDERED_ACTOR_IDENTITY")
        rendered_fd = sealed_memfd(
            "ab16-formal-" + expected_kind + "-rendered",
            rendered,
        )
        try:
            validation_raw = selected_child(
                "formal-launch-validator",
                [
                    "--campaign-dir",
                    context["campaign_dir"],
                    "--candidate",
                    "/proc/self/fd/6",
                    "--kind",
                    expected_kind,
                    *prerequisites,
                ],
                rendered_fd,
            )
            validation = parse_canonical(validation_raw, "VALIDATION")
            expected_candidate = {
                "path": "/proc/self/fd/6",
                "sha256": hashlib.sha256(rendered).hexdigest(),
                "size_bytes": len(rendered),
            }
            if validation != {
                "candidate_identity": expected_candidate,
                "kind": expected_kind,
                "status": "PASS",
            }:
                stop("VALIDATION_RESULT")
            output_path = (
                context["formal_admission_path"]
                if expected_kind == "admission"
                else context["formal_selection_path"]
            )
            parent = os.path.dirname(output_path)
            basename = os.path.basename(output_path)
            if not basename or basename in {".", ".."}:
                stop("OUTPUT_BASENAME")
            directory_fd = os.open(
                parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                expected_frame = (
                    "OK "
                    + hashlib.sha256(rendered).hexdigest()
                    + " "
                    + str(len(rendered))
                    + "\n"
                ).encode("ascii")
                actual_frame = publisher_child(
                    rendered_fd,
                    directory_fd,
                    basename,
                )
                if actual_frame != expected_frame:
                    stop("PUBLISH_RESULT_UNCERTAIN")
                published_identity = readback(
                    directory_fd,
                    basename,
                    output_path,
                    rendered,
                )
            finally:
                os.close(directory_fd)
        finally:
            os.close(rendered_fd)
        send(
            {
                "actor": actor,
                "artifact_identity": published_identity,
                "kind": expected_kind,
                "schema_version": response_schema,
                "sequence": expected_sequence,
                "status": "PUBLISHED",
            }
        )
    except SystemExit:
        raise
    except BaseException as exc:
        stop(type(exc).__name__ + "_" + str(exc))

try:
    handoff_raw = control.recv(max_frame + 1)
    if not handoff_raw or len(handoff_raw) > max_frame:
        stop("HANDOFF_SIZE")
    handoff = parse_canonical(handoff_raw, "HANDOFF")
    if handoff != {
        "kind": "handoff-complete",
        "schema_version": request_schema,
        "sequence": 3,
    }:
        stop("HANDOFF_SEQUENCE")
    send(
        {
            "actor": actor,
            "schema_version": response_schema,
            "sequence": 3,
            "status": "HANDOFF_COMPLETE",
        }
    )
except SystemExit:
    raise
except BaseException as exc:
    stop(type(exc).__name__ + "_" + str(exc))

control.close()
raise SystemExit(0)
""".strip()

V4_SCRIPT_TOOL_FILES: dict[str, str] = {
    "campaign_authority_v4": "campaign_authority_v4.py",
    "gate1_campaign_bootstrap_v4": "gate1_campaign_bootstrap_v4.py",
    "gate1_campaign_driver_v4": "gate1_campaign_driver_v4.py",
    "gate1_campaign_execution_v4": "gate1_campaign_execution_v4.py",
    "gate1_payload_v4": "gate1_payload_v4.py",
    "gate1_unit_orchestrator_v4": "gate1_unit_orchestrator_v4.py",
    "independent_arithmetic_v4": "independent_arithmetic_v4.py",
    "manager_attestor_v4": "manager_attestor_v4.py",
    "positive_control_formal_v4": "positive_control_formal_v4.py",
    "positive_control_v4": "positive_control_v4.py",
    "positive_control_gate_v4": "positive_control_gate_v4.py",
    "resource_lifecycle_v4": "resource_lifecycle_v4.py",
    "resource_verifier_v4": "resource_verifier_v4.py",
}
AB16_SCRIPT_TOOL_FILES: dict[str, str] = {
    "ab16_authority_v1": "ab16_authority_v1.py",
    "ab16_authority_v2": "ab16_authority_v2.py",
    "ab16_campaign_bootstrap_v1": "ab16_campaign_bootstrap_v1.py",
    "ab16_campaign_bootstrap_v2": "ab16_campaign_bootstrap_v2.py",
    "ab16_contract_v1": "ab16_contract_v1.py",
    "ab16_formal_campaign_v1": "ab16_formal_campaign_v1.py",
    "ab16_formal_controller_v1": "ab16_formal_controller_v1.py",
    "ab16_formal_launch_authority_v1": "ab16_formal_launch_authority_v1.py",
    "ab16_formal_launch_validator_v1": "ab16_formal_launch_validator_v1.py",
    "ab16_formal_loader_v1": "ab16_formal_loader_v1.py",
    "ab16_formal_orchestrator_v1": "ab16_formal_orchestrator_v1.py",
    "ab16_formal_success_verifier_v1": "ab16_formal_success_verifier_v1.py",
    "ab16_gate_b_qualification_v1": "ab16_gate_b_qualification_v1.py",
    "ab16_outer_closeout_state_v1": "ab16_outer_closeout_state_v1.py",
    "ab16_outer_guardian_v1": "ab16_outer_guardian_v1.py",
    "ab16_outer_refunit_closeout_v1": "ab16_outer_refunit_closeout_v1.py",
    "ab16_terminal_gate_v1": "ab16_terminal_gate_v1.py",
    "ab16_terminal_gate_v2": "ab16_terminal_gate_v2.py",
    "baseline_admission_v1": "baseline_admission_v1.py",
    "baseline_rebuild_v1": "baseline_rebuild_v1.py",
    "cut_free_incumbent_replay_v1": "cut_free_incumbent_replay_v1.py",
    "disposable_drill_authority_v1": "disposable_drill_authority_v1.py",
    "disposable_drill_authority_v2": "disposable_drill_authority_v2.py",
    "disposable_drill_payload_v1": "disposable_drill_payload_v1.py",
    "gate_a_pinned_entrypoint_v2": "gate_a_pinned_entrypoint_v2.py",
    "gate_a_recovery_inputs_v1": "gate_a_recovery_inputs_v1.py",
    "gate_a_validation_v2": "gate_a_validation_v2.py",
    "organic_arm_replay_v1": "organic_arm_replay_v1.py",
    "organic_arm_runner_v1": "organic_arm_runner_v1.py",
    "organic_resource_lifecycle_v1": "organic_resource_lifecycle_v1.py",
    "organic_resource_lifecycle_v2": "organic_resource_lifecycle_v2.py",
    "organic_resource_verifier_v1": "organic_resource_verifier_v1.py",
    "organic_resource_verifier_v2": "organic_resource_verifier_v2.py",
    "organic_unit_orchestrator_v1": "organic_unit_orchestrator_v1.py",
    "organic_unit_orchestrator_v2": "organic_unit_orchestrator_v2.py",
    "systemd_unit_reference_v1": "systemd_unit_reference_v1.py",
}
SCRIPT_TOOL_FILES = {**V4_SCRIPT_TOOL_FILES, **AB16_SCRIPT_TOOL_FILES}

STRICT_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "cuts_mandatory_schedule",
        "history_freeze_manifest",
        "legacy_control_a002",
        "mandatory_instances",
        "preflight_gate",
        "project_lock",
    }
)
EXTERNAL_STRICT_INPUT_ROLES = frozenset(
    {
        "history_freeze_manifest",
        "legacy_control_a002",
    }
)
SYSTEM_TOOL_ROLES = frozenset(
    {
        "attestor_python",
        "busctl",
        "git",
        "libsystemd",
        "python3_13",
        "sudo",
        "systemctl",
        "systemd_run",
    }
)
JSON_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "history_freeze_manifest",
        "legacy_control_a002",
        "mandatory_instances",
    }
)
CANONICAL_JSON_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "history_freeze_manifest",
        "mandatory_instances",
    }
)

GATE_INPUT_ROLES = {
    "ab16_gate_a_receipt": "input.ab16_gate_a_receipt.json",
    "ab16_offline_candidate": "input.ab16_offline_candidate.json",
    "ab16_gate_b_approval": "input.ab16_gate_b_approval.json",
    "ab16_gate_b_epoch_observation": "input.ab16_gate_b_epoch_observation.json",
    "ab16_gate_b_final_full_preflight": "input.ab16_gate_b_final_full_preflight.json",
}
CAPTURE_INPUT_ROLE = "ab16_bootstrap_manager_epoch_capture"
CAPTURE_PACKAGE_ROLE = "input.ab16_bootstrap_manager_epoch_capture.json"
PATH_PREREGISTRATION_INPUT_ROLE = "ab16_path_preregistration"
PATH_PREREGISTRATION_PACKAGE_ROLE = "input.ab16_path_preregistration.json"
SNAPSHOT_MANIFEST_INPUT_ROLE = "ab16_repository_snapshot"
SNAPSHOT_MANIFEST_PACKAGE_ROLE = "input.ab16_repository_snapshot.json"
SNAPSHOT_ARCHIVE_INPUT_ROLE = "ab16_repository_snapshot_archive"
SNAPSHOT_ARCHIVE_PACKAGE_ROLE = "input.ab16_repository_snapshot.zip"
SNAPSHOT_MATERIALIZATION_INPUT_ROLE = "ab16_repository_snapshot_materialization"
EXTERNAL_PLATFORM_INPUT_ROLE = "ab16_external_platform_assumptions"
EXTERNAL_PLATFORM_PACKAGE_ROLE = "input.ab16_external_platform_assumptions.json"


class BootstrapError(RuntimeError):
    """A staged bootstrap precondition failed closed."""


def _fd_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_stable_fd(descriptor: int, *, limit: int, label: str) -> bytes:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 <= before.st_size <= limit:
        raise BootstrapError(f"{label} is not one bounded regular file")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = before.st_size
    while remaining:
        chunk = os.read(descriptor, min(1 << 20, remaining))
        if not chunk:
            raise BootstrapError(f"{label} was truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1):
        raise BootstrapError(f"{label} grew during read")
    if _fd_signature(before) != _fd_signature(os.fstat(descriptor)):
        raise BootstrapError(f"{label} changed during same-FD read")
    return b"".join(chunks)


def _verify_bootstrap_git(binding: Mapping[str, Any]) -> None:
    git_fd = int(binding["git_fd"])
    parent_fd = int(binding["git_parent_fd"])
    metadata = os.fstat(git_fd)
    named = os.stat(str(binding["git_name"]), dir_fd=parent_fd, follow_symlinks=False)
    proc = os.stat(f"/proc/self/fd/{git_fd}")
    parent = os.fstat(parent_fd)
    if (
        _fd_signature(metadata) != binding["git_signature"]
        or _fd_signature(named) != binding["git_signature"]
        or _fd_signature(proc) != binding["git_signature"]
        or _fd_signature(parent) != binding["git_parent_signature"]
        or hashlib.sha256(_read_stable_fd(git_fd, limit=1 << 30, label="bootstrap Git")).hexdigest()
        != binding["git_sha256"]
    ):
        raise BootstrapError("retained bootstrap Git identity drifted")


def _bootstrap_git(
    binding: Mapping[str, Any],
    *arguments: str,
    input_bytes: bytes | None = None,
    output_limit: int = 128 << 20,
) -> bytes:
    _verify_bootstrap_git(binding)
    try:
        completed = subprocess.run(
            ["git", "-C", str(binding["repository_root"]), *arguments],
            check=False,
            close_fds=True,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin"},
            executable=f"/proc/self/fd/{binding['git_fd']}",
            input=input_bytes,
            pass_fds=(int(binding["git_fd"]),),
            stdin=None if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapError(f"retained bootstrap Git execution failed: {exc}") from exc
    _verify_bootstrap_git(binding)
    if completed.returncode != 0 or completed.stderr or len(completed.stdout) > output_limit:
        raise BootstrapError(
            f"retained bootstrap Git command failed closed: {arguments!r}; "
            f"exit={completed.returncode}; stderr={completed.stderr!r}"
        )
    return completed.stdout


def _close_bootstrap_binding(binding: Mapping[str, Any]) -> None:
    for field in ("git_fd", "git_parent_fd"):
        descriptor = binding.get(field)
        if type(descriptor) is int:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _load_authority_from_fixed_head() -> tuple[types.ModuleType, dict[str, Any]]:
    repository = Path(__file__).resolve().parents[3]
    selected = shutil.which("git")
    if selected is None:
        raise BootstrapError("Git is required by the sole pre-package executor")
    git_path = Path(os.path.realpath(selected))
    parent_fd = os.open(git_path.parent, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        git_fd = os.open(git_path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)
    except BaseException:
        os.close(parent_fd)
        raise
    try:
        metadata = os.fstat(git_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or stat.S_IMODE(metadata.st_mode) & 0o111 == 0:
            raise BootstrapError("bootstrap Git is not one executable regular file")
        binding: dict[str, Any] = {
            "git_fd": git_fd,
            "git_name": git_path.name,
            "git_parent_fd": parent_fd,
            "git_parent_signature": _fd_signature(os.fstat(parent_fd)),
            "git_path": str(git_path),
            "git_sha256": hashlib.sha256(
                _read_stable_fd(git_fd, limit=1 << 30, label="bootstrap Git")
            ).hexdigest(),
            "git_signature": _fd_signature(metadata),
            "repository_root": str(repository),
        }
        top = _bootstrap_git(binding, "rev-parse", "--show-toplevel", output_limit=4096).decode("utf-8").strip()
        if Path(top) != repository:
            raise BootstrapError("pre-package executor is not at the exact Git top level")
        head = _bootstrap_git(binding, "rev-parse", "--verify", "HEAD^{commit}", output_limit=128).decode().strip()
        tree = _bootstrap_git(binding, "rev-parse", "--verify", "HEAD^{tree}", output_limit=128).decode().strip()
        if GIT_SHA_RE.fullmatch(head) is None or GIT_SHA_RE.fullmatch(tree) is None:
            raise BootstrapError("pre-package Git HEAD/tree identity is malformed")
        relative = V4_AUTHORITY_PATH.relative_to(repository).as_posix()
        source = _bootstrap_git(binding, "show", f"{head}:{relative}", output_limit=16 << 20)
        module = types.ModuleType("_ab16_campaign_authority_v4_git_object")
        module.__file__ = f"{repository}/.git-object/{head}/{relative}"
        module.__package__ = None
        sys.modules[module.__name__] = module
        try:
            exec(compile(source, module.__file__, "exec", dont_inherit=True), module.__dict__)
        except BaseException:
            sys.modules.pop(module.__name__, None)
            raise
        binding.update({"authority_bytes": source, "repository_head": head, "repository_tree": tree})
        return module, binding
    except BaseException:
        os.close(git_fd)
        os.close(parent_fd)
        raise


_PREPACKAGE_STATE: tuple[types.ModuleType, dict[str, Any]] | None = None
_PREPACKAGE_STATE_LOCK = threading.Lock()


def _prepackage_state() -> tuple[types.ModuleType, dict[str, Any]]:
    global _PREPACKAGE_STATE
    if _PREPACKAGE_STATE is not None:
        return _PREPACKAGE_STATE
    if not _is_live_prepackage_closure_entry():
        raise BootstrapError(
            "pre-package authority is unavailable outside the exact live checkout entry"
        )
    with _PREPACKAGE_STATE_LOCK:
        if _PREPACKAGE_STATE is None:
            if not _is_live_prepackage_closure_entry():
                raise BootstrapError(
                    "pre-package authority is unavailable outside the exact live checkout entry"
                )
            loaded = _load_authority_from_fixed_head()
            _PREPACKAGE_STATE = loaded
            atexit.register(_close_bootstrap_binding, loaded[1])
    assert _PREPACKAGE_STATE is not None
    return _PREPACKAGE_STATE


class _LazyAuthority:
    """Expose the live Git authority only when a pre-package API needs it."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_prepackage_state()[0], name)


class _LazyBootstrapBinding(Mapping[str, Any]):
    """Delay the retained Git binding while package consumers read literals."""

    def __getitem__(self, key: str) -> Any:
        return _prepackage_state()[1][key]

    def __iter__(self) -> Iterator[str]:
        return iter(_prepackage_state()[1])

    def __len__(self) -> int:
        return len(_prepackage_state()[1])


authority: Any = _LazyAuthority()
_BOOTSTRAP_BINDING: Mapping[str, Any] = _LazyBootstrapBinding()


def _live_prepackage_repository(*, allow_retained_fd: bool) -> Path | None:
    raw_source = Path(os.path.abspath(__file__))
    try:
        source_metadata = os.lstat(raw_source)
    except OSError as exc:
        raise BootstrapError("pre-package source metadata cannot be inspected") from exc
    if stat.S_ISREG(source_metadata.st_mode):
        source = raw_source.resolve(strict=False)
        if raw_source != source:
            return None
    elif (
        allow_retained_fd
        and stat.S_ISLNK(source_metadata.st_mode)
        and raw_source.parent == Path("/proc/self/fd")
        and raw_source.name.isdecimal()
    ):
        descriptor = int(raw_source.name)
        try:
            retained = os.fstat(descriptor)
            source = raw_source.resolve(strict=True)
            named = os.stat(source, follow_symlinks=False)
        except OSError as exc:
            raise BootstrapError(
                "retained pre-package source identity cannot be inspected"
            ) from exc
        if (
            not stat.S_ISREG(retained.st_mode)
            or retained.st_nlink != 1
            or _fd_signature(retained) != _fd_signature(named)
        ):
            return None
    else:
        return None
    repository = source.parents[3]
    expected = (
        repository
        / "docs"
        / "research"
        / "noncert_cuts_ab16_20260724"
        / "ab16_campaign_bootstrap_v2.py"
    )
    if source != expected:
        return None
    git_metadata = repository / ".git"
    try:
        metadata = os.lstat(git_metadata)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise BootstrapError("pre-package Git metadata cannot be inspected") from exc
    if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
        return None
    return repository


def _is_live_prepackage_entry() -> bool:
    """Recognize only the directly imported tracked Git entry."""

    return _live_prepackage_repository(allow_retained_fd=False) is not None


def _is_live_prepackage_closure_entry() -> bool:
    """Also admit the same tracked source held open at ``/proc/self/fd/N``."""

    return _live_prepackage_repository(allow_retained_fd=True) is not None


# The tracked pre-package entry retains its historical import-time Git binding.
# Package payloads and the Git-free sealed repository snapshot need only the
# owner literals until a real pre-package API is requested.
if _is_live_prepackage_entry():
    _prepackage_state()


def _replay_prepackage_closure(*, planned: Mapping[str, Mapping[str, object]] | None = None) -> None:
    binding = _BOOTSTRAP_BINDING
    head = _bootstrap_git(binding, "rev-parse", "--verify", "HEAD^{commit}", output_limit=128).decode().strip()
    tree = _bootstrap_git(binding, "rev-parse", "--verify", "HEAD^{tree}", output_limit=128).decode().strip()
    status_bytes = _bootstrap_git(
        binding,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=no",
        output_limit=1 << 20,
    )
    repository = Path(str(binding["repository_root"]))
    bootstrap_relative = Path(__file__).resolve().relative_to(repository).as_posix()
    authority_relative = V4_AUTHORITY_PATH.relative_to(repository).as_posix()
    bootstrap_head = _bootstrap_git(binding, "show", f"{head}:{bootstrap_relative}", output_limit=16 << 20)
    authority_head = _bootstrap_git(binding, "show", f"{head}:{authority_relative}", output_limit=16 << 20)
    current_fd = os.open(Path(__file__).resolve(), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        current = _read_stable_fd(current_fd, limit=16 << 20, label="pre-package executor")
    finally:
        os.close(current_fd)
    if (
        head != binding["repository_head"]
        or tree != binding["repository_tree"]
        or status_bytes
        or current != bootstrap_head
        or authority_head != binding["authority_bytes"]
    ):
        raise BootstrapError("pre-package HEAD/tree/clean/source closure drifted")
    if planned is not None:
        expected = planned.get("system.git")
        fields = {"device", "inode", "mode", "mode_octal", "path", "sha256", "size_bytes"}
        observed_mode = stat.S_IMODE(os.fstat(int(binding["git_fd"])).st_mode)
        observed = {
            "device": os.fstat(int(binding["git_fd"])).st_dev,
            "inode": os.fstat(int(binding["git_fd"])).st_ino,
            "mode": observed_mode,
            "mode_octal": f"{observed_mode:04o}",
            "path": binding["git_path"],
            "sha256": binding["git_sha256"],
            "size_bytes": os.fstat(int(binding["git_fd"])).st_size,
        }
        if not isinstance(expected, Mapping) or any(expected.get(field) != observed[field] for field in fields):
            raise BootstrapError("planned Git differs from the retained pre-package Git")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _utc(value: object, label: str) -> str:
    if type(value) is not str:
        raise BootstrapError(f"{label} must be an exact UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BootstrapError(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise BootstrapError(f"{label} is not UTC")
    return value


def _exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise BootstrapError(f"{label} key set drifted")
    return value


def _canonical_record(
    path: Path | str,
    label: str,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    snapshot = authority.snapshot_regular(path)
    value = authority.strict_loads(snapshot.data, label)
    if authority.canonical_json(value) != snapshot.data:
        raise BootstrapError(f"{label} is not canonical strict JSON")
    if not isinstance(value, Mapping):
        raise BootstrapError(f"{label} is not a JSON object")
    return value, authority.detached_identity(snapshot)


def _mode_identity(value: object, label: str) -> dict[str, object]:
    record = _exact_keys(value, {"mode", "path", "sha256", "size_bytes"}, f"{label} identity")
    if (
        type(record["mode"]) is not int
        or not 0 <= record["mode"] <= 0o7777
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or _absolute(record["path"]) != Path(record["path"])
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise BootstrapError(f"{label} identity is malformed")
    return dict(record)


def _snapshot_mode_identity(path: Path | str) -> dict[str, object]:
    snapshot = authority.snapshot_regular(path)
    return {"mode": stat.S_IMODE(snapshot.stat_result.st_mode), **authority.detached_identity(snapshot)}


def _canonical_mode_record(
    path: Path | str,
    label: str,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    value, _ = _canonical_record(path, label)
    return value, _snapshot_mode_identity(path)


def _unterminated_canonical_mode_record(
    path: Path | str,
    label: str,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    snapshot = authority.snapshot_regular(path)
    value = authority.strict_loads(snapshot.data, label)
    if authority.canonical_json(value)[:-1] != snapshot.data:
        raise BootstrapError(f"{label} is not canonical unterminated strict JSON")
    if not isinstance(value, Mapping):
        raise BootstrapError(f"{label} is not a JSON object")
    return value, {
        "mode": stat.S_IMODE(snapshot.stat_result.st_mode),
        **authority.detached_identity(snapshot),
    }


def _project_mode_identity(value: Mapping[str, object], label: str) -> dict[str, object]:
    try:
        projection = {field: value[field] for field in ("mode", "path", "sha256", "size_bytes")}
    except KeyError as exc:
        raise BootstrapError(f"{label} source identity is incomplete") from exc
    return _mode_identity(projection, label)


def _digest_without(record: Mapping[str, object], field: str) -> str:
    value = dict(record)
    value.pop(field, None)
    return hashlib.sha256(authority.canonical_json(value)).hexdigest()


def _source_set_digest(source_identities: Mapping[str, object]) -> str:
    return hashlib.sha256(authority.canonical_json(source_identities)).hexdigest()


def _script_paths() -> dict[str, Path]:
    ab16_dir = Path(__file__).resolve().parent
    paths: dict[str, Path] = {}
    for role, filename in V4_SCRIPT_TOOL_FILES.items():
        paths[role] = V4_RESEARCH_DIR / filename
    for role, filename in AB16_SCRIPT_TOOL_FILES.items():
        paths[role] = ab16_dir / filename
    if set(paths) != set(SCRIPT_TOOL_FILES):
        raise BootstrapError("script tool role construction drifted")
    for role, path in paths.items():
        authority.snapshot_regular(path)
        if path.suffix != ".py":
            raise BootstrapError(f"script tool {role} is not a Python source")
    if not authority.REQUIRED_GATE1_TOOL_ROLES <= (set(paths) | set(SYSTEM_TOOL_ROLES)):
        raise BootstrapError("script allowlist misses a mandatory Gate-1 role")
    return paths


def _exact_path_map(
    value: Mapping[str, Path | str],
    roles: frozenset[str],
    label: str,
) -> dict[str, Path]:
    if type(value) is not dict or set(value) != set(roles):
        raise BootstrapError(f"{label} must have the exact pre-registered roles")
    result: dict[str, Path] = {}
    for role, raw_path in value.items():
        if type(role) is not str or not isinstance(raw_path, (str, os.PathLike)):
            raise BootstrapError(f"{label}.{role!s} path is malformed")
        path = _absolute(raw_path)
        authority.snapshot_regular(path)
        result[role] = path
    return result


def _resolved_system_tools(
    paths: Mapping[str, Path | str],
) -> tuple[dict[str, Path], dict[str, dict[str, object]]]:
    if type(paths) is not dict or set(paths) != set(SYSTEM_TOOL_ROLES):
        raise BootstrapError("system tools must have the exact pre-registered roles")
    resolved: dict[str, Path] = {}
    identities: dict[str, dict[str, object]] = {}
    for role, raw_path in sorted(paths.items()):
        if type(role) is not str or not isinstance(raw_path, (str, os.PathLike)):
            raise BootstrapError(f"system tool {role!s} path is malformed")
        _, full = authority.snapshot_tool(raw_path)
        resolved[role] = Path(str(full["path"]))
        identities[role] = dict(full)
    return resolved, identities


def _planned_source_identities(
    *,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, Path],
    dict[str, Path],
    dict[str, Path],
]:
    strict_paths = _exact_path_map(
        strict_input_paths,
        STRICT_INPUT_ROLES,
        "strict inputs",
    )
    system_paths, system_identities = _resolved_system_tools(system_tool_paths)
    scripts = _script_paths()
    identities: dict[str, dict[str, object]] = {}
    for role, path in sorted(scripts.items()):
        identities[f"script.{role}"] = authority.full_identity(authority.snapshot_regular(path))
    for role, full in sorted(system_identities.items()):
        identities[f"system.{role}"] = full
    for role, path in sorted(strict_paths.items()):
        identities[f"input.{role}"] = authority.full_identity(authority.snapshot_regular(path))
    return identities, scripts, system_paths, strict_paths


def observe_planned_sources(
    *,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
) -> dict[str, object]:
    """Read-only Gate-A helper; it never creates a candidate or campaign."""

    identities, _, _, _ = _planned_source_identities(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    return {
        "planned_source_identities": identities,
        "planned_source_set_digest": _source_set_digest(identities),
    }


def _validate_gate_a(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "approval_id",
            "arm_launch_authorized",
            "created_at_utc",
            "decision",
            "disposable_authority_ready_identity",
            "disposable_detached_replay_identity",
            "formal_campaign_creation_authorized",
            "full_preflight_receipt_identity",
            "gate",
            "history_freeze_replay_identity",
            "manager_epoch",
            "offline_candidate_only",
            "planned_source_set_digest",
            "purpose",
            "reference_capability_identity",
            "reference_capability_transcript_identity",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "target_campaign_dir",
        },
        "Gate-A receipt",
    )
    _utc(record["created_at_utc"], "Gate-A created_at_utc")
    for field in (
        "disposable_authority_ready_identity",
        "disposable_detached_replay_identity",
        "full_preflight_receipt_identity",
        "history_freeze_replay_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
    ):
        identity = _exact_keys(
            record[field],
            {"mode", "path", "sha256", "size_bytes"},
            f"Gate-A {field}",
        )
        if (
            identity["mode"] != 0o444
            or type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] < 0
        ):
            raise BootstrapError(f"Gate-A {field} identity is malformed")
        observed = authority.snapshot_regular(identity["path"])
        if stat.S_IMODE(observed.stat_result.st_mode) != identity["mode"] or authority.detached_identity(observed) != {
            key: identity[key] for key in ("path", "sha256", "size_bytes")
        }:
            raise BootstrapError(f"Gate-A {field} bytes drifted")
    authority.validate_manager_epoch(record["manager_epoch"])
    if (
        record["schema_version"] != GATE_A_SCHEMA
        or record["purpose"] != GATE_A_PURPOSE
        or record["gate"] != "A"
        or record["decision"] != "PASS"
        or record["offline_candidate_only"] is not True
        or record["formal_campaign_creation_authorized"] is not False
        or record["arm_launch_authorized"] is not False
        or type(record["approval_id"]) is not str
        or APPROVAL_ID_RE.fullmatch(record["approval_id"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["run_nonce"]) is not str
        or RUN_NONCE_RE.fullmatch(record["run_nonce"]) is None
        or type(record["planned_source_set_digest"]) is not str
        or SHA256_RE.fullmatch(record["planned_source_set_digest"]) is None
        or type(record["target_campaign_dir"]) is not str
        or not Path(record["target_campaign_dir"]).is_absolute()
        or Path(record["target_campaign_dir"]).name != record["run_nonce"]
    ):
        raise BootstrapError("Gate-A receipt is not a non-authorizing PASS")
    return record


def _validate_source_identities(
    value: object,
) -> Mapping[str, Any]:
    expected_roles = {
        *(f"script.{role}" for role in SCRIPT_TOOL_FILES),
        *(f"system.{role}" for role in SYSTEM_TOOL_ROLES),
        *(f"input.{role}" for role in STRICT_INPUT_ROLES),
    }
    records = _exact_keys(value, expected_roles, "planned source identities")
    for role, identity in records.items():
        expected_keys = {
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "sha256",
            "size_bytes",
        }
        if role.startswith("system."):
            expected_keys.add("requested_path")
        item = _exact_keys(
            identity,
            expected_keys,
            f"planned source identity {role}",
        )
        if (
            type(item["path"]) is not str
            or not Path(item["path"]).is_absolute()
            or type(item["sha256"]) is not str
            or SHA256_RE.fullmatch(item["sha256"]) is None
            or type(item["size_bytes"]) is not int
            or item["size_bytes"] < 0
            or type(item["device"]) is not int
            or type(item["inode"]) is not int
            or type(item["mode"]) is not int
            or type(item["mode_octal"]) is not str
            or item["mode_octal"] != f"{item['mode']:04o}"
            or (
                role.startswith("system.")
                and (type(item["requested_path"]) is not str or not Path(item["requested_path"]).is_absolute())
            )
        ):
            raise BootstrapError(f"planned source identity {role} is malformed")
    return records


def validate_candidate(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "arm_launch_authorized",
            "candidate_id",
            "candidate_only",
            "created_at_utc",
            "formal_campaign_creation_authorized",
            "gate_a_receipt_identity",
            "path_preregistration_identity",
            "planned_source_identities",
            "planned_source_set_digest",
            "purpose",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "target_campaign_dir",
        },
        "offline candidate",
    )
    _utc(record["created_at_utc"], "candidate created_at_utc")
    authority.validate_detached_identity(
        record["gate_a_receipt_identity"],
        "candidate Gate-A receipt",
    )
    authority.validate_detached_identity(
        record["path_preregistration_identity"],
        "candidate AB16 path preregistration",
    )
    sources = _validate_source_identities(record["planned_source_identities"])
    if (
        record["schema_version"] != CANDIDATE_SCHEMA
        or record["purpose"] != CANDIDATE_PURPOSE
        or record["candidate_only"] is not True
        or record["formal_campaign_creation_authorized"] is not False
        or record["arm_launch_authorized"] is not False
        or type(record["candidate_id"]) is not str
        or record["candidate_id"] != _digest_without(record, "candidate_id")
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["run_nonce"]) is not str
        or RUN_NONCE_RE.fullmatch(record["run_nonce"]) is None
        or type(record["target_campaign_dir"]) is not str
        or not Path(record["target_campaign_dir"]).is_absolute()
        or Path(record["target_campaign_dir"]).name != record["run_nonce"]
        or record["planned_source_set_digest"] != _source_set_digest(sources)
    ):
        raise BootstrapError("offline candidate semantics drifted")
    return record


def _literal_identity(value: str) -> dict[str, object]:
    raw = value.encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _validate_literal_identity(value: object, expected: str, label: str) -> dict[str, object]:
    record = _exact_keys(value, {"sha256", "size_bytes"}, label)
    projected = dict(record)
    if projected != _literal_identity(expected):
        raise BootstrapError(f"{label} identity drifted")
    return projected


def _proc_starttime(pid: int) -> str:
    if type(pid) is not int or pid <= 1:
        raise BootstrapError("owner PID is invalid")
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise BootstrapError("owner process identity cannot be observed") from exc
    closing = raw.rfind(")")
    fields = raw[closing + 2 :].split()
    if closing <= 1 or len(fields) <= 19:
        raise BootstrapError("owner process stat is malformed")
    try:
        starttime = int(fields[19])
    except ValueError as exc:
        raise BootstrapError("owner process starttime is malformed") from exc
    if starttime <= 0:
        raise BootstrapError("owner process starttime is invalid")
    return str(starttime)


def _validate_gate_b_publisher(
    value: object,
    *,
    expected_output_path: Path | str | None = None,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "actor",
            "driver_program",
            "execution_strategy",
            "mechanical_publisher",
            "owner_source",
            "output_mode",
            "output_path",
            "python",
            "qualification_session",
            "renderer_source",
        },
        "Gate-B publisher",
    )
    actor = _exact_keys(
        record["actor"],
        {"pid", "pid_starttime", "role"},
        "Gate-B publisher actor",
    )
    if (
        actor["role"] != "AB16_GATE_B_OWNER"
        or type(actor["pid"]) is not int
        or actor["pid"] <= 1
        or type(actor["pid_starttime"]) is not str
        or not actor["pid_starttime"].isdigit()
        or _proc_starttime(actor["pid"]) != actor["pid_starttime"]
    ):
        raise BootstrapError("Gate-B publisher actor identity drifted")
    _validate_literal_identity(
        record["driver_program"],
        GATE_B_OWNER_DRIVER_V1,
        "Gate-B owner driver",
    )
    _validate_literal_identity(
        record["mechanical_publisher"],
        OWNER_OEXCL_PUBLISH_V1,
        "Gate-B mechanical publisher",
    )
    renderer = _mode_identity(record["renderer_source"], "Gate-B renderer source")
    owner_source = _mode_identity(record["owner_source"], "Gate-B qualification owner source")
    python = _mode_identity(record["python"], "Gate-B publisher Python")
    qualification = _exact_keys(
        record["qualification_session"],
        {
            "lock_identities",
            "retained_fd_roles",
            "sequence",
            "session_id",
            "state",
        },
        "Gate-B qualification session",
    )
    if type(qualification["lock_identities"]) is not list or len(qualification["lock_identities"]) != 3:
        raise BootstrapError("Gate-B qualification lock identity set drifted")
    lock_paths: list[str] = []
    for value in qualification["lock_identities"]:
        lock = _exact_keys(
            value,
            {"device", "inode", "mode", "nlink", "path", "uid"},
            "Gate-B qualification lock",
        )
        if (
            type(lock["device"]) is not int
            or lock["device"] < 0
            or type(lock["inode"]) is not int
            or lock["inode"] < 0
            or type(lock["mode"]) is not int
            or lock["mode"] != 0o600
            or lock["nlink"] != 1
            or type(lock["path"]) is not str
            or type(lock["uid"]) is not int
            or lock["uid"] < 0
        ):
            raise BootstrapError("Gate-B qualification lock identity is malformed")
        lock_paths.append(lock["path"])
    output = _absolute(str(record["output_path"]))
    current_renderer = _snapshot_mode_identity(Path(__file__).resolve())
    current_owner_source = _snapshot_mode_identity(
        Path(__file__).resolve().with_name("ab16_gate_b_qualification_v1.py")
    )
    current_python = _snapshot_mode_identity(Path(os.path.realpath(sys.executable)))
    if (
        record["execution_strategy"] != GATE_B_OWNER_EXECUTION_STRATEGY
        or record["output_mode"] != 0o444
        or not output.is_absolute()
        or (expected_output_path is not None and output != _absolute(expected_output_path))
        or renderer != current_renderer
        or owner_source != current_owner_source
        or python != current_python
        or lock_paths != list(GATE_B_QUALIFICATION_LOCK_PATHS)
        or qualification["retained_fd_roles"] != list(GATE_B_RETAINED_FD_ROLES)
        or qualification["sequence"] not in (1, 2)
        or type(qualification["session_id"]) is not str
        or SHA256_RE.fullmatch(qualification["session_id"]) is None
        or qualification["state"]
        != "PUBLISHED_FDS_RETAINED_PENDING_BOOTSTRAP_HANDOFF"
    ):
        raise BootstrapError("Gate-B publisher selected-byte identity drifted")
    return record


def _gate_b_publisher_from_owner_context(output_path: Path | str) -> dict[str, object]:
    context = globals().get("__ab16_gate_b_owner_context__")
    if type(context) is not dict:
        raise BootstrapError("Gate-B renderer lacks its persistent owner context")
    record = dict(context)
    if record.get("output_path") != str(_absolute(output_path)):
        raise BootstrapError("Gate-B owner context output path drifted")
    _validate_gate_b_publisher(record, expected_output_path=output_path)
    return record


def _gate_b_publisher_for_parent(
    output_path: Path | str,
    *,
    sequence: int = 2,
    session_id: str = "0" * 64,
) -> dict[str, object]:
    """Build a live-process fixture publisher; production rendering uses owner context."""

    owner_pid = os.getpid()
    record = {
        "actor": {
            "pid": owner_pid,
            "pid_starttime": _proc_starttime(owner_pid),
            "role": "AB16_GATE_B_OWNER",
        },
        "driver_program": _literal_identity(GATE_B_OWNER_DRIVER_V1),
        "execution_strategy": GATE_B_OWNER_EXECUTION_STRATEGY,
        "mechanical_publisher": _literal_identity(OWNER_OEXCL_PUBLISH_V1),
        "owner_source": _snapshot_mode_identity(
            Path(__file__).resolve().with_name("ab16_gate_b_qualification_v1.py")
        ),
        "output_mode": 0o444,
        "output_path": str(_absolute(output_path)),
        "python": _snapshot_mode_identity(Path(os.path.realpath(sys.executable))),
        "qualification_session": {
            "lock_identities": [
                {
                    "device": index + 1,
                    "inode": index + 11,
                    "mode": 0o600,
                    "nlink": 1,
                    "path": path,
                    "uid": os.getuid(),
                }
                for index, path in enumerate(GATE_B_QUALIFICATION_LOCK_PATHS)
            ],
            "retained_fd_roles": list(GATE_B_RETAINED_FD_ROLES),
            "sequence": sequence,
            "session_id": session_id,
            "state": "PUBLISHED_FDS_RETAINED_PENDING_BOOTSTRAP_HANDOFF",
        },
        "renderer_source": _snapshot_mode_identity(Path(__file__).resolve()),
    }
    _validate_gate_b_publisher(record, expected_output_path=output_path)
    return record


def _render_gate_b_record(
    request: object,
    *,
    validator: Any,
    label: str,
) -> bytes:
    envelope = _exact_keys(request, {"output_path", "record"}, f"{label} render request")
    if not isinstance(envelope["record"], Mapping):
        raise BootstrapError(f"{label} render record is malformed")
    record = dict(envelope["record"])
    if "publisher" in record:
        raise BootstrapError(f"{label} renderer does not accept caller publisher bytes")
    record["publisher"] = _gate_b_publisher_from_owner_context(str(envelope["output_path"]))
    validator(record)
    return authority.canonical_json(record)


def render_gate_b_epoch_observation(request: object) -> bytes:
    """Render owner-bound epoch bytes without publishing them."""

    def validate(record: object) -> None:
        # The full join is replayed by bootstrap once the record is published;
        # rendering still enforces the exact schema and publisher identity.
        checked = _exact_keys(
            record,
            {
                "authorizations",
                "candidate_identity",
                "capture_transcript",
                "created_at_utc",
                "final_full_preflight_receipt_identity",
                "gate_a_receipt_identity",
                "manager_epoch",
                "planned_source_set_digest",
                "publisher",
                "purpose",
                "repository_head",
                "repository_root",
                "run_nonce",
                "schema_version",
                "status",
                "target_campaign_dir",
            },
            "Gate-B epoch observation",
        )
        _validate_gate_b_publisher(checked["publisher"], expected_output_path=str(request["output_path"]))
        if checked["schema_version"] != GATE_B_EPOCH_SCHEMA:
            raise BootstrapError("Gate-B epoch renderer schema drifted")

    return _render_gate_b_record(
        request,
        validator=validate,
        label="Gate-B epoch observation",
    )


def render_gate_b_approval(request: object) -> bytes:
    """Render owner-bound approval bytes without publishing them."""

    return _render_gate_b_record(
        request,
        validator=_validate_gate_b,
        label="Gate-B approval",
    )


def _validate_gate_b(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "approval_id",
            "arm_launch_authorized",
            "candidate_identity",
            "created_at_utc",
            "decision",
            "final_full_preflight_receipt_identity",
            "formal_campaign_creation_authorized",
            "gate",
            "gate_a_receipt_identity",
            "gate_b_epoch_observation_identity",
            "planned_source_set_digest",
            "publisher",
            "purpose",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "target_campaign_dir",
        },
        "Gate-B approval",
    )
    _utc(record["created_at_utc"], "Gate-B created_at_utc")
    authority.validate_detached_identity(
        record["candidate_identity"],
        "Gate-B candidate",
    )
    authority.validate_detached_identity(
        record["gate_a_receipt_identity"],
        "Gate-B Gate-A receipt",
    )
    final_identity = _mode_identity(
        record["final_full_preflight_receipt_identity"],
        "Gate-B final full-preflight receipt",
    )
    epoch_identity = _mode_identity(
        record["gate_b_epoch_observation_identity"],
        "Gate-B epoch observation",
    )
    _validate_gate_b_publisher(
        record["publisher"],
        expected_output_path=record["publisher"]["output_path"],
    )
    if (
        final_identity["mode"] != 0o444
        or epoch_identity["mode"] != 0o444
        or _snapshot_mode_identity(final_identity["path"]) != final_identity
        or _snapshot_mode_identity(epoch_identity["path"]) != epoch_identity
        or record["schema_version"] != GATE_B_SCHEMA
        or record["purpose"] != GATE_B_PURPOSE
        or record["gate"] != "B"
        or record["decision"] != "APPROVED"
        or record["formal_campaign_creation_authorized"] is not True
        or record["arm_launch_authorized"] is not False
        or record["publisher"]["qualification_session"]["sequence"] != 2
        or type(record["approval_id"]) is not str
        or APPROVAL_ID_RE.fullmatch(record["approval_id"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["run_nonce"]) is not str
        or RUN_NONCE_RE.fullmatch(record["run_nonce"]) is None
        or type(record["planned_source_set_digest"]) is not str
        or SHA256_RE.fullmatch(record["planned_source_set_digest"]) is None
        or type(record["target_campaign_dir"]) is not str
        or not Path(record["target_campaign_dir"]).is_absolute()
        or Path(record["target_campaign_dir"]).name != record["run_nonce"]
    ):
        raise BootstrapError("Gate-B approval does not authorize identity creation")
    return record


def _validate_final_full_preflight(
    value: object,
    *,
    gate_a: Mapping[str, Any],
    planned: Mapping[str, Mapping[str, object]],
) -> Mapping[str, Any]:
    record = _exact_keys(value, FINAL_FULL_PREFLIGHT_KEYS, "Gate-B final full-preflight receipt")
    _utc(record["started_at_utc"], "Gate-B final full-preflight started_at_utc")
    _utc(record["finished_at_utc"], "Gate-B final full-preflight finished_at_utc")
    for field in (
        "authority_ready_identity",
        "detached_replay_identity",
        "pre_run_authority_identity",
        "preflight_script_identity",
        "python_identity",
        "runner_tool_identity",
        "stderr_identity",
        "stdout_identity",
    ):
        _mode_identity(record[field], f"Gate-B final full-preflight {field}")
    command = _exact_keys(
        record["command"],
        {"argv", "execution_strategy", "loader_identity"},
        "Gate-B final full-preflight command",
    )
    loader = _exact_keys(
        command["loader_identity"],
        {"sha256", "size_bytes"},
        "Gate-B final full-preflight loader",
    )
    if (
        type(loader["sha256"]) is not str
        or SHA256_RE.fullmatch(loader["sha256"]) is None
        or type(loader["size_bytes"]) is not int
        or loader["size_bytes"] <= 0
    ):
        raise BootstrapError("Gate-B final full-preflight loader identity is malformed")
    expected_preflight = _project_mode_identity(planned["input.preflight_gate"], "preflight script")
    expected_python = _project_mode_identity(planned["system.python3_13"], "preflight Python")
    expected_runner = _project_mode_identity(planned["script.gate_a_validation_v2"], "preflight runner")
    gate_a_preflight, gate_a_identity = _unterminated_canonical_mode_record(
        gate_a["full_preflight_receipt_identity"]["path"],
        "Gate-A full-preflight receipt",
    )
    if gate_a_identity != gate_a["full_preflight_receipt_identity"]:
        raise BootstrapError("Gate-A full-preflight receipt identity drifted")
    gate_a_preflight = _exact_keys(
        gate_a_preflight,
        FINAL_FULL_PREFLIGHT_KEYS,
        "Gate-A full-preflight receipt",
    )
    gate_a_command = _exact_keys(
        gate_a_preflight["command"],
        {"argv", "execution_strategy", "loader_identity"},
        "Gate-A full-preflight command",
    )
    gate_a_loader = _exact_keys(
        gate_a_command["loader_identity"],
        {"sha256", "size_bytes"},
        "Gate-A full-preflight loader",
    )
    expected_pre_run = _mode_identity(
        gate_a_preflight["pre_run_authority_identity"],
        "Gate-A full-preflight pre-run authority",
    )
    if _snapshot_mode_identity(expected_pre_run["path"]) != expected_pre_run:
        raise BootstrapError("Gate-A full-preflight pre-run authority bytes drifted")
    if (
        gate_a_preflight["schema_version"] != FINAL_FULL_PREFLIGHT_SCHEMA
        or gate_a_preflight["purpose"] != FINAL_FULL_PREFLIGHT_PURPOSE
        or gate_a_preflight["status"] != "PASS"
        or gate_a_preflight["exit_code"] != 0
        or gate_a_preflight["timed_out"] is not False
        or gate_a_preflight["authority_ready_identity"] != gate_a["disposable_authority_ready_identity"]
        or gate_a_preflight["detached_replay_identity"] != gate_a["disposable_detached_replay_identity"]
        or gate_a_preflight["planned_source_set_digest"] != gate_a["planned_source_set_digest"]
        or gate_a_preflight["repository_head"] != gate_a["repository_head"]
        or gate_a_preflight["repository_root"] != gate_a["repository_root"]
        or gate_a_command["execution_strategy"] != FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY
        or loader != gate_a_loader
    ):
        raise BootstrapError("Gate-A full-preflight receipt no longer joins Gate A")
    if (
        record["schema_version"] != FINAL_FULL_PREFLIGHT_SCHEMA
        or record["purpose"] != FINAL_FULL_PREFLIGHT_PURPOSE
        or record["status"] != "PASS"
        or record["exit_code"] != 0
        or record["timed_out"] is not False
        or record["preflight_timeout_scale"] != FINAL_FULL_PREFLIGHT_TIMEOUT_SCALE
        or record["authorizations"]
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        }
        or type(record["duration_monotonic_ns"]) is not int
        or record["duration_monotonic_ns"] <= 0
        or record["authority_ready_identity"] != gate_a["disposable_authority_ready_identity"]
        or record["detached_replay_identity"] != gate_a["disposable_detached_replay_identity"]
        or record["pre_run_authority_identity"] != expected_pre_run
        or record["planned_source_set_digest"] != gate_a["planned_source_set_digest"]
        or record["repository_head"] != gate_a["repository_head"]
        or record["repository_root"] != gate_a["repository_root"]
        or record["preflight_script_identity"] != expected_preflight
        or record["python_identity"] != expected_python
        or record["runner_tool_identity"] != expected_runner
        or command["execution_strategy"] != FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY
        or command["argv"] != [expected_python["path"], "-I", expected_preflight["path"], "--full"]
    ):
        raise BootstrapError("Gate-B final full-preflight is not one exact current-HEAD PASS")
    for field in ("stdout_identity", "stderr_identity"):
        if record[field]["mode"] != 0o444 or _snapshot_mode_identity(record[field]["path"]) != record[field]:
            raise BootstrapError(f"Gate-B final full-preflight {field} bytes drifted")
    if len({record["stdout_identity"]["path"], record["stderr_identity"]["path"], expected_preflight["path"]}) != 3:
        raise BootstrapError("Gate-B final full-preflight evidence paths alias")
    return record


def _validate_gate_b_epoch_observation(
    value: object,
    *,
    gate_a: Mapping[str, Any],
    gate_a_identity: Mapping[str, object],
    candidate_identity: Mapping[str, object],
    final_full_preflight_identity: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "authorizations",
            "candidate_identity",
            "capture_transcript",
            "created_at_utc",
            "final_full_preflight_receipt_identity",
            "gate_a_receipt_identity",
            "manager_epoch",
            "planned_source_set_digest",
            "publisher",
            "purpose",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "status",
            "target_campaign_dir",
        },
        "Gate-B epoch observation",
    )
    _utc(record["created_at_utc"], "Gate-B epoch observation created_at_utc")
    authority.validate_manager_epoch(record["manager_epoch"])
    authority.validate_manager_epoch_capture_transcript(
        record["capture_transcript"],
        expected_epoch=record["manager_epoch"],
    )
    _validate_gate_b_publisher(
        record["publisher"],
        expected_output_path=record["publisher"]["output_path"],
    )
    if (
        record["schema_version"] != GATE_B_EPOCH_SCHEMA
        or record["purpose"] != GATE_B_EPOCH_PURPOSE
        or record["status"] != "PASS"
        or record["authorizations"]
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        }
        or record["candidate_identity"] != candidate_identity
        or record["gate_a_receipt_identity"] != gate_a_identity
        or record["final_full_preflight_receipt_identity"] != final_full_preflight_identity
        or record["publisher"]["qualification_session"]["sequence"] != 1
        or record["manager_epoch"] != gate_a["manager_epoch"]
        or any(
            record[field] != gate_a[field]
            for field in (
                "planned_source_set_digest",
                "repository_head",
                "repository_root",
                "run_nonce",
                "target_campaign_dir",
            )
        )
    ):
        raise BootstrapError("Gate-B epoch observation does not join Gate A")
    return record


def _assert_campaign_absent(campaign_dir: Path) -> None:
    authority._reject_symlink_chain(campaign_dir.parent)  # noqa: SLF001
    if not campaign_dir.parent.is_dir():
        raise BootstrapError("campaign parent must already exist")
    if campaign_dir.exists() or campaign_dir.is_symlink():
        raise BootstrapError("campaign directory already exists; no-overwrite applies")


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_directory_fd(path: Path) -> tuple[Path, int]:
    absolute = _absolute(path)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            next_descriptor = os.open(
                component,
                flags,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as exc:
        try:
            os.close(descriptor)
        except UnboundLocalError:
            pass
        raise BootstrapError("Git executable parent path is invalid or symlinked") from exc
    return absolute, descriptor


def _hash_open_executable(
    descriptor: int,
    *,
    absolute: Path,
) -> tuple[dict[str, object], tuple[int, ...]]:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 0
        or before.st_size > 1 << 30
        or stat.S_IMODE(before.st_mode) & 0o111 == 0
    ):
        raise BootstrapError(f"Git executable is not one bounded executable: {absolute}")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, 1 << 20)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    after = os.fstat(descriptor)
    if _stat_signature(before) != _stat_signature(after) or size != after.st_size:
        raise BootstrapError("Git executable changed during same-FD hash")
    mode = stat.S_IMODE(after.st_mode)
    return (
        {
            "device": after.st_dev,
            "inode": after.st_ino,
            "mode": mode,
            "mode_octal": f"{mode:04o}",
            "path": str(absolute),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        },
        _stat_signature(after),
    )


def _assert_expected_tool_identity(
    observed: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    fields = {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }
    if not fields <= set(expected) or any(observed[field] != expected[field] for field in fields):
        raise BootstrapError("Git executable differs from the planned source identity")


def _observe_repository_head(
    repository_root: Path,
    git_path: Path,
    *,
    expected_identity: Mapping[str, object],
) -> str:
    parent, parent_descriptor = _open_directory_fd(git_path.parent)
    absolute = parent / git_path.name
    try:
        descriptor = os.open(
            absolute.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        os.close(parent_descriptor)
        raise BootstrapError("Git executable path is invalid or symlinked") from exc
    try:
        observed, before_signature = _hash_open_executable(
            descriptor,
            absolute=absolute,
        )
        _assert_expected_tool_identity(observed, expected_identity)
        try:
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository_root),
                    "rev-parse",
                    "--verify",
                    "HEAD",
                ],
                check=False,
                close_fds=True,
                env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin"},
                executable=f"/proc/self/fd/{descriptor}",
                pass_fds=(descriptor,),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BootstrapError(f"repository HEAD observation failed: {exc}") from exc
        try:
            current_path = os.stat(
                absolute.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise BootstrapError("Git executable path changed during HEAD observation") from exc
        if (
            not stat.S_ISREG(current_path.st_mode)
            or current_path.st_dev != before_signature[0]
            or current_path.st_ino != before_signature[1]
        ):
            raise BootstrapError("Git executable path changed during HEAD observation")
        after, after_signature = _hash_open_executable(
            descriptor,
            absolute=absolute,
        )
        if after_signature != before_signature or after != observed:
            raise BootstrapError("Git executable bytes changed during HEAD observation")
    finally:
        os.close(descriptor)
        os.close(parent_descriptor)
    if (
        completed.returncode != 0
        or completed.stderr
        or len(completed.stdout) != 41
        or not completed.stdout.endswith(b"\n")
    ):
        raise BootstrapError("repository HEAD observation was not one clean SHA")
    try:
        head = completed.stdout[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise BootstrapError("repository HEAD was not ASCII") from exc
    if GIT_SHA_RE.fullmatch(head) is None:
        raise BootstrapError("repository HEAD was not lowercase 40-hex")
    return head


def _capture_epoch(
    *,
    scripts: Mapping[str, Path],
    system_paths: Mapping[str, Path],
) -> dict[str, object]:
    captured = authority.capture_manager_epoch_with_transcript(
        attestor_path=scripts["manager_attestor_v4"],
        busctl_path=system_paths["busctl"],
        python_path=system_paths["attestor_python"],
        sudo_path=system_paths["sudo"],
    )
    if type(captured) is not dict or set(captured) != {
        "manager_epoch",
        "transcript",
    }:
        raise BootstrapError("manager capture returned the wrong exact schema")
    authority.validate_manager_epoch(captured["manager_epoch"])
    authority.validate_manager_epoch_capture_transcript(
        captured["transcript"],
        expected_epoch=captured["manager_epoch"],
    )
    return captured


def _safe_snapshot_path(raw: bytes) -> str:
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BootstrapError("repository snapshot contains a non-UTF-8 path") from exc
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or unicodedata.normalize("NFC", value) != value
    ):
        raise BootstrapError(f"repository snapshot path is unsafe: {value!r}")
    return path.as_posix()


def _head_repository_blobs(
    repository: Path,
    repository_head: str,
) -> tuple[str, list[dict[str, object]], dict[str, bytes]]:
    if repository != Path(str(_BOOTSTRAP_BINDING["repository_root"])):
        raise BootstrapError("repository snapshot source is not the retained Git top level")
    tree_oid = _bootstrap_git(
        _BOOTSTRAP_BINDING,
        "rev-parse",
        "--verify",
        f"{repository_head}^{{tree}}",
        output_limit=128,
    ).decode().strip()
    raw_tree = _bootstrap_git(
        _BOOTSTRAP_BINDING,
        "ls-tree",
        "-rz",
        "-r",
        "--full-tree",
        repository_head,
        output_limit=64 << 20,
    )
    entries: list[tuple[str, str, str]] = []
    collision_keys: set[str] = set()
    for raw_record in raw_tree.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode_raw, object_type, oid_raw = metadata.split(b" ")
        except ValueError as exc:
            raise BootstrapError("repository ls-tree record is malformed") from exc
        mode = mode_raw.decode("ascii")
        oid = oid_raw.decode("ascii")
        path = _safe_snapshot_path(raw_path)
        collision = unicodedata.normalize("NFC", path).casefold()
        if (
            object_type != b"blob"
            or mode not in {"100644", "100755"}
            or GIT_SHA_RE.fullmatch(oid) is None
            or collision in collision_keys
        ):
            raise BootstrapError(f"repository snapshot member is inadmissible: {path}")
        collision_keys.add(collision)
        entries.append((path, mode, oid))
    if not entries or entries != sorted(entries, key=lambda item: item[0].encode("utf-8")):
        raise BootstrapError("repository snapshot member order drifted")
    batch_input = b"".join(oid.encode("ascii") + b"\n" for _, _, oid in entries)
    batch = _bootstrap_git(
        _BOOTSTRAP_BINDING,
        "cat-file",
        "--batch",
        input_bytes=batch_input,
        output_limit=256 << 20,
    )
    offset = 0
    blobs: dict[str, bytes] = {}
    members: list[dict[str, object]] = []
    for path, mode, expected_oid in entries:
        newline = batch.find(b"\n", offset)
        if newline < 0:
            raise BootstrapError("repository cat-file batch header is truncated")
        header = batch[offset:newline].split(b" ")
        if len(header) != 3 or header[1] != b"blob":
            raise BootstrapError("repository cat-file batch header drifted")
        oid = header[0].decode("ascii")
        try:
            size = int(header[2])
        except ValueError as exc:
            raise BootstrapError("repository cat-file batch size is malformed") from exc
        start = newline + 1
        end = start + size
        if oid != expected_oid or end >= len(batch) or batch[end : end + 1] != b"\n":
            raise BootstrapError(f"repository blob framing drifted: {path}")
        data = batch[start:end]
        offset = end + 1
        blobs[path] = data
        members.append(
            {
                "git_blob_oid": oid,
                "git_mode": mode,
                "materialized_mode": 0o555 if mode == "100755" else 0o444,
                "path": path,
                "raw_sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "source_kind": "git_blob",
            }
        )
    if offset != len(batch):
        raise BootstrapError("repository cat-file batch has trailing bytes")
    return tree_oid, members, blobs


def _external_platform_record(
    *,
    repository_head: str,
    python_identity: Mapping[str, object],
) -> dict[str, object]:
    executable = Path(os.path.realpath(sys.executable))
    if executable != Path(str(python_identity["path"])) or tuple(sys.version_info[:3]) != (3, 13, 13):
        raise BootstrapError("bootstrap is not running under the coherent CPython 3.13.13 interpreter")
    return {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "cpython_version": "3.13.13",
        "dual_holder_survival": {
            "assumption_id": "AB16_DUAL_HOLDER_SURVIVAL_V1",
            "simultaneous_guardian_supervisor_death_excluded": True,
            "reboot_or_power_loss_during_heavy_runtime_excluded": True,
            "single_holder_death_must_be_contained": True,
        },
        "external_platform_trust": [
            "CPython runtime and standard library semantics",
            "OR-Tools/protobuf installation and native dependencies",
            "kernel, systemd, D-Bus, cgroup-v2 and filesystem durability",
            "non-hostile operating-system account",
        ],
        "formal_launch_owner_driver": _literal_identity(FORMAL_LAUNCH_OWNER_DRIVER_V1),
        "gate_b_owner_driver": _literal_identity(GATE_B_OWNER_DRIVER_V1),
        "mechanical_oexcl_publisher": _literal_identity(OWNER_OEXCL_PUBLISH_V1),
        "ortools_version": importlib.metadata.version("ortools"),
        "protobuf_version": importlib.metadata.version("protobuf"),
        "python_identity": {
            key: python_identity[key] for key in ("mode", "path", "sha256", "size_bytes")
        },
        "repository_head": repository_head,
        "schema_version": EXTERNAL_PLATFORM_SCHEMA,
        "selected_byte_launch": {
            "direct_fd_map": {"authority": 5, "loader": 4, "python": 3},
            "execution_strategy": SELECTED_BYTE_EXECUTION_STRATEGY,
            "literal_identity": _literal_identity(SELECTED_BYTE_LAUNCH_V1),
            "systemd_fd_map": {"authority": 5, "loader": 4, "python": 3},
            "systemd_fd_names": ["ab16-python", "ab16-loader", "ab16-authority"],
        },
    }


def _build_repository_snapshot_sources(
    *,
    bootstrap_dir: Path,
    package_dir: Path,
    repository: Path,
    repository_head: str,
    planned: Mapping[str, Mapping[str, object]],
    scripts: Mapping[str, Path],
    strict_paths: Mapping[str, Path],
    system_full: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    tree_oid, tracked_members, blobs = _head_repository_blobs(repository, repository_head)
    candidate_snapshot = authority.snapshot_regular(strict_paths["candidate_placements"])
    planned_candidate = planned["input.candidate_placements"]
    if authority.full_identity(candidate_snapshot) != planned_candidate:
        raise BootstrapError("candidate_placements changed after Gate A")
    candidate_path = "data/preprocessed/candidate_placements.json"
    if candidate_path in blobs:
        raise BootstrapError("candidate overlay unexpectedly exists in the tracked tree")
    candidate_member = {
        "materialized_mode": 0o444,
        "package_role": "input.candidate_placements.json",
        "path": candidate_path,
        "raw_sha256": candidate_snapshot.sha256,
        "size_bytes": candidate_snapshot.size,
        "source_kind": "package_overlay",
    }
    members = [*tracked_members, candidate_member]
    ordered_digest = hashlib.sha256(authority.canonical_json(members)).hexdigest()
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for member in tracked_members:
            info = zipfile.ZipInfo(str(member["path"]), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = int(member["materialized_mode"]) << 16
            archive.writestr(info, blobs[str(member["path"])])
    archive_raw = archive_buffer.getvalue()
    manifest = {
        "archive_descriptor": {
            "package_role": SNAPSHOT_ARCHIVE_PACKAGE_ROLE,
            "sha256": hashlib.sha256(archive_raw).hexdigest(),
            "size_bytes": len(archive_raw),
        },
        "authority_scope": "AB16_RESEARCH_ONLY",
        "import_mode": "ordinary_pathfinder",
        "member_count": len(members),
        "members": members,
        "ordered_member_digest": ordered_digest,
        "repository_head": repository_head,
        "repository_tree": tree_oid,
        "schema_version": REPOSITORY_SNAPSHOT_SCHEMA,
        "total_bytes": sum(int(member["size_bytes"]) for member in members),
    }
    snapshot_sources = authority.mkdir_exclusive(bootstrap_dir / "repository-snapshot-sources")
    archive_path = snapshot_sources / "repository-snapshot.zip"
    manifest_path = snapshot_sources / "repository-snapshot.json"
    platform_path = snapshot_sources / "external-platform-assumptions.json"
    authority.write_exclusive(archive_path, archive_raw, mode=0o444)
    authority.write_exclusive(manifest_path, authority.canonical_json(manifest), mode=0o444)
    authority.write_exclusive(
        platform_path,
        authority.canonical_json(
            _external_platform_record(
                repository_head=repository_head,
                python_identity=system_full["python3_13"],
            )
        ),
        mode=0o444,
    )

    staged_dir = authority.mkdir_exclusive(bootstrap_dir / "package-source-staging")
    staged_scripts: dict[str, Path] = {}
    for role, live_path in scripts.items():
        try:
            relative = live_path.relative_to(repository).as_posix()
        except ValueError as exc:
            raise BootstrapError(f"repository script escaped the fixed tree: {role}") from exc
        raw = blobs.get(relative)
        planned_identity = planned[f"script.{role}"]
        if (
            raw is None
            or hashlib.sha256(raw).hexdigest() != planned_identity["sha256"]
            or len(raw) != planned_identity["size_bytes"]
        ):
            raise BootstrapError(f"repository script differs from fixed HEAD: {role}")
        staged_scripts[role] = staged_dir / f"script.{role}.py"
        authority.write_exclusive(staged_scripts[role], raw, mode=0o444)
    staged_inputs: dict[str, Path] = {}
    for role, live_path in strict_paths.items():
        if role == "candidate_placements":
            raw = candidate_snapshot.data
        elif role in EXTERNAL_STRICT_INPUT_ROLES:
            external_snapshot = authority.snapshot_regular(live_path)
            if authority.full_identity(external_snapshot) != planned[f"input.{role}"]:
                raise BootstrapError(f"external strict input changed after Gate A: {role}")
            raw = external_snapshot.data
        else:
            try:
                relative = live_path.relative_to(repository).as_posix()
            except ValueError as exc:
                raise BootstrapError(f"repository strict input escaped the fixed tree: {role}") from exc
            if relative not in blobs:
                raise BootstrapError(f"tracked strict input missing from fixed HEAD: {role}")
            raw = blobs[relative]
        if role != "candidate_placements":
            if hashlib.sha256(raw).hexdigest() != planned[f"input.{role}"]["sha256"]:
                raise BootstrapError(f"strict input differs from Gate-A plan: {role}")
        staged_inputs[role] = staged_dir / f"input.{role}"
        authority.write_exclusive(staged_inputs[role], raw, mode=0o444)
    return {
        "archive_path": archive_path,
        "blobs": blobs,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "platform_path": platform_path,
        "staged_inputs": staged_inputs,
        "staged_scripts": staged_scripts,
    }


def _materialize_repository_snapshot(
    *,
    campaign_dir: Path,
    package_dir: Path,
    package_id: str,
    created_at_utc: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_snapshot = authority.snapshot_regular(package_dir / "payload" / SNAPSHOT_MANIFEST_PACKAGE_ROLE)
    manifest = authority.strict_loads(manifest_snapshot.data, "AB16 repository snapshot manifest")
    manifest = _exact_keys(
        manifest,
        {
            "archive_descriptor",
            "authority_scope",
            "import_mode",
            "member_count",
            "members",
            "ordered_member_digest",
            "repository_head",
            "repository_tree",
            "schema_version",
            "total_bytes",
        },
        "AB16 repository snapshot manifest",
    )
    archive_snapshot = authority.snapshot_regular(package_dir / "payload" / SNAPSHOT_ARCHIVE_PACKAGE_ROLE)
    candidate_snapshot = authority.snapshot_regular(package_dir / "payload" / "input.candidate_placements.json")
    if manifest.get("archive_descriptor") != {
        "package_role": SNAPSHOT_ARCHIVE_PACKAGE_ROLE,
        "sha256": archive_snapshot.sha256,
        "size_bytes": archive_snapshot.size,
    }:
        raise BootstrapError("sealed repository snapshot archive identity drifted")
    members = manifest.get("members")
    if type(members) is not list:
        raise BootstrapError("sealed repository snapshot members are malformed")
    checked_members: list[Mapping[str, Any]] = []
    for index, value in enumerate(members):
        if not isinstance(value, Mapping):
            raise BootstrapError(f"sealed repository snapshot member {index} is malformed")
        source_kind = value.get("source_kind")
        if source_kind == "git_blob":
            expected_keys = {
                "git_blob_oid",
                "git_mode",
                "materialized_mode",
                "path",
                "raw_sha256",
                "size_bytes",
                "source_kind",
            }
        elif source_kind == "package_overlay":
            expected_keys = {
                "materialized_mode",
                "package_role",
                "path",
                "raw_sha256",
                "size_bytes",
                "source_kind",
            }
        else:
            raise BootstrapError(f"sealed repository snapshot member {index} source kind drifted")
        checked_members.append(
            _exact_keys(value, expected_keys, f"sealed repository snapshot member {index}")
        )
    if (
        manifest["schema_version"] != REPOSITORY_SNAPSHOT_SCHEMA
        or manifest["authority_scope"] != "AB16_RESEARCH_ONLY"
        or manifest["import_mode"] != "ordinary_pathfinder"
        or manifest["member_count"] != len(checked_members)
        or manifest["ordered_member_digest"]
        != hashlib.sha256(authority.canonical_json(checked_members)).hexdigest()
        or manifest["total_bytes"] != sum(int(member["size_bytes"]) for member in checked_members)
    ):
        raise BootstrapError("sealed repository snapshot manifest semantics drifted")
    root = authority.mkdir_exclusive(campaign_dir / "campaign-authority" / "source-snapshot-a001")
    repository = authority.mkdir_exclusive(root / "repository")
    expected = {str(member["path"]): member for member in checked_members}
    if len(expected) != len(checked_members):
        raise BootstrapError("sealed repository snapshot contains duplicate member paths")
    tracked = {path: member for path, member in expected.items() if member.get("source_kind") == "git_blob"}
    directories = {
        parent.as_posix()
        for path in expected
        for parent in Path(path).parents
        if parent.as_posix() != "."
    }
    for relative in sorted(directories, key=lambda value: (len(Path(value).parts), value.encode("utf-8"))):
        authority.mkdir_exclusive(repository / relative)
    with zipfile.ZipFile(io.BytesIO(archive_snapshot.data), "r") as archive:
        if archive.namelist() != list(tracked):
            raise BootstrapError("sealed repository snapshot ZIP member set/order drifted")
        for info in archive.infolist():
            member = tracked[info.filename]
            raw = archive.read(info)
            if (
                hashlib.sha256(raw).hexdigest() != member["raw_sha256"]
                or len(raw) != member["size_bytes"]
            ):
                raise BootstrapError(f"sealed repository snapshot member drifted: {info.filename}")
            destination = repository / info.filename
            authority.write_exclusive(destination, raw, mode=int(member["materialized_mode"]))
    overlay = expected.get("data/preprocessed/candidate_placements.json")
    if (
        not isinstance(overlay, Mapping)
        or overlay.get("source_kind") != "package_overlay"
        or overlay.get("raw_sha256") != candidate_snapshot.sha256
        or overlay.get("size_bytes") != candidate_snapshot.size
    ):
        raise BootstrapError("candidate overlay binding drifted")
    overlay_path = repository / "data/preprocessed/candidate_placements.json"
    authority.write_exclusive(overlay_path, candidate_snapshot.data, mode=0o444)
    identities: dict[str, dict[str, object]] = {}
    for path, member in expected.items():
        snapshot = authority.snapshot_regular(repository / path)
        if (
            snapshot.sha256 != member["raw_sha256"]
            or snapshot.size != member["size_bytes"]
            or stat.S_IMODE(snapshot.stat_result.st_mode) != member["materialized_mode"]
        ):
            raise BootstrapError(f"materialized repository snapshot member drifted: {path}")
        identities[path] = authority.detached_identity(snapshot)
    for directory in sorted((path for path in repository.rglob("*") if path.is_dir()), reverse=True):
        directory.chmod(0o555)
    repository.chmod(0o555)
    receipt = {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "candidate_identity": authority.detached_identity(candidate_snapshot),
        "created_at_utc": created_at_utc,
        "import_mode": "ordinary_pathfinder",
        "member_count": manifest["member_count"],
        "ordered_member_digest": manifest["ordered_member_digest"],
        "package_id": package_id,
        "repository_head": manifest["repository_head"],
        "repository_tree": manifest["repository_tree"],
        "schema_version": SNAPSHOT_MATERIALIZATION_SCHEMA,
        "snapshot_archive_identity": authority.detached_identity(archive_snapshot),
        "snapshot_manifest_identity": authority.detached_identity(manifest_snapshot),
        "snapshot_root": str(repository),
        "status": "PASS",
        "total_bytes": manifest["total_bytes"],
    }
    receipt_identity = authority.write_exclusive(
        root / "materialization-receipt.json",
        authority.canonical_json(receipt),
        mode=0o444,
    )
    return {"receipt": receipt, "receipt_identity": receipt_identity}, identities


def _path_preregistration(
    campaign_dir: Path | str,
) -> dict[str, object]:
    """Build the deterministic AB16 child-path registry without writing it."""

    campaign = _absolute(campaign_dir)
    prospective = campaign / "prospective-ab16"
    baseline = prospective / "baseline"
    formal = campaign / "formal-ab16"
    formal_attempt = formal / "formal-attempt-a001"
    package_payload = campaign / "campaign-authority" / "package" / "payload"
    snapshot_authority = campaign / "campaign-authority" / "source-snapshot-a001"
    slots = tuple(
        f"{configuration}-{order}-{arm}"
        for configuration in authority.AB16_CONFIGURATIONS
        for order in authority.AB16_ORDERS
        for arm in authority.AB16_ARMS
    )
    attempt_dirs = {slot: str(prospective / "arms" / slot) for slot in slots}
    return {
        "arithmetic_replay_paths": {
            slot: str(Path(attempt_dirs[slot]) / "replays/independent-arithmetic.json") for slot in slots
        },
        "arm_gate_paths": {slot: str(Path(attempt_dirs[slot]) / "replays/arm-credibility.json") for slot in slots},
        "arm_prelaunch_paths": {
            slot: {
                "receipt": str(formal_attempt / "arm-prelaunch" / f"{slot}-receipt.json"),
                "request": str(formal_attempt / "arm-prelaunch" / f"{slot}-request.json"),
            }
            for slot in slots
        },
        "arm_selection_paths": {slot: str(Path(attempt_dirs[slot]) / "selection.json") for slot in slots},
        "attempt_dirs": attempt_dirs,
        "baseline_admission_path": str(prospective / "baseline-admission-a001.json"),
        "baseline_campaign_provenance_path": str(baseline / "campaign-provenance.json"),
        "baseline_fixed_replay_path": str(baseline / "fixed-replay-a001.json"),
        "baseline_incumbent_path": str(baseline / "incumbent.json"),
        "baseline_rebuilt_metadata_path": str(baseline / "rebuilt-model-metadata.json"),
        "baseline_rebuilt_model_path": str(baseline / "cut-free-model.bin"),
        "binding_paths": {slot: str(prospective / "bindings" / f"{slot}.json") for slot in slots},
        "campaign_dir": str(campaign),
        "classification_contract_path": str(package_payload / "tool.ab16_contract_v1.py"),
        "common_prestate_path": str(prospective / "common-prestate-a001.json"),
        "child_audit_path": str(formal_attempt / "child-audit.json"),
        "cut_free_replay_paths": {
            slot: str(Path(attempt_dirs[slot]) / "replays/cut-free-incumbent.json") for slot in slots
        },
        "formal_admission_path": str(formal / "formal-launch-admission-a001.json"),
        "formal_attempt_dir": str(formal_attempt),
        "formal_selection_path": str(formal_attempt / "selection.json"),
        "gate1_prelaunch_ownership_path": str(formal_attempt / "gate1-prelaunch-ownership.json"),
        "guardian_control_socket_path": str(formal / "guardian-control.sock"),
        "guardian_control_retired_socket_path": str(formal / "guardian-control.sock.retired"),
        "guardian_ready_path": str(formal / "outer-guardian-ready-a001.json"),
        "immediate_stop_path": str(prospective / "immediate-stop-a001.json"),
        "manifest_path": str(prospective / "manifest-a001.json"),
        "launch_environment_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-launch-environment.json") for slot in slots
        },
        "outer_barrier_path": str(formal_attempt / "outer-barrier-release.json"),
        "outer_receipt_paths": {
            "detached_closeout": str(formal_attempt / "detached-closeout.json"),
            "detached_incomplete_closeout": str(
                formal_attempt / "detached-incomplete-closeout.json"
            ),
            "dual_lock_release": str(formal_attempt / "dual-lock-release.json"),
            "guardian_absence": str(formal_attempt / "guardian-absence.json"),
            "guardian_lock_close": str(formal_attempt / "guardian-lock-close.json"),
            "observer": str(formal_attempt / "observer.json"),
            "outer_prelaunch": str(formal_attempt / "outer-prelaunch.json"),
            "outer_resource": str(formal_attempt / "resource-live.json"),
            "outer_start": str(formal_attempt / "outer-start.json"),
            "outer_terminal": str(formal_attempt / "outer-terminal.json"),
            "post_unref_absence": str(formal_attempt / "post-unref-absence.json"),
            "pre_unref_cleanup": str(formal_attempt / "pre-unref-cleanup.json"),
            "reference_acquisition": str(formal_attempt / "reference-acquisition.json"),
            "reference_release": str(formal_attempt / "reference-release.json"),
        },
        "preselection_epoch_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-preselection-epoch.json") for slot in slots
        },
        "preselection_transcript_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-preselection-transcript.json") for slot in slots
        },
        "pre_run_authority_paths": {slot: str(Path(attempt_dirs[slot]) / "pre-run-authority.json") for slot in slots},
        "pre_run_candidate_paths": {slot: str(prospective / "pre-run-candidates" / f"{slot}.json") for slot in slots},
        "repository_snapshot_archive_path": str(package_payload / SNAPSHOT_ARCHIVE_PACKAGE_ROLE),
        "repository_snapshot_manifest_path": str(package_payload / SNAPSHOT_MANIFEST_PACKAGE_ROLE),
        "repository_snapshot_materialization_receipt_path": str(
            snapshot_authority / "materialization-receipt.json"
        ),
        "repository_snapshot_root": str(snapshot_authority / "repository"),
        "resource_replay_paths": {
            slot: str(Path(attempt_dirs[slot]) / "replays/independent-resource-terminal.json") for slot in slots
        },
        "purpose": PATH_PREREGISTRATION_PURPOSE,
        "run_nonce": campaign.name,
        "schema": PATH_PREREGISTRATION_SCHEMA,
        "suite_selection_path": str(prospective / "selection-a001.json"),
        "terminal_classification_path": str(prospective / "terminal-classification-a001.json"),
    }


def validate_path_preregistration(
    value: object,
    *,
    campaign_dir: Path | str,
) -> Mapping[str, Any]:
    """Reject any path registry that differs from the fixed v4 child topology."""

    expected = _path_preregistration(campaign_dir)
    record = _exact_keys(
        value,
        set(expected),
        "AB16 path preregistration",
    )
    if record != expected:
        raise BootstrapError("AB16 path preregistration topology drifted")
    campaign = _absolute(campaign_dir)
    path_fields = {
        "baseline_admission_path",
        "baseline_campaign_provenance_path",
        "baseline_fixed_replay_path",
        "baseline_incumbent_path",
        "baseline_rebuilt_metadata_path",
        "baseline_rebuilt_model_path",
        "classification_contract_path",
        "child_audit_path",
        "common_prestate_path",
        "formal_admission_path",
        "formal_attempt_dir",
        "formal_selection_path",
        "gate1_prelaunch_ownership_path",
        "guardian_control_socket_path",
        "guardian_control_retired_socket_path",
        "guardian_ready_path",
        "immediate_stop_path",
        "manifest_path",
        "outer_barrier_path",
        "repository_snapshot_archive_path",
        "repository_snapshot_manifest_path",
        "repository_snapshot_materialization_receipt_path",
        "repository_snapshot_root",
        "suite_selection_path",
        "terminal_classification_path",
    }
    paths = [Path(record[field]) for field in path_fields]
    outer_receipts = _exact_keys(
        record["outer_receipt_paths"],
        set(expected["outer_receipt_paths"]),
        "AB16 path preregistration outer_receipt_paths",
    )
    paths.extend(Path(path) for path in outer_receipts.values())
    for mapping_field in (
        "arithmetic_replay_paths",
        "arm_gate_paths",
        "arm_selection_paths",
        "attempt_dirs",
        "binding_paths",
        "cut_free_replay_paths",
        "launch_environment_paths",
        "preselection_epoch_paths",
        "preselection_transcript_paths",
        "pre_run_candidate_paths",
        "pre_run_authority_paths",
        "resource_replay_paths",
    ):
        mapping = _exact_keys(
            record[mapping_field],
            set(expected[mapping_field]),
            f"AB16 path preregistration {mapping_field}",
        )
        paths.extend(Path(path) for path in mapping.values())
    arm_prelaunch = _exact_keys(
        record["arm_prelaunch_paths"],
        set(expected["arm_prelaunch_paths"]),
        "AB16 path preregistration arm_prelaunch_paths",
    )
    for slot, item in arm_prelaunch.items():
        pair = _exact_keys(
            item,
            {"receipt", "request"},
            f"AB16 path preregistration arm_prelaunch_paths.{slot}",
        )
        paths.extend(Path(pair[field]) for field in ("receipt", "request"))
    if any(not path.is_absolute() or not path.is_relative_to(campaign) for path in paths):
        raise BootstrapError("AB16 path preregistration escaped the campaign")
    return record


def _validate_path_preregistration_against_root(
    value: Mapping[str, Any],
    root: Mapping[str, Any],
    *,
    campaign_dir: Path | str,
) -> None:
    """Join the package-pinned registry to the unchanged v4 campaign root."""

    record = validate_path_preregistration(
        value,
        campaign_dir=campaign_dir,
    )
    prospective = root["stage_topology"]["prospective_ab16"]
    root_attempts = {arm["slot"]: arm["attempt_dir"] for arm in prospective["arms"]}
    if (
        record["manifest_path"] != prospective["manifest_path"]
        or record["suite_selection_path"] != prospective["arm_selection_path"]
        or record["terminal_classification_path"] != prospective["terminal_classification_path"]
        or record["attempt_dirs"] != root_attempts
    ):
        raise BootstrapError("AB16 path preregistration differs from v4 root")
    for slot, attempt_dir in root_attempts.items():
        attempt = Path(attempt_dir)
        expected_paths = {
            "arithmetic_replay_paths": attempt / "replays/independent-arithmetic.json",
            "arm_gate_paths": attempt / "replays/arm-credibility.json",
            "arm_selection_paths": attempt / "selection.json",
            "cut_free_replay_paths": attempt / "replays/cut-free-incumbent.json",
            "pre_run_authority_paths": attempt / "pre-run-authority.json",
            "resource_replay_paths": attempt / "replays/independent-resource-terminal.json",
        }
        if any(record[field][slot] != str(path) for field, path in expected_paths.items()):
            raise BootstrapError("AB16 per-arm preregistration differs from v4 root")


def build_gate_a_candidate(
    *,
    output_path: Path | str,
    gate_a_receipt: Path | str,
    repository_root: Path | str,
    target_campaign_dir: Path | str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    created_at_utc: str | None = None,
) -> dict[str, object]:
    """Write only a non-authorizing candidate; never create a campaign."""

    campaign_dir = _absolute(target_campaign_dir)
    candidate_output = _absolute(output_path)
    preregistration_output = candidate_output.parent / "ab16-path-preregistration.json"
    repository = _absolute(repository_root)
    _assert_campaign_absent(campaign_dir)
    authority._reject_symlink_chain(candidate_output.parent)  # noqa: SLF001
    if (
        candidate_output.exists()
        or candidate_output.is_symlink()
        or preregistration_output.exists()
        or preregistration_output.is_symlink()
    ):
        raise BootstrapError("offline candidate or path preregistration already exists")
    gate_a, gate_a_identity = _canonical_record(
        gate_a_receipt,
        "Gate-A receipt",
    )
    gate_a = _validate_gate_a(gate_a)
    planned, _, system_paths, _ = _planned_source_identities(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    digest = _source_set_digest(planned)
    observed_head = _observe_repository_head(
        repository,
        system_paths["git"],
        expected_identity=planned["system.git"],
    )
    if (
        gate_a["target_campaign_dir"] != str(campaign_dir)
        or gate_a["run_nonce"] != campaign_dir.name
        or gate_a["repository_root"] != str(repository)
        or gate_a["planned_source_set_digest"] != digest
        or gate_a["repository_head"] != observed_head
    ):
        raise BootstrapError("Gate-A receipt does not bind the offline candidate")
    timestamp = created_at_utc or _utc_now()
    _utc(timestamp, "candidate created_at_utc")
    preregistration = _path_preregistration(campaign_dir)
    validate_path_preregistration(
        preregistration,
        campaign_dir=campaign_dir,
    )
    preregistration_identity = authority.write_exclusive(
        preregistration_output,
        authority.canonical_json(preregistration),
    )
    candidate: dict[str, object] = {
        "arm_launch_authorized": False,
        "candidate_id": "",
        "candidate_only": True,
        "created_at_utc": timestamp,
        "formal_campaign_creation_authorized": False,
        "gate_a_receipt_identity": gate_a_identity,
        "path_preregistration_identity": preregistration_identity,
        "planned_source_identities": planned,
        "planned_source_set_digest": digest,
        "purpose": CANDIDATE_PURPOSE,
        "repository_head": observed_head,
        "repository_root": str(repository),
        "run_nonce": campaign_dir.name,
        "schema_version": CANDIDATE_SCHEMA,
        "target_campaign_dir": str(campaign_dir),
    }
    candidate["candidate_id"] = _digest_without(candidate, "candidate_id")
    validate_candidate(candidate)
    candidate_identity = authority.write_exclusive(
        candidate_output,
        authority.canonical_json(candidate),
    )
    if campaign_dir.exists() or campaign_dir.is_symlink():
        raise BootstrapError("Gate A illegally created the campaign directory")
    return {
        "candidate": candidate,
        "candidate_identity": candidate_identity,
        "formal_campaign_created": False,
        "path_preregistration": preregistration,
        "path_preregistration_identity": preregistration_identity,
    }


def _payload_identity(
    package_dir: Path,
    role: str,
) -> dict[str, object]:
    return authority.detached_identity(authority.snapshot_regular(package_dir / "payload" / role))


def _package_roles(
    *,
    scripts: Mapping[str, Path],
    system_paths: Mapping[str, Path],
    strict_paths: Mapping[str, Path],
    gate_a_path: Path,
    candidate_path: Path,
    gate_b_path: Path,
    gate_b_epoch_path: Path,
    final_full_preflight_path: Path,
    capture_path: Path,
    path_preregistration_path: Path,
    snapshot_archive_path: Path,
    snapshot_manifest_path: Path,
    external_platform_path: Path,
) -> tuple[
    list[authority.SourceSpec],
    dict[str, str],
    dict[str, str],
]:
    specs: list[authority.SourceSpec] = []
    script_roles: dict[str, str] = {}
    for role, path in sorted(scripts.items()):
        package_role = "campaign_authority_v4.py" if role == "campaign_authority_v4" else f"tool.{role}.py"
        script_roles[role] = package_role
        specs.append(authority.SourceSpec(package_role, path))
    for role, path in sorted(system_paths.items()):
        specs.append(authority.SourceSpec(f"system.{role}.bin", path))
    input_roles: dict[str, str] = {}
    for role, path in sorted(strict_paths.items()):
        suffix = ".json" if role in JSON_INPUT_ROLES else ".txt"
        package_role = f"input.{role}{suffix}"
        input_roles[role] = package_role
        specs.append(
            authority.SourceSpec(
                package_role,
                path,
                parse_json=role in CANONICAL_JSON_INPUT_ROLES,
            )
        )
    for role, filename, path in (
        ("ab16_gate_a_receipt", GATE_INPUT_ROLES["ab16_gate_a_receipt"], gate_a_path),
        (
            "ab16_offline_candidate",
            GATE_INPUT_ROLES["ab16_offline_candidate"],
            candidate_path,
        ),
        ("ab16_gate_b_approval", GATE_INPUT_ROLES["ab16_gate_b_approval"], gate_b_path),
        (
            "ab16_gate_b_epoch_observation",
            GATE_INPUT_ROLES["ab16_gate_b_epoch_observation"],
            gate_b_epoch_path,
        ),
        (
            "ab16_gate_b_final_full_preflight",
            GATE_INPUT_ROLES["ab16_gate_b_final_full_preflight"],
            final_full_preflight_path,
        ),
    ):
        input_roles[role] = filename
        specs.append(authority.SourceSpec(filename, path, parse_json=True))
    input_roles[CAPTURE_INPUT_ROLE] = CAPTURE_PACKAGE_ROLE
    specs.append(
        authority.SourceSpec(
            CAPTURE_PACKAGE_ROLE,
            capture_path,
            parse_json=True,
        )
    )
    input_roles[PATH_PREREGISTRATION_INPUT_ROLE] = PATH_PREREGISTRATION_PACKAGE_ROLE
    specs.append(
        authority.SourceSpec(
            PATH_PREREGISTRATION_PACKAGE_ROLE,
            path_preregistration_path,
            parse_json=True,
        )
    )
    for role, package_role, path, parse_json in (
        (SNAPSHOT_ARCHIVE_INPUT_ROLE, SNAPSHOT_ARCHIVE_PACKAGE_ROLE, snapshot_archive_path, False),
        (SNAPSHOT_MANIFEST_INPUT_ROLE, SNAPSHOT_MANIFEST_PACKAGE_ROLE, snapshot_manifest_path, True),
        (EXTERNAL_PLATFORM_INPUT_ROLE, EXTERNAL_PLATFORM_PACKAGE_ROLE, external_platform_path, True),
    ):
        input_roles[role] = package_role
        specs.append(authority.SourceSpec(package_role, path, parse_json=parse_json))
    return specs, script_roles, input_roles


def _detached_from_full(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "path": value["path"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _package_source_join(
    package_dir: Path,
    *,
    expected_sources: Mapping[str, Mapping[str, object]],
) -> None:
    manifest_snapshot = authority.snapshot_regular(package_dir / "package-manifest.json")
    manifest = authority.strict_loads(
        manifest_snapshot.data,
        "AB16 package manifest source join",
    )
    if not isinstance(manifest, Mapping) or not isinstance(
        manifest.get("external_sources"),
        list,
    ):
        raise BootstrapError("package source manifest is malformed")
    records: dict[str, Mapping[str, object]] = {}
    for raw_record in manifest["external_sources"]:
        record = _exact_keys(
            raw_record,
            {
                "package_path",
                "parse_json",
                "role",
                "source_identity",
            },
            "package external source",
        )
        role = record["role"]
        if type(role) is not str or role in records:
            raise BootstrapError("package external source role drifted")
        if not isinstance(record["source_identity"], Mapping):
            raise BootstrapError("package source identity is malformed")
        records[role] = record["source_identity"]

    if set(records) != set(expected_sources):
        raise BootstrapError("package external source role set drifted")
    for role, expected in expected_sources.items():
        if dict(records[role]) != dict(expected):
            raise BootstrapError(f"package source changed during creation: {role}")


def _check_epoch_toolchain(
    epoch: Mapping[str, object],
    *,
    scripts: Mapping[str, Path],
    system_full: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    attestor = {key: epoch["attestation_toolchain"]["attestor"][key] for key in ("path", "sha256", "size_bytes")}
    authority.validate_detached_identity(attestor, "epoch attestor")
    current_attestor = authority.detached_identity(authority.snapshot_regular(scripts["manager_attestor_v4"]))
    expected = {
        "attestor_python": epoch["attestation_toolchain"]["python"],
        "busctl": epoch["observation_toolchain"]["busctl"],
        "sudo": epoch["attestation_toolchain"]["sudo"],
    }
    if attestor != current_attestor:
        raise BootstrapError("manager epoch attestor does not match selected bytes")
    for role, full in expected.items():
        if _detached_from_full(system_full[role]) != {key: full[key] for key in ("path", "sha256", "size_bytes")}:
            raise BootstrapError(f"manager epoch {role} does not match selected bytes")
    return attestor


def _qualification_lock_identity(
    descriptor: int,
    path: str,
) -> dict[str, object]:
    absolute = _absolute(path)
    parent, parent_descriptor = _open_directory_fd(absolute.parent)
    try:
        named = os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    finally:
        os.close(parent_descriptor)
    opened = os.fstat(descriptor)
    if (
        parent != absolute.parent
        or _stat_signature(opened) != _stat_signature(named)
        or not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or opened.st_uid != os.getuid()
        or stat.S_IMODE(opened.st_mode) != 0o600
    ):
        raise BootstrapError(f"Gate-B qualification lock identity drifted: {absolute}")
    return {
        "device": opened.st_dev,
        "inode": opened.st_ino,
        "mode": stat.S_IMODE(opened.st_mode),
        "nlink": opened.st_nlink,
        "path": str(absolute),
        "uid": opened.st_uid,
    }


def _complete_gate_b_qualification_handoff(
    *,
    qualification_fd: int,
    qualification_lock_fds: Mapping[str, int],
    epoch_publisher: Mapping[str, Any],
    approval_publisher: Mapping[str, Any],
    gate_b_epoch_identity: Mapping[str, object],
    gate_b_approval_identity: Mapping[str, object],
    campaign_root_identity: Mapping[str, object],
    gate1_selection_identity: Mapping[str, object],
    expected_lock_paths: Sequence[str] = GATE_B_QUALIFICATION_LOCK_PATHS,
) -> dict[str, object]:
    epoch_session = _exact_keys(
        epoch_publisher["qualification_session"],
        {
            "lock_identities",
            "retained_fd_roles",
            "sequence",
            "session_id",
            "state",
        },
        "Gate-B epoch qualification session",
    )
    approval_session = _exact_keys(
        approval_publisher["qualification_session"],
        set(epoch_session),
        "Gate-B approval qualification session",
    )
    paths = tuple(expected_lock_paths)
    if (
        epoch_publisher["actor"] != approval_publisher["actor"]
        or epoch_session["session_id"] != approval_session["session_id"]
        or epoch_session["sequence"] != 1
        or approval_session["sequence"] != 2
        or epoch_session["lock_identities"] != approval_session["lock_identities"]
        or epoch_session["retained_fd_roles"] != list(GATE_B_RETAINED_FD_ROLES)
        or approval_session["retained_fd_roles"] != list(GATE_B_RETAINED_FD_ROLES)
        or set(qualification_lock_fds) != set(paths)
    ):
        raise BootstrapError("Gate-B qualification session join drifted")
    observed_locks = [
        _qualification_lock_identity(qualification_lock_fds[path], path)
        for path in paths
    ]
    if observed_locks != epoch_session["lock_identities"]:
        raise BootstrapError("Gate-B qualification lock FD join drifted")
    request = {
        "action": "BOOTSTRAP_HANDOFF",
        "actor": dict(epoch_publisher["actor"]),
        "campaign_root_identity": dict(campaign_root_identity),
        "gate1_selection_identity": dict(gate1_selection_identity),
        "gate_b_approval_identity": dict(gate_b_approval_identity),
        "gate_b_epoch_identity": dict(gate_b_epoch_identity),
        "lock_identities": observed_locks,
        "publisher_sequences": [1, 2],
        "schema": GATE_B_HANDOFF_REQUEST_SCHEMA,
        "session_id": epoch_session["session_id"],
    }
    try:
        channel = socket.socket(fileno=os.dup(qualification_fd))
        channel.settimeout(60)
        try:
            raw = authority.canonical_json(request)
            if channel.send(raw) != len(raw):
                raise BootstrapError("Gate-B qualification handoff write was short")
            response_raw = channel.recv(16 * 1024 * 1024)
        finally:
            channel.close()
    except (OSError, TimeoutError) as exc:
        raise BootstrapError("Gate-B qualification handoff transport failed") from exc
    response = authority.strict_loads(
        response_raw,
        "Gate-B qualification handoff response",
    )
    response = _exact_keys(
        response,
        {
            "actor",
            "lock_identities",
            "publisher_sequences",
            "retained_fd_digest",
            "retained_fd_roles",
            "schema",
            "session_id",
            "state",
            "status",
        },
        "Gate-B qualification handoff response",
    )
    if (
        authority.canonical_json(response) != response_raw
        or response["schema"] != GATE_B_HANDOFF_RESPONSE_SCHEMA
        or response["status"] != "PASS"
        or response["state"] != "BOOTSTRAP_HANDOFF_COMPLETE_FDS_RETAINED"
        or response["actor"] != epoch_publisher["actor"]
        or response["session_id"] != epoch_session["session_id"]
        or response["publisher_sequences"] != [1, 2]
        or response["lock_identities"] != observed_locks
        or response["retained_fd_roles"] != list(GATE_B_RETAINED_FD_ROLES)
        or type(response["retained_fd_digest"]) is not str
        or SHA256_RE.fullmatch(response["retained_fd_digest"]) is None
    ):
        raise BootstrapError("Gate-B qualification handoff response drifted")
    return dict(response)


def _select_root_strict_input_identities(
    *,
    repository: Path,
    strict_paths: Mapping[str, Path],
    planned: Mapping[str, Mapping[str, Any]],
    packaged_inputs: Mapping[str, Mapping[str, Any]],
    snapshot_identities: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, object]]:
    """Select the exact authority identity consumed by the campaign root."""

    inputs = {
        role: dict(identity)
        for role, identity in packaged_inputs.items()
    }
    for role, source_path in strict_paths.items():
        if role == "candidate_placements":
            relative = "data/preprocessed/candidate_placements.json"
        elif role in EXTERNAL_STRICT_INPUT_ROLES:
            if role == "history_freeze_manifest":
                # Its replay receipt binds the immutable external manifest's
                # complete path/mode/content identity.  The package copy remains
                # a sealed payload member, but it cannot replace that source
                # identity at the formal join.
                original = _detached_from_full(planned[f"input.{role}"])
                packaged = inputs.get(role)
                if (
                    packaged is None
                    or packaged["sha256"] != original["sha256"]
                    or packaged["size_bytes"] != original["size_bytes"]
                ):
                    raise BootstrapError(
                        "packaged history-freeze manifest differs from its source"
                    )
                inputs[role] = original
            continue
        else:
            try:
                relative = source_path.relative_to(repository).as_posix()
            except ValueError as exc:
                raise BootstrapError(
                    f"repository strict input escaped the materialized snapshot: {role}"
                ) from exc
        materialized = snapshot_identities.get(relative)
        if materialized is None:
            raise BootstrapError(
                f"repository strict input is absent from the materialized snapshot: {role}"
            )
        packaged = inputs[role]
        if (
            materialized["sha256"] != packaged["sha256"]
            or materialized["size_bytes"] != packaged["size_bytes"]
        ):
            raise BootstrapError(
                f"materialized strict input differs from sealed package: {role}"
            )
        inputs[role] = dict(materialized)
    return inputs


def bootstrap_campaign(
    *,
    campaign_dir: Path | str,
    repository_root: Path | str,
    gate_a_receipt: Path | str,
    offline_candidate: Path | str,
    gate_b_approval: Path | str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    qualification_fd: int | None = None,
    qualification_lock_fds: Mapping[str, int] | None = None,
    created_at_utc: str | None = None,
) -> dict[str, object]:
    """Create a complete v4 campaign authority only after both gates bind."""

    output = _absolute(campaign_dir)
    repository = _absolute(repository_root)
    _assert_campaign_absent(output)
    gate_a_path = _absolute(gate_a_receipt)
    candidate_path = _absolute(offline_candidate)
    gate_b_path = _absolute(gate_b_approval)
    gate_a, gate_a_identity = _canonical_record(gate_a_path, "Gate-A receipt")
    gate_a = _validate_gate_a(gate_a)
    candidate, candidate_identity = _canonical_record(
        candidate_path,
        "offline candidate",
    )
    candidate = validate_candidate(candidate)
    path_preregistration_path = _absolute(candidate["path_preregistration_identity"]["path"])
    path_preregistration, path_preregistration_identity = _canonical_record(
        path_preregistration_path,
        "AB16 path preregistration",
    )
    if path_preregistration_identity != candidate["path_preregistration_identity"]:
        raise BootstrapError("candidate AB16 path preregistration identity drifted")
    path_preregistration = validate_path_preregistration(
        path_preregistration,
        campaign_dir=output,
    )
    gate_b, gate_b_identity = _canonical_record(gate_b_path, "Gate-B approval")
    gate_b = _validate_gate_b(gate_b)
    if (
        gate_a["approval_id"] == gate_b["approval_id"]
        or gate_a_identity["path"] == gate_b_identity["path"]
        or gate_a_identity["sha256"] == gate_b_identity["sha256"]
        or candidate["gate_a_receipt_identity"] != gate_a_identity
        or gate_b["gate_a_receipt_identity"] != gate_a_identity
        or gate_b["candidate_identity"] != candidate_identity
    ):
        raise BootstrapError("Gate-A/candidate/Gate-B byte binding is invalid")
    scalar_binding = {
        "planned_source_set_digest",
        "repository_head",
        "repository_root",
        "run_nonce",
        "target_campaign_dir",
    }
    if any(candidate[field] != gate_a[field] or candidate[field] != gate_b[field] for field in scalar_binding):
        raise BootstrapError("Gate-A/candidate/Gate-B scalar binding drifted")
    if gate_b["target_campaign_dir"] != str(output):
        raise BootstrapError("Gate-B target is not this campaign directory")
    if gate_b["repository_root"] != str(repository):
        raise BootstrapError("Gate-B repository root is not this repository")

    planned, scripts, system_paths, strict_paths = _planned_source_identities(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    if candidate["planned_source_identities"] != planned or candidate[
        "planned_source_set_digest"
    ] != _source_set_digest(planned):
        raise BootstrapError("planned package source bytes drifted after Gate A")
    final_full_preflight_path = _absolute(gate_b["final_full_preflight_receipt_identity"]["path"])
    final_full_preflight, final_full_preflight_identity = _unterminated_canonical_mode_record(
        final_full_preflight_path,
        "Gate-B final full-preflight receipt",
    )
    if final_full_preflight_identity != gate_b["final_full_preflight_receipt_identity"]:
        raise BootstrapError("Gate-B final full-preflight identity drifted")
    if (
        final_full_preflight_identity["path"] == gate_a["full_preflight_receipt_identity"]["path"]
        or final_full_preflight_identity["sha256"] == gate_a["full_preflight_receipt_identity"]["sha256"]
    ):
        raise BootstrapError("Gate-B final full-preflight is not independent from Gate A")
    _validate_final_full_preflight(final_full_preflight, gate_a=gate_a, planned=planned)
    gate_b_epoch_path = _absolute(gate_b["gate_b_epoch_observation_identity"]["path"])
    gate_b_epoch, gate_b_epoch_identity = _canonical_mode_record(
        gate_b_epoch_path,
        "Gate-B epoch observation",
    )
    if gate_b_epoch_identity != gate_b["gate_b_epoch_observation_identity"]:
        raise BootstrapError("Gate-B epoch observation identity drifted")
    gate_b_epoch = _validate_gate_b_epoch_observation(
        gate_b_epoch,
        gate_a=gate_a,
        gate_a_identity=gate_a_identity,
        candidate_identity=candidate_identity,
        final_full_preflight_identity=final_full_preflight_identity,
    )
    if (
        gate_b_epoch["publisher"]["actor"] != gate_b["publisher"]["actor"]
        or gate_b_epoch["publisher"]["qualification_session"]["session_id"]
        != gate_b["publisher"]["qualification_session"]["session_id"]
        or gate_b_epoch["publisher"]["qualification_session"]["lock_identities"]
        != gate_b["publisher"]["qualification_session"]["lock_identities"]
    ):
        raise BootstrapError("Gate-B epoch and approval were not rendered by one persistent owner")
    system_full = {role: planned[f"system.{role}"] for role in SYSTEM_TOOL_ROLES}
    repository_head = _observe_repository_head(
        repository,
        system_paths["git"],
        expected_identity=planned["system.git"],
    )
    if repository_head != candidate["repository_head"]:
        raise BootstrapError("repository HEAD drifted before campaign creation")
    captured = _capture_epoch(scripts=scripts, system_paths=system_paths)
    epoch_attestor = _check_epoch_toolchain(
        captured["manager_epoch"],
        scripts=scripts,
        system_full=system_full,
    )
    if captured["manager_epoch"] != gate_a["manager_epoch"] or captured["manager_epoch"] != gate_b_epoch["manager_epoch"]:
        raise BootstrapError("current manager/boot epoch differs from Gate-A/Gate-B authority")
    if (
        _observe_repository_head(
            repository,
            system_paths["git"],
            expected_identity=planned["system.git"],
        )
        != repository_head
    ):
        raise BootstrapError("repository HEAD drifted before campaign creation")
    timestamp = created_at_utc or _utc_now()
    _utc(timestamp, "bootstrap created_at_utc")

    authority.mkdir_exclusive(output)
    bootstrap_dir = authority.mkdir_exclusive(output / "bootstrap-authority")
    capture_record = {
        "candidate_identity": candidate_identity,
        "formal_arm_launch_authorized": False,
        "gate_a_receipt_identity": gate_a_identity,
        "gate_b_approval_identity": gate_b_identity,
        "manager_epoch": captured["manager_epoch"],
        "purpose": "manager epoch captured after Gate B for v4 campaign creation",
        "repository_head": repository_head,
        "run_nonce": output.name,
        "schema": CAPTURE_SCHEMA,
        "transcript": captured["transcript"],
    }
    capture_path = bootstrap_dir / "manager-epoch-capture.json"
    capture_source_identity = authority.write_exclusive(
        capture_path,
        authority.canonical_json(capture_record),
    )
    campaign_authority_dir = authority.mkdir_exclusive(output / "campaign-authority")
    package_dir = campaign_authority_dir / "package"
    snapshot_build = _build_repository_snapshot_sources(
        bootstrap_dir=bootstrap_dir,
        package_dir=package_dir,
        repository=repository,
        repository_head=repository_head,
        planned=planned,
        scripts=scripts,
        strict_paths=strict_paths,
        system_full=system_full,
    )
    source_specs, script_package_roles, input_package_roles = _package_roles(
        scripts=snapshot_build["staged_scripts"],
        system_paths=system_paths,
        strict_paths=snapshot_build["staged_inputs"],
        gate_a_path=gate_a_path,
        candidate_path=candidate_path,
        gate_b_path=gate_b_path,
        gate_b_epoch_path=gate_b_epoch_path,
        final_full_preflight_path=final_full_preflight_path,
        capture_path=capture_path,
        path_preregistration_path=path_preregistration_path,
        snapshot_archive_path=snapshot_build["archive_path"],
        snapshot_manifest_path=snapshot_build["manifest_path"],
        external_platform_path=snapshot_build["platform_path"],
    )
    expected_package_sources = {
        spec.role: authority.full_identity(authority.snapshot_regular(spec.path)) for spec in source_specs
    }
    package = authority.build_package(
        package_dir,
        source_specs,
        repository_head=repository_head,
        run_nonce=output.name,
        manager_epoch=captured["manager_epoch"],
    )
    _package_source_join(
        package_dir,
        expected_sources=expected_package_sources,
    )
    materialization, snapshot_identities = _materialize_repository_snapshot(
        campaign_dir=output,
        package_dir=package_dir,
        package_id=package["package_id"],
        created_at_utc=timestamp,
    )
    tools = {role: _payload_identity(package_dir, package_role) for role, package_role in script_package_roles.items()}
    if (
        tools["manager_attestor_v4"]["sha256"] != epoch_attestor["sha256"]
        or tools["manager_attestor_v4"]["size_bytes"] != epoch_attestor["size_bytes"]
    ):
        raise BootstrapError("sealed attestor copy differs from epoch attestor")
    tools["manager_attestor_v4"] = epoch_attestor
    tools.update({role: _detached_from_full(system_full[role]) for role in SYSTEM_TOOL_ROLES})
    inputs = _select_root_strict_input_identities(
        repository=repository,
        strict_paths=strict_paths,
        planned=planned,
        packaged_inputs={
            role: _payload_identity(package_dir, package_role)
            for role, package_role in input_package_roles.items()
        },
        snapshot_identities=snapshot_identities,
    )
    materialization_receipt = materialization["receipt_identity"]
    if not isinstance(materialization_receipt, Mapping):
        raise BootstrapError("repository snapshot materialization identity is malformed")
    inputs[SNAPSHOT_MATERIALIZATION_INPUT_ROLE] = dict(materialization_receipt)

    root = authority.build_campaign_root(
        output,
        package=package,
        repository_head=repository_head,
        run_nonce=output.name,
        manager_epoch=captured["manager_epoch"],
        authority_tools=tools,
        strict_inputs=inputs,
        created_at_utc=timestamp,
    )
    _validate_path_preregistration_against_root(
        path_preregistration,
        root,
        campaign_dir=output,
    )
    root_identity = authority.write_campaign_root(output, root)
    selection = authority.make_gate1_selection(
        root,
        campaign_root_identity=root_identity,
        tools=tools,
        inputs=inputs,
        created_at_utc=timestamp,
    )
    selection_identity = authority.write_gate1_selection(
        output / "campaign-root.json",
        root_identity,
        selection,
    )
    if (
        _observe_repository_head(
            repository,
            system_paths["git"],
            expected_identity=planned["system.git"],
        )
        != repository_head
    ):
        raise BootstrapError("repository HEAD drifted after selection; campaign is consumed")
    authority.verify_package(
        package_dir,
        expected_manager_epoch=captured["manager_epoch"],
        replay_external=True,
    )
    authority.replay_gate1_selection(
        output / "campaign-root.json",
        root_identity,
        selection_identity,
        current_manager_epoch=captured["manager_epoch"],
    )
    selection_path = Path(root["stage_topology"]["gate1_v4"]["selection_path"])
    if any(
        path.exists() or path.is_symlink() for path in authority.reserved_child_paths(root) if path != selection_path
    ):
        raise BootstrapError("a reserved post-selection child was created")
    formal_parent = authority.mkdir_exclusive(output / "formal-ab16")
    if any(formal_parent.iterdir()):
        raise BootstrapError("formal launch parent is not one fresh empty directory")
    if qualification_fd is None or qualification_lock_fds is None:
        raise BootstrapError("Gate-B qualification handoff capability is absent")
    qualification_handoff = _complete_gate_b_qualification_handoff(
        qualification_fd=qualification_fd,
        qualification_lock_fds=qualification_lock_fds,
        epoch_publisher=gate_b_epoch["publisher"],
        approval_publisher=gate_b["publisher"],
        gate_b_epoch_identity=gate_b_epoch_identity,
        gate_b_approval_identity=gate_b_identity,
        campaign_root_identity=root_identity,
        gate1_selection_identity=selection_identity,
    )
    return {
        "bootstrap_capture_source_identity": capture_source_identity,
        "campaign_dir": str(output),
        "campaign_root_identity": root_identity,
        "candidate_identity": candidate_identity,
        "formal_arm_launch_authorized": False,
        "formal_launch_parent": str(formal_parent),
        "gate1_selection_identity": selection_identity,
        "gate_a_receipt_identity": gate_a_identity,
        "gate_b_approval_identity": gate_b_identity,
        "gate_b_epoch_observation_identity": gate_b_epoch_identity,
        "gate_b_final_full_preflight_identity": final_full_preflight_identity,
        "gate_b_qualification_handoff": qualification_handoff,
        "organic_ab16_authorized": False,
        "package_id": package["package_id"],
        "path_preregistration_identity": inputs[PATH_PREREGISTRATION_INPUT_ROLE],
        "repository_snapshot_archive_identity": inputs[SNAPSHOT_ARCHIVE_INPUT_ROLE],
        "repository_snapshot_manifest_identity": inputs[SNAPSHOT_MANIFEST_INPUT_ROLE],
        "repository_snapshot_materialization_identity": materialization["receipt_identity"],
        "repository_snapshot_root": materialization["receipt"]["snapshot_root"],
        "repository_head": repository_head,
        "run_nonce": output.name,
        "schema": RESULT_SCHEMA,
        "status": "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED",
    }


def _add_common_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--gate-a-receipt", type=Path, required=True)
    parser.add_argument("--history-freeze-manifest", type=Path, required=True)
    parser.add_argument("--cuts-mandatory-schedule", type=Path, required=True)
    parser.add_argument("--legacy-control-a002", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    parser.add_argument(
        "--python3-13",
        type=Path,
        default=Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"),
    )
    parser.add_argument(
        "--attestor-python",
        type=Path,
        default=Path("/usr/bin/python3.14"),
    )
    parser.add_argument("--busctl", type=Path, default=Path("/usr/bin/busctl"))
    parser.add_argument("--git", type=Path, default=Path("/usr/bin/git"))
    parser.add_argument(
        "--libsystemd",
        type=Path,
        default=Path("/usr/lib/libsystemd.so.0"),
    )
    parser.add_argument("--sudo", type=Path, default=Path("/usr/bin/sudo"))
    parser.add_argument(
        "--systemctl",
        type=Path,
        default=Path("/usr/bin/systemctl"),
    )
    parser.add_argument(
        "--systemd-run",
        type=Path,
        default=Path("/usr/bin/systemd-run"),
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate = commands.add_parser(
        "candidate",
        help=("consume an external Gate-A receipt and write only one non-authorizing O_EXCL candidate"),
    )
    _add_common_cli_arguments(candidate)
    candidate.add_argument("--candidate-output", type=Path, required=True)
    bootstrap = commands.add_parser(
        "bootstrap",
        help=(
            "consume the Gate-A receipt/candidate and a distinct external "
            "Gate-B approval, then create v4 campaign authority"
        ),
    )
    _add_common_cli_arguments(bootstrap)
    bootstrap.add_argument("--offline-candidate", type=Path, required=True)
    bootstrap.add_argument("--gate-b-approval", type=Path, required=True)
    bootstrap.add_argument("--gate-b-qualification-fd", type=int, required=True)
    bootstrap.add_argument(
        "--gate-b-qualification-lock-fd",
        action="append",
        required=True,
    )
    return parser.parse_args(argv)


def _production_strict_inputs(
    repository: Path,
    args: argparse.Namespace,
) -> dict[str, Path]:
    return {
        "candidate_placements": (repository / "data" / "preprocessed" / "candidate_placements.json"),
        "canonical_rules": repository / "rules" / "canonical_rules.json",
        "cuts_mandatory_schedule": args.cuts_mandatory_schedule,
        "history_freeze_manifest": args.history_freeze_manifest,
        "legacy_control_a002": args.legacy_control_a002,
        "mandatory_instances": (repository / "data" / "preprocessed" / "mandatory_exact_instances.json"),
        "preflight_gate": repository / "scripts" / "preflight_gate.py",
        "project_lock": repository / "PROJECT_LOCK.md",
    }


def _cli_system_tools(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "attestor_python": args.attestor_python,
        "busctl": args.busctl,
        "git": args.git,
        "libsystemd": args.libsystemd,
        "python3_13": args.python3_13,
        "sudo": args.sudo,
        "systemctl": args.systemctl,
        "systemd_run": args.systemd_run,
    }


def _cli_qualification_lock_fds(values: Sequence[str]) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for value in values:
        path, separator, descriptor = value.rpartition("=")
        if (
            not separator
            or path not in GATE_B_QUALIFICATION_LOCK_PATHS
            or path in parsed
            or not descriptor.isdigit()
        ):
            raise BootstrapError("Gate-B qualification lock FD argument drifted")
        parsed[path] = int(descriptor)
    if set(parsed) != set(GATE_B_QUALIFICATION_LOCK_PATHS):
        raise BootstrapError("Gate-B qualification lock FD set drifted")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repository = _absolute(args.repository_root)
    try:
        _replay_prepackage_closure()
        if repository != Path(str(_BOOTSTRAP_BINDING["repository_root"])):
            raise BootstrapError("CLI repository root differs from the fixed Git top level")
        if args.command == "candidate":
            result = build_gate_a_candidate(
                output_path=args.candidate_output,
                gate_a_receipt=args.gate_a_receipt,
                repository_root=repository,
                target_campaign_dir=args.campaign_dir,
                strict_input_paths=_production_strict_inputs(repository, args),
                system_tool_paths=_cli_system_tools(args),
                created_at_utc=args.created_at_utc,
            )
        elif args.command == "bootstrap":
            result = bootstrap_campaign(
                campaign_dir=args.campaign_dir,
                repository_root=repository,
                gate_a_receipt=args.gate_a_receipt,
                offline_candidate=args.offline_candidate,
                gate_b_approval=args.gate_b_approval,
                strict_input_paths=_production_strict_inputs(repository, args),
                system_tool_paths=_cli_system_tools(args),
                qualification_fd=args.gate_b_qualification_fd,
                qualification_lock_fds=_cli_qualification_lock_fds(
                    args.gate_b_qualification_lock_fd
                ),
                created_at_utc=args.created_at_utc,
            )
        else:
            raise BootstrapError("unknown CLI command")
        _replay_prepackage_closure()
    except (authority.AuthorityError, BootstrapError) as exc:
        sys.stderr.buffer.write(
            authority.canonical_json(
                {
                    "error": str(exc),
                    "schema": RESULT_SCHEMA,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2
    sys.stdout.buffer.write(authority.canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
