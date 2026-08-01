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
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import select
import signal
import shutil
import socket
import stat
import subprocess
import sys
import threading
import types
from typing import Any, cast
import unicodedata
import zipfile


V4_RESEARCH_DIR = Path(__file__).resolve().parents[1] / "noncert_cuts_ab_trust_gate1_v4_20260724"
V4_AUTHORITY_PATH = V4_RESEARCH_DIR / "campaign_authority_v4.py"
AB16_RESEARCH_DIR = Path(__file__).resolve().parent
BUDGET_AUTHORITY_PATH = AB16_RESEARCH_DIR / "ab16_budget_authority_v1.py"


GATE_A_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-a-receipt-v3"
CANDIDATE_SCHEMA = "noncert-cuts-ab16-bootstrap-offline-candidate-v4"
GATE_B_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-b-approval-v7"
GATE_B_EPOCH_SCHEMA = "noncert-cuts-ab16-gate-b-epoch-observation-v5"
CAPTURE_SCHEMA = "noncert-cuts-ab16-bootstrap-manager-epoch-capture-v3"
RESULT_SCHEMA = "noncert-cuts-ab16-campaign-bootstrap-result-v6"
PATH_PREREGISTRATION_SCHEMA = "noncert-cuts-ab16-path-preregistration-v5"
FINAL_FULL_PREFLIGHT_SCHEMA = "noncert-cuts-ab16-gate-a-full-preflight-receipt-v7"
REPOSITORY_SNAPSHOT_SCHEMA = "noncert-cuts-ab16-repository-snapshot-v1"
SNAPSHOT_MATERIALIZATION_SCHEMA = "noncert-cuts-ab16-repository-snapshot-materialization-v1"
HISTORICAL_EXTERNAL_PLATFORM_SCHEMA = (
    "noncert-cuts-ab16-external-platform-assumptions-v2"
)
EXTERNAL_PLATFORM_SCHEMA = "noncert-cuts-ab16-external-platform-assumptions-v3"
RESOURCE_BUDGET_PROFILE_SCHEMA = "noncert-cuts-ab16-resource-budget-profile-v1"
BOOTSTRAP_BUDGET_CONTRACT_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-budget-contract-v1"
)
BOOTSTRAP_BUDGET_TERMINAL_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-budget-terminal-v1"
)
BOOTSTRAP_PACKAGE_FAILURE_CLOSEOUT_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-package-failure-closeout-v1"
)
FORMAL_ROOT_BUDGET_CONTRACT_SCHEMA = (
    "noncert-cuts-ab16-formal-root-budget-contract-v1"
)
FORMAL_ROOT_BUDGET_HANDOFF_SCHEMA = (
    "noncert-cuts-ab16-formal-root-budget-handoff-v2"
)
BOOTSTRAP_BROKER_RUNTIME_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-broker-runtime-v2"
)
BOOTSTRAP_RETAINED_DIRECTORY_HANDOFF_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-retained-directory-handoff-v1"
)
BOOTSTRAP_STAGING_HANDOFF_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-staging-handoff-v1"
)
BOOTSTRAP_BUDGET_ACCOUNT_HANDOFF_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-budget-account-handoff-v1"
)
BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA = (
    "noncert-cuts-ab16-bootstrap-structural-handoff-v1"
)
OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE = "formal-ab16/final-release"
OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES = 4 * 1024 * 1024
OUTSIDE_FINAL_RELEASE_RESERVATIONS = {
    "failure-terminal-release": "failure-terminal-release.json",
    "formal-root-replay-alternate-receipt": (
        "formal-root-replay-alternate.json"
    ),
    "formal-root-replay-primary-receipt": "formal-root-replay-primary.json",
    "success-dual-lock-release": "dual-lock-release.json",
}
RESOURCE_CALIBRATION_STAGES = (
    "FULL_PREFLIGHT",
    "GATE_B_QUALIFICATION",
    "FORMAL_ORGANIC_ARM",
)
RESOURCE_CALIBRATION_INPUT_ROLES = {
    "FULL_PREFLIGHT": "resource_calibration_full_preflight",
    "GATE_B_QUALIFICATION": "resource_calibration_gate_b_qualification",
    "FORMAL_ORGANIC_ARM": "resource_calibration_formal_organic_arm",
}
CALIBRATION_TOOL_PLANNED_ROLES = {
    "aggregator": "script.ab16_resource_calibration_aggregator_v1",
    "alternate_replayer": "script.replay_ab16_resource_calibration_alt_v1",
    "fd_loader": "script.ab16_resource_calibration_fd_loader_v1",
    "observer_harness": "script.ab16_resource_calibration_harness_v1",
    "package_verifier": "script.ab16_resource_calibration_package_v1",
    "primary_replayer": "script.replay_ab16_resource_calibration_v1",
    "protocol": "script.ab16_resource_calibration_v1",
    "runner": "script.ab16_resource_calibration_runner_v1",
    "workload": "script.ab16_resource_calibration_workloads_v1",
}

GATE_A_PURPOSE = "AB16_OFFLINE_SOURCE_SET_PREFLIGHT"
CANDIDATE_PURPOSE = "AB16_OFFLINE_NONAUTHORIZING_CANDIDATE"
GATE_B_PURPOSE = "AB16_FORMAL_CAMPAIGN_IDENTITY_CREATION"
GATE_B_EPOCH_PURPOSE = "AB16_GATE_B_MANAGER_EPOCH_OBSERVATION"
FINAL_FULL_PREFLIGHT_PURPOSE = "AB16_GATE_A_FULL_PREFLIGHT"
PATH_PREREGISTRATION_PURPOSE = "prospective_noncert_cuts_ab16_path_authority"
FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY = "same-fd-subreaper-ab16-qualification-runner-v4"
FINAL_FULL_PREFLIGHT_TIMEOUT_SCALE = "12"
FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME = "pytest-scratch"
FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME = "basetemp"
FINAL_FULL_PREFLIGHT_SCRATCH_POLICY = "fresh-no-overwrite-repo-local-retained-closed-tree-v1"
FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA = (
    "noncert-cuts-ab16-gate-a-preflight-publication-commit-v2"
)
GATE_B_RESOURCE_GATE_SCHEMA = "noncert-cuts-ab16-gate-b-resource-gate-v3"
PACKAGE_INDEPENDENT_REPLAY_SCHEMA = (
    "noncert-cuts-ab16-campaign-package-independent-replay-v2"
)
PACKAGE_SCHEMA = "noncert-cuts-campaign-authority-package-v5"
PACKAGE_MANIFEST_SCHEMA = "noncert-cuts-campaign-authority-manifest-v5"
PACKAGE_INDEPENDENT_VERIFIER_PACKAGE_PATH = (
    "payload/tool.package_independent_verifier_v1.py"
)
NATIVE_BUDGET_HELPER_PACKAGE_PATH = "payload/system.native_budget_helper.bin"
NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH = (
    "payload/tool.ab16_native_budget_helper_v1.py"
)
PACKAGE_BUDGET_RUNTIME_ROLE_PATHS = {
    "campaign-authority-v4": "payload/campaign_authority_v4.py",
    "ab16-authority-v2": "payload/tool.ab16_authority_v2.py",
    "ab16-budget-authority-v1": (
        "payload/tool.ab16_budget_authority_v1.py"
    ),
    "ab16-budget-broker-v1": "payload/tool.ab16_budget_broker_v1.py",
    "ab16-campaign-bootstrap-v2": (
        "payload/tool.ab16_campaign_bootstrap_v2.py"
    ),
    "ab16-closure-actor-v1": "payload/tool.ab16_closure_actor_v1.py",
    "ab16-final-release-actor-v1": (
        "payload/tool.ab16_final_release_actor_v1.py"
    ),
    "ab16-formal-campaign-v1": (
        "payload/tool.ab16_formal_campaign_v1.py"
    ),
    "ab16-formal-controller-v1": (
        "payload/tool.ab16_formal_controller_v1.py"
    ),
    "ab16-formal-launch-validator-v1": (
        "payload/tool.ab16_formal_launch_validator_v1.py"
    ),
    "ab16-formal-orchestrator-v1": (
        "payload/tool.ab16_formal_orchestrator_v1.py"
    ),
    "ab16-formal-success-verifier-v1": (
        "payload/tool.ab16_formal_success_verifier_v1.py"
    ),
    "ab16-outer-closeout-state-v1": (
        "payload/tool.ab16_outer_closeout_state_v1.py"
    ),
    "ab16-outer-guardian-v1": "payload/tool.ab16_outer_guardian_v1.py",
    "ab16-outer-refunit-closeout-v1": (
        "payload/tool.ab16_outer_refunit_closeout_v1.py"
    ),
    "ab16-recovery-closeout-v1": (
        "payload/tool.ab16_recovery_closeout_v1.py"
    ),
    "ab16-resource-admission-v1": (
        "payload/tool.ab16_resource_admission_v1.py"
    ),
    "replay-ab16-formal-root-alt-v1": (
        "payload/tool.replay_ab16_formal_root_alt_v1.py"
    ),
    "replay-ab16-formal-root-v1": (
        "payload/tool.replay_ab16_formal_root_v1.py"
    ),
    "systemd-unit-reference-v1": (
        "payload/tool.systemd_unit_reference_v1.py"
    ),
}
PACKAGE_BUDGET_RUNTIME_MODULE_NAMES = {
    "campaign-authority-v4": "campaign_authority_v4",
    "ab16-authority-v2": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_authority_v2"
    ),
    "ab16-budget-authority-v1": "ab16_budget_authority_v1",
    "ab16-budget-broker-v1": "ab16_budget_broker_v1",
    "ab16-campaign-bootstrap-v2": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_campaign_bootstrap_v2"
    ),
    "ab16-closure-actor-v1": "ab16_closure_actor_v1",
    "ab16-final-release-actor-v1": "ab16_final_release_actor_v1",
    "ab16-formal-campaign-v1": "ab16_formal_campaign_v1",
    "ab16-formal-controller-v1": "ab16_formal_controller_v1",
    "ab16-formal-launch-validator-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_formal_launch_validator_v1"
    ),
    "ab16-formal-orchestrator-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_formal_orchestrator_v1"
    ),
    "ab16-formal-success-verifier-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_formal_success_verifier_v1"
    ),
    "ab16-outer-closeout-state-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_outer_closeout_state_v1"
    ),
    "ab16-outer-guardian-v1": "ab16_outer_guardian_v1",
    "ab16-outer-refunit-closeout-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_outer_refunit_closeout_v1"
    ),
    "ab16-recovery-closeout-v1": "ab16_recovery_closeout_v1",
    "ab16-resource-admission-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "ab16_resource_admission_v1"
    ),
    "replay-ab16-formal-root-alt-v1": (
        "replay_ab16_formal_root_alt_v1"
    ),
    "replay-ab16-formal-root-v1": "replay_ab16_formal_root_v1",
    "systemd-unit-reference-v1": (
        "docs.research.noncert_cuts_ab16_20260724."
        "systemd_unit_reference_v1"
    ),
}
_AB16_PACKAGE_MODULE_PREFIX = "docs.research.noncert_cuts_ab16_20260724."
_V4_PACKAGE_MODULE_PREFIX = (
    "docs.research.noncert_cuts_ab_trust_gate1_v4_20260724."
)
PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES = {
    role: tuple(
        dict.fromkeys(
            (
                module_name,
                (
                    _V4_PACKAGE_MODULE_PREFIX
                    if role == "campaign-authority-v4"
                    else _AB16_PACKAGE_MODULE_PREFIX
                )
                + Path(package_path)
                .name.removeprefix("tool.")
                .removesuffix(".py"),
                Path(package_path).name.removeprefix("tool.").removesuffix(
                    ".py"
                ),
            )
        )
    )
    for role, package_path in PACKAGE_BUDGET_RUNTIME_ROLE_PATHS.items()
    for module_name in (PACKAGE_BUDGET_RUNTIME_MODULE_NAMES[role],)
}
PACKAGE_BUDGET_RUNTIME_ROLE_DEPENDENCIES = {
    "campaign-authority-v4": (),
    "ab16-authority-v2": (),
    "ab16-budget-authority-v1": (),
    "ab16-budget-broker-v1": (
        "ab16-budget-authority-v1",
        "ab16-outer-guardian-v1",
    ),
    "ab16-campaign-bootstrap-v2": (),
    "ab16-closure-actor-v1": (
        "ab16-budget-authority-v1",
        "ab16-budget-broker-v1",
        "ab16-resource-admission-v1",
    ),
    "ab16-final-release-actor-v1": ("ab16-budget-broker-v1",),
    "ab16-formal-campaign-v1": (
        "ab16-authority-v2",
        "ab16-budget-broker-v1",
        "ab16-closure-actor-v1",
        "ab16-final-release-actor-v1",
        "ab16-formal-controller-v1",
        "ab16-formal-launch-validator-v1",
        "ab16-formal-success-verifier-v1",
        "ab16-outer-closeout-state-v1",
        "ab16-outer-guardian-v1",
        "ab16-outer-refunit-closeout-v1",
        "ab16-resource-admission-v1",
        "replay-ab16-formal-root-alt-v1",
        "replay-ab16-formal-root-v1",
        "systemd-unit-reference-v1",
    ),
    "ab16-formal-controller-v1": (
        "ab16-authority-v2",
        "ab16-formal-launch-validator-v1",
        "ab16-resource-admission-v1",
    ),
    "ab16-formal-launch-validator-v1": (
        "ab16-authority-v2",
        "ab16-outer-closeout-state-v1",
    ),
    "ab16-formal-orchestrator-v1": (
        "ab16-authority-v2",
        "ab16-budget-broker-v1",
        "ab16-campaign-bootstrap-v2",
        "ab16-formal-launch-validator-v1",
        "ab16-formal-campaign-v1",
    ),
    "ab16-formal-success-verifier-v1": (
        "ab16-authority-v2",
        "ab16-formal-launch-validator-v1",
        "ab16-outer-closeout-state-v1",
        "ab16-resource-admission-v1",
    ),
    "ab16-outer-closeout-state-v1": (),
    "ab16-outer-guardian-v1": (
        "ab16-authority-v2",
        "ab16-formal-launch-validator-v1",
        "ab16-formal-success-verifier-v1",
        "ab16-outer-closeout-state-v1",
        "ab16-outer-refunit-closeout-v1",
    ),
    "ab16-outer-refunit-closeout-v1": (
        "ab16-authority-v2",
        "ab16-outer-closeout-state-v1",
        "ab16-resource-admission-v1",
    ),
    "ab16-recovery-closeout-v1": (
        "ab16-budget-authority-v1",
        "ab16-budget-broker-v1",
    ),
    "ab16-resource-admission-v1": (),
    "replay-ab16-formal-root-alt-v1": (),
    "replay-ab16-formal-root-v1": (
        "ab16-budget-broker-v1",
        "ab16-closure-actor-v1",
        "ab16-resource-admission-v1",
    ),
    "systemd-unit-reference-v1": (),
}
PACKAGE_BUDGET_RUNTIME_LOAD_ORDER = (
    "campaign-authority-v4",
    "ab16-authority-v2",
    "ab16-budget-authority-v1",
    "ab16-campaign-bootstrap-v2",
    "ab16-outer-closeout-state-v1",
    "ab16-resource-admission-v1",
    "systemd-unit-reference-v1",
    "ab16-formal-launch-validator-v1",
    "ab16-formal-success-verifier-v1",
    "ab16-outer-refunit-closeout-v1",
    "ab16-outer-guardian-v1",
    "ab16-budget-broker-v1",
    "ab16-closure-actor-v1",
    "ab16-final-release-actor-v1",
    "ab16-formal-controller-v1",
    "replay-ab16-formal-root-alt-v1",
    "replay-ab16-formal-root-v1",
    "ab16-formal-campaign-v1",
    "ab16-formal-orchestrator-v1",
    "ab16-recovery-closeout-v1",
)
PACKAGE_BUDGET_RUNTIME_SOURCE_KEYS = {
    role: (
        "script.campaign_authority_v4"
        if role == "campaign-authority-v4"
        else "script."
        + Path(package_path)
        .name.removeprefix("tool.")
        .removesuffix(".py")
    )
    for role, package_path in PACKAGE_BUDGET_RUNTIME_ROLE_PATHS.items()
}
PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA = (
    "noncert-cuts-ab16-package-selected-fd-transport-v1"
)
PACKAGE_SELECTED_FD_TRANSPORT_PATHS = {
    "authority": "payload/tool.ab16_authority_v2.py",
    "loader": "payload/tool.ab16_formal_loader_v1.py",
    "native_helper": NATIVE_BUDGET_HELPER_PACKAGE_PATH,
    "native_helper_wrapper": NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH,
    "python": "payload/system.python3_13.bin",
}
NATIVE_BUDGET_HELPER_SHA256 = (
    "65150434dc370596413e3e425e5cdcaa2d7960b8b181109f738588e8f40dca81"
)
NATIVE_BUDGET_HELPER_SIZE_BYTES = 16512
NATIVE_BUDGET_HELPER_MODE = 0o555
NATIVE_BUDGET_HELPER_BUILD_ID_SHA1 = (
    "808dbb57b4fd260e704cb7399e76d76fef2e3146"
)
PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES = 4 * 1024 * 1024
PACKAGE_INDEPENDENT_VERIFIER_TIMEOUT_SECONDS = 120
_ACTIVE_BOOTSTRAP_BUDGET_RUNTIME: dict[str, object] | None = None
FINAL_FULL_PREFLIGHT_KEYS = {
    "authorizations",
    "authority_ready_identity",
    "command",
    "detached_replay_identity",
    "duration_monotonic_ns",
    "exit_code",
    "finished_at_utc",
    "output_root_identity",
    "planned_source_set_digest",
    "pre_run_authority_identity",
    "qualification_runner_identity",
    "preflight_script_identity",
    "preflight_timeout_scale",
    "purpose",
    "pytest_collection",
    "pytest_collection_plugin_identity",
    "pytest_collection_protocol_identity",
    "pytest_scratch",
    "python_identity",
    "resource_admission",
    "resource_admission_source_identity",
    "resource_lock_release_identities",
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
PACKAGE_ROLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
RUN_NONCE_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{4,123}\Z")
APPROVAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{5,127}\Z")

GATE_B_OWNER_EXECUTION_STRATEGY = "persistent-owner-sealed-fd-oexcl-bootstrap-handoff-v1"
GATE_B_HANDOFF_REQUEST_SCHEMA = "noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v2"
GATE_B_HANDOFF_RESPONSE_SCHEMA = "noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v2"
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
SELECTED_BYTE_EXECUTION_STRATEGY_V1 = (
    "selected-byte-python-loader-fd-v1"
)
SELECTED_BYTE_EXECUTION_STRATEGY_V2 = (
    "selected-byte-python-loader-budget-fd-v2"
)
SELECTED_BYTE_EXECUTION_STRATEGY = SELECTED_BYTE_EXECUTION_STRATEGY_V2
OWNER_PUBLISH_EXECUTION_STRATEGY = "sealed-memfd-dirfd-oexcl-v1"
PACKAGE_VERIFIER_SELECTED_FD_LOADER_V1 = r"""
import hashlib
import os
import stat
import sys

def fail(code):
    os.write(2, (code + "\n").encode("ascii"))
    raise SystemExit(125)

if len(sys.argv) < 4:
    fail("PACKAGE_VERIFIER_LOADER_ARGV_INVALID")
try:
    verifier_fd = int(sys.argv[1])
    expected_size = int(sys.argv[2])
except ValueError:
    fail("PACKAGE_VERIFIER_LOADER_ARGV_INVALID")
expected_sha256 = sys.argv[3]
before = os.fstat(verifier_fd)
if (
    verifier_fd < 3
    or expected_size <= 0
    or len(expected_sha256) != 64
    or any(ch not in "0123456789abcdef" for ch in expected_sha256)
    or not stat.S_ISREG(before.st_mode)
    or before.st_size != expected_size
):
    fail("PACKAGE_VERIFIER_LOADER_IDENTITY_INVALID")
raw = bytearray()
offset = 0
while offset < expected_size:
    block = os.pread(verifier_fd, min(1024 * 1024, expected_size - offset), offset)
    if not block:
        fail("PACKAGE_VERIFIER_LOADER_SHORT_READ")
    raw.extend(block)
    offset += len(block)
after = os.fstat(verifier_fd)
signature = lambda value: tuple(
    int(getattr(value, field))
    for field in (
        "st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid",
        "st_size", "st_mtime_ns", "st_ctime_ns",
    )
)
if (
    signature(before) != signature(after)
    or hashlib.sha256(raw).hexdigest() != expected_sha256
):
    fail("PACKAGE_VERIFIER_LOADER_IDENTITY_DRIFT")
origin = "/proc/self/fd/" + str(verifier_fd)
sys.argv = [origin] + sys.argv[4:]
globals()["__file__"] = origin
globals()["__cached__"] = None
globals()["__package__"] = None
globals()["__spec__"] = None
exec(compile(bytes(raw), origin, "exec", dont_inherit=True), globals(), globals())
"""

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

SELECTED_BYTE_LAUNCH_V2 = r"""
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
if set(expected) != {
    "authority",
    "loader",
    "native_helper",
    "native_helper_wrapper",
    "python",
}:
    fail("IDENTITY_KEYS")
if transport == "systemd-openfile":
    if (
        os.environ.get("LISTEN_PID") != str(os.getpid())
        or os.environ.get("LISTEN_FDS") != "6"
        or os.environ.get("LISTEN_FDNAMES")
        != (
            "ab16-python:ab16-loader:ab16-authority:"
            "ab16-native-helper-wrapper:ab16-native-helper:"
            "ab16-budget-broker"
        )
    ):
        fail("OPENFILE_ENV")
elif transport != "direct":
    fail("TRANSPORT")
read_selected(3, expected["python"], "PYTHON")
read_selected(4, expected["loader"], "LOADER")
read_selected(5, expected["authority"], "AUTHORITY")
read_selected(
    6,
    expected["native_helper_wrapper"],
    "NATIVE_HELPER_WRAPPER",
)
read_selected(7, expected["native_helper"], "NATIVE_HELPER")
broker_socket = os.fstat(8)
if not stat.S_ISSOCK(broker_socket.st_mode):
    fail("BUDGET_BROKER_SOCKET")
for descriptor in (3, 4, 5, 6, 7, 8):
    os.set_inheritable(descriptor, True)
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
            "--native-helper-wrapper-fd",
            "6",
            "--native-helper-wrapper-identity",
            json.dumps(
                expected["native_helper_wrapper"],
                sort_keys=True,
                separators=(",", ":"),
            ),
            "--native-helper-fd",
            "7",
            "--native-helper-identity",
            json.dumps(
                expected["native_helper"],
                sort_keys=True,
                separators=(",", ":"),
            ),
            "--budget-broker-fd",
            "8",
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

prepared_selection = None
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
            prepared_identity = {
                "path": output_path,
                "sha256": hashlib.sha256(rendered).hexdigest(),
                "size_bytes": len(rendered),
            }
            if expected_kind == "selection":
                prepared_selection = {
                    "identity": prepared_identity,
                    "raw": rendered,
                    "descriptor": rendered_fd,
                }
                rendered_fd = -1
                published_identity = prepared_identity
            else:
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
            if rendered_fd >= 0:
                os.close(rendered_fd)
        send(
            {
                "actor": actor,
                "artifact_identity": published_identity,
                "kind": expected_kind,
                "schema_version": response_schema,
                "sequence": expected_sequence,
                "status": (
                    "PREPARED"
                    if expected_kind == "selection"
                    else "PUBLISHED"
                ),
            }
        )
    except SystemExit:
        raise
    except BaseException as exc:
        stop(type(exc).__name__ + "_" + str(exc))

try:
    if prepared_selection is None:
        stop("SELECTION_PREPARE_ABSENT")
    commit_raw = control.recv(max_frame + 1)
    if not commit_raw or len(commit_raw) > max_frame:
        stop("SELECTION_COMMIT_SIZE")
    commit = parse_canonical(commit_raw, "SELECTION_COMMIT")
    if (
        set(commit)
        != {
            "broker_binding_receipt_identity",
            "kind",
            "prepared_selection_identity",
            "preregistration_receipt_identity",
            "schema_version",
            "sequence",
        }
        or commit["schema_version"] != request_schema
        or commit["sequence"] != 3
        or commit["kind"] != "selection-commit"
        or commit["prepared_selection_identity"]
        != prepared_selection["identity"]
        or validate_message_identity(
            commit["broker_binding_receipt_identity"],
            "BROKER_BINDING_RECEIPT",
        )
        != commit["broker_binding_receipt_identity"]
        or validate_message_identity(
            commit["preregistration_receipt_identity"],
            "PREREGISTRATION_RECEIPT",
        )
        != commit["preregistration_receipt_identity"]
    ):
        stop("SELECTION_COMMIT_DRIFT")
    output_path = prepared_selection["identity"]["path"]
    parent = os.path.dirname(output_path)
    basename = os.path.basename(output_path)
    directory_fd = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        expected_frame = (
            "OK "
            + prepared_selection["identity"]["sha256"]
            + " "
            + str(prepared_selection["identity"]["size_bytes"])
            + "\n"
        ).encode("ascii")
        actual_frame = publisher_child(
            prepared_selection["descriptor"],
            directory_fd,
            basename,
        )
        if actual_frame != expected_frame:
            stop("SELECTION_COMMIT_UNCERTAIN")
        published_identity = readback(
            directory_fd,
            basename,
            output_path,
            prepared_selection["raw"],
        )
    finally:
        os.close(directory_fd)
        os.close(prepared_selection["descriptor"])
        prepared_selection = None
    send(
        {
            "actor": actor,
            "artifact_identity": published_identity,
            "broker_binding_receipt_identity": commit[
                "broker_binding_receipt_identity"
            ],
            "kind": "selection-commit",
            "preregistration_receipt_identity": commit[
                "preregistration_receipt_identity"
            ],
            "schema_version": response_schema,
            "sequence": 3,
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
        "sequence": 4,
    }:
        stop("HANDOFF_SEQUENCE")
    send(
        {
            "actor": actor,
            "schema_version": response_schema,
            "sequence": 4,
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
FORMAL_LAUNCH_OWNER_DRIVER_V2 = (
    FORMAL_LAUNCH_OWNER_DRIVER_V1.replace(
        "noncert-cuts-ab16-formal-launch-owner-request-v1",
        "noncert-cuts-ab16-formal-launch-owner-request-v2",
    ).replace(
        "noncert-cuts-ab16-formal-launch-owner-response-v1",
        "noncert-cuts-ab16-formal-launch-owner-response-v2",
    ).replace(
        '''    if set(selected) != {"authority", "loader", "python"}:
        raise RuntimeError("SELECTED_IDENTITY_KEYS")
    for name in ("authority", "loader", "python"):
        selected[name] = validate_mode_identity(selected[name], name.upper())''',
        '''    if set(selected) != {
        "authority",
        "loader",
        "native_helper",
        "native_helper_wrapper",
        "python",
    }:
        raise RuntimeError("SELECTED_IDENTITY_KEYS")
    for name in (
        "authority",
        "loader",
        "native_helper",
        "native_helper_wrapper",
        "python",
    ):
        selected[name] = validate_mode_identity(selected[name], name.upper())''',
    ).replace(
        '''                os.execve(
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
                )''',
        '''                os.execve(
                    "/proc/self/fd/3",
                    [
                        selected["python"]["path"],
                        "-I",
                        "-B",
                        "/proc/self/fd/4",
                        "--loader-identity",
                        canonical_text(selected["loader"]),
                        "--authority-fd",
                        "5",
                        "--authority-identity",
                        canonical_text(selected["authority"]),
                        "--campaign-dir",
                        context["campaign_dir"],
                        "--role",
                        role,
                        "--",
                        *role_argv,
                    ],
                    clean,
                )''',
    )
)

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
    "ab16_artifact_cohort_v1": "ab16_artifact_cohort_v1.py",
    "ab16_arm_attempt_closure_v1": "ab16_arm_attempt_closure_v1.py",
    "ab16_authority_v1": "ab16_authority_v1.py",
    "ab16_authority_v2": "ab16_authority_v2.py",
    "ab16_budget_authority_v1": "ab16_budget_authority_v1.py",
    "ab16_budget_broker_v1": "ab16_budget_broker_v1.py",
    "ab16_budgeted_writers_v1": "ab16_budgeted_writers_v1.py",
    "ab16_campaign_bootstrap_v1": "ab16_campaign_bootstrap_v1.py",
    "ab16_campaign_bootstrap_v2": "ab16_campaign_bootstrap_v2.py",
    "ab16_closure_actor_v1": "ab16_closure_actor_v1.py",
    "ab16_contract_v1": "ab16_contract_v1.py",
    "ab16_formal_campaign_v1": "ab16_formal_campaign_v1.py",
    "ab16_formal_controller_v1": "ab16_formal_controller_v1.py",
    "ab16_formal_launch_authority_v1": "ab16_formal_launch_authority_v1.py",
    "ab16_formal_launch_validator_v1": "ab16_formal_launch_validator_v1.py",
    "ab16_formal_loader_v1": "ab16_formal_loader_v1.py",
    "ab16_formal_orchestrator_v1": "ab16_formal_orchestrator_v1.py",
    "ab16_formal_success_verifier_v1": "ab16_formal_success_verifier_v1.py",
    "ab16_final_release_actor_v1": "ab16_final_release_actor_v1.py",
    "ab16_gate_b_qualification_v1": "ab16_gate_b_qualification_v1.py",
    "ab16_native_budget_helper_v1": "ab16_native_budget_helper_v1.py",
    "ab16_outer_closeout_state_v1": "ab16_outer_closeout_state_v1.py",
    "ab16_outer_guardian_v1": "ab16_outer_guardian_v1.py",
    "ab16_outer_refunit_closeout_v1": "ab16_outer_refunit_closeout_v1.py",
    "ab16_package_writer_inventory_v1": "ab16_package_writer_inventory_v1.py",
    "ab16_preflight_qualification_v1": "ab16_preflight_qualification_v1.py",
    "ab16_pytest_collection_plugin_v1": "ab16_pytest_collection_plugin_v1.py",
    "ab16_pytest_collection_protocol_v1": "ab16_pytest_collection_protocol_v1.py",
    "ab16_recovery_closeout_v1": "ab16_recovery_closeout_v1.py",
    "ab16_resource_admission_v1": "ab16_resource_admission_v1.py",
    "ab16_resource_calibration_aggregator_v1": (
        "ab16_resource_calibration_aggregator_v1.py"
    ),
    "ab16_resource_calibration_fd_loader_v1": (
        "ab16_resource_calibration_fd_loader_v1.py"
    ),
    "ab16_resource_calibration_harness_v1": (
        "ab16_resource_calibration_harness_v1.py"
    ),
    "ab16_resource_calibration_package_v1": (
        "ab16_resource_calibration_package_v1.py"
    ),
    "ab16_resource_calibration_runner_v1": (
        "ab16_resource_calibration_runner_v1.py"
    ),
    "ab16_resource_calibration_v1": "ab16_resource_calibration_v1.py",
    "ab16_resource_calibration_workloads_v1": (
        "ab16_resource_calibration_workloads_v1.py"
    ),
    "ab16_terminal_gate_v1": "ab16_terminal_gate_v1.py",
    "ab16_terminal_gate_v2": "ab16_terminal_gate_v2.py",
    "ab16_terminal_gate_v3": "ab16_terminal_gate_v3.py",
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
    "package_independent_verifier_v1": "package_independent_verifier_v1.py",
    "replay_ab16_resource_calibration_alt_v1": (
        "replay_ab16_resource_calibration_alt_v1.py"
    ),
    "replay_ab16_resource_calibration_v1": (
        "replay_ab16_resource_calibration_v1.py"
    ),
    "replay_ab16_formal_root_alt_v1": (
        "replay_ab16_formal_root_alt_v1.py"
    ),
    "replay_ab16_formal_root_v1": "replay_ab16_formal_root_v1.py",
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
        "native_budget_helper",
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
    "ab16_gate_b_pre_full_resource_gate": "input.ab16_gate_b_pre_full_resource_gate.json",
    "ab16_gate_b_pre_publication_resource_gate": (
        "input.ab16_gate_b_pre_publication_resource_gate.json"
    ),
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
PACKAGE_INDEPENDENT_REPLAY_INPUT_ROLE = "ab16_package_independent_replay"
RESOURCE_BUDGET_PROFILE_INPUT_ROLE = "ab16_resource_budget_profile"
RESOURCE_BUDGET_PROFILE_PACKAGE_ROLE = "input.ab16_resource_budget_profile.json"


class BootstrapError(RuntimeError):
    """A staged bootstrap precondition failed closed."""


class _BootstrapMechanicalError(RuntimeError):
    """Stable error raised by the sole pre-package mechanical authority."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _BootstrapSnapshot:
    """One stable same-FD byte capture owned by the bootstrap source."""

    path: Path
    data: bytes
    sha256: str
    stat_result: os.stat_result

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class _BootstrapSourceSpec:
    """One package member and its predeclared source path."""

    role: str
    path: Path
    parse_json: bool = False


def _bootstrap_canonical_json(value: object) -> bytes:
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


def _bootstrap_strict_loads(raw: bytes, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _BootstrapMechanicalError(
                    "JSON_DUPLICATE_KEY",
                    f"{label}: duplicate key {key!r}",
                )
            result[key] = value
        return result

    def reject_float(value: str) -> object:
        raise _BootstrapMechanicalError(
            "JSON_FLOAT_REJECTED",
            f"{label}: floating point value {value!r}",
        )

    def reject_constant(value: str) -> object:
        raise _BootstrapMechanicalError(
            "JSON_CONSTANT_REJECTED",
            f"{label}: invalid constant {value!r}",
        )

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _BootstrapMechanicalError(
            "JSON_INVALID",
            f"{label}: invalid strict JSON: {exc}",
        ) from exc


def _bootstrap_snapshot_regular(
    path: Path | str,
    *,
    size_limit: int = 1 << 31,
) -> _BootstrapSnapshot:
    """Capture one regular file without executing any captured byte."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    _bootstrap_reject_symlink_chain(absolute)
    before_path = os.stat(absolute, follow_symlinks=False)
    if (
        not stat.S_ISREG(before_path.st_mode)
        or before_path.st_nlink != 1
        or before_path.st_size < 0
        or before_path.st_size > size_limit
    ):
        raise _BootstrapMechanicalError(
            "INPUT_INVALID",
            f"input is not one bounded single-link regular file: {absolute}",
        )
    descriptor = os.open(
        absolute,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        before_fd = os.fstat(descriptor)
        if _fd_signature(before_path) != _fd_signature(before_fd):
            raise _BootstrapMechanicalError(
                "INPUT_RACE",
                f"input changed before read: {absolute}",
            )
        raw = _read_stable_fd(
            descriptor,
            limit=size_limit,
            label=f"bootstrap input {absolute}",
        )
        after_fd = os.fstat(descriptor)
        after_path = os.stat(absolute, follow_symlinks=False)
        if (
            _fd_signature(before_fd) != _fd_signature(after_fd)
            or _fd_signature(after_fd) != _fd_signature(after_path)
        ):
            raise _BootstrapMechanicalError(
                "INPUT_RACE",
                f"input identity changed during read: {absolute}",
            )
    finally:
        os.close(descriptor)
    return _BootstrapSnapshot(
        path=absolute,
        data=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        stat_result=after_fd,
    )


def _bootstrap_detached_identity(
    snapshot: _BootstrapSnapshot,
) -> dict[str, object]:
    return {
        "path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size,
    }


def _bootstrap_full_identity(
    snapshot: _BootstrapSnapshot,
    *,
    requested_path: str | None = None,
) -> dict[str, object]:
    mode = stat.S_IMODE(snapshot.stat_result.st_mode)
    result: dict[str, object] = {
        "device": snapshot.stat_result.st_dev,
        "inode": snapshot.stat_result.st_ino,
        "mode": mode,
        "mode_octal": f"{mode:04o}",
        "path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size,
    }
    if requested_path is not None:
        result["requested_path"] = requested_path
    return result


def _bootstrap_snapshot_tool(
    path: Path | str,
    *,
    size_limit: int = 1 << 30,
) -> tuple[bytes, dict[str, object]]:
    requested = str(Path(os.path.abspath(os.fspath(path))))
    resolved = os.path.realpath(requested)
    if not os.path.isabs(resolved):
        raise _BootstrapMechanicalError(
            "TOOL_PATH_INVALID",
            f"tool did not resolve absolutely: {requested}",
        )
    snapshot = _bootstrap_snapshot_regular(resolved, size_limit=size_limit)
    if os.path.realpath(requested) != resolved:
        raise _BootstrapMechanicalError(
            "TOOL_PATH_RACE",
            f"tool symlink chain changed: {requested}",
        )
    return snapshot.data, _bootstrap_full_identity(
        snapshot,
        requested_path=requested,
    )


def _bootstrap_validate_detached_identity(
    value: object,
    label: str,
) -> Mapping[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"path", "sha256", "size_bytes"}
        or type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
    ):
        raise _BootstrapMechanicalError(
            "IDENTITY_INVALID",
            f"{label}: detached identity is malformed",
        )
    return value


def _bootstrap_validate_full_identity(
    value: object,
    label: str,
) -> Mapping[str, object]:
    required = {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }
    if (
        not isinstance(value, Mapping)
        or frozenset(value)
        not in {
            frozenset(required),
            frozenset(required | {"requested_path"}),
        }
        or type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] <= 0
        or type(value["mode"]) is not int
        or value["mode_octal"] != f"{value['mode']:04o}"
        or type(value["device"]) is not int
        or type(value["inode"]) is not int
        or value["inode"] <= 0
    ):
        raise _BootstrapMechanicalError(
            "TOOL_IDENTITY_INVALID",
            f"{label}: full identity is malformed",
        )
    return value


def _bootstrap_write_exclusive(
    path: Path | str,
    raw: bytes,
    *,
    mode: int = 0o600,
) -> dict[str, object]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    _bootstrap_reject_symlink_chain(absolute.parent)
    parent_fd = os.open(
        absolute.parent,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            absolute.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            mode,
            dir_fd=parent_fd,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise _BootstrapMechanicalError(
                    "OUTPUT_SHORT_WRITE",
                    f"short write: {absolute}",
                )
            offset += written
        os.fsync(descriptor)
        if os.fstat(descriptor).st_size != len(raw):
            raise _BootstrapMechanicalError(
                "OUTPUT_SHORT_WRITE",
                f"output size mismatch: {absolute}",
            )
        os.close(descriptor)
        descriptor = None
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise _BootstrapMechanicalError(
            "NO_OVERWRITE_COLLISION",
            f"refusing to overwrite: {absolute}",
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)
    return _bootstrap_detached_identity(
        _bootstrap_snapshot_regular(absolute)
    )


def _bootstrap_mkdir_exclusive(
    path: Path | str,
    *,
    mode: int = 0o755,
) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    _bootstrap_reject_symlink_chain(absolute.parent)
    try:
        os.mkdir(absolute, mode)
    except FileExistsError as exc:
        raise _BootstrapMechanicalError(
            "NO_OVERWRITE_COLLISION",
            f"directory already exists: {absolute}",
        ) from exc
    return absolute


def _bootstrap_reject_symlink_chain(
    path: Path,
    *,
    missing_leaf: bool = False,
) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if missing_leaf and index == len(parts) - 1:
                return
            raise _BootstrapMechanicalError(
                "PATH_MISSING",
                f"path component is missing: {current}",
            ) from None
        if stat.S_ISLNK(metadata.st_mode):
            raise _BootstrapMechanicalError(
                "SYMLINK_REJECTED",
                f"symlink path component rejected: {current}",
            )


def _bootstrap_validate_manager_epoch(
    value: object,
) -> Mapping[str, Any]:
    """Mechanically validate the fixed v4 epoch envelope.

    The independent Gate-A/Gate-B consumers retain the semantic replay.  This
    pre-package actor only checks the complete byte-level envelope and its
    cross-field source identities; it never executes the planned authority
    implementation.
    """

    required = {
        "attestation_toolchain",
        "attestor_ast_audit",
        "boot_id",
        "capture_protocol",
        "dbus_unique_owner",
        "manager_executable",
        "manager_features",
        "manager_pid",
        "manager_pid_starttime",
        "manager_version",
        "observation_toolchain",
        "schema",
    }
    record = _exact_keys(value, required, "manager epoch")
    if (
        record["schema"] != "noncert-cuts-manager-boot-epoch-v4"
        or record["capture_protocol"]
        != "double-unprivileged-join-plus-read-only-sudo-attestation-v4"
        or type(record["manager_pid"]) is not int
        or record["manager_pid"] <= 0
        or type(record["manager_pid_starttime"]) is not int
        or record["manager_pid_starttime"] <= 0
    ):
        raise _BootstrapMechanicalError(
            "MANAGER_EPOCH_INVALID",
            "manager epoch scalar fields are invalid",
        )
    for group, roles in (
        (record["observation_toolchain"], ("busctl",)),
        (
            record["attestation_toolchain"],
            ("attestor", "python", "sudo"),
        ),
    ):
        checked = _exact_keys(group, set(roles), "manager epoch toolchain")
        for role in roles:
            _bootstrap_validate_full_identity(
                checked[role],
                f"manager epoch {role} identity",
            )
    _bootstrap_validate_full_identity(
        record["manager_executable"],
        "manager executable identity",
    )
    return record


def _bootstrap_validate_manager_epoch_capture_transcript(
    value: object,
    *,
    expected_epoch: object | None = None,
) -> Mapping[str, Any]:
    transcript = _exact_keys(
        value,
        {"capture_protocol", "rounds", "schema"},
        "manager epoch capture transcript",
    )
    if (
        transcript["schema"]
        != "noncert-cuts-manager-boot-epoch-capture-transcript-v4"
        or transcript["capture_protocol"]
        != "two-round-before-read-only-attestor-after-transcript-v4"
        or not isinstance(transcript["rounds"], list)
        or len(transcript["rounds"]) != 2
    ):
        raise _BootstrapMechanicalError(
            "MANAGER_TRANSCRIPT_INVALID",
            "manager epoch capture transcript framing drifted",
        )
    previous_finished = 0
    for index, untyped in enumerate(transcript["rounds"], start=1):
        record = _exact_keys(
            untyped,
            {
                "attestation_toolchain",
                "attestor_ast_audit",
                "attestor_invocation",
                "observation_toolchain",
                "observation_finished_monotonic_ns",
                "observation_started_monotonic_ns",
                "privileged_attestation",
                "round_index",
                "unprivileged_after",
                "unprivileged_before",
            },
            f"manager epoch transcript round {index}",
        )
        started = record["observation_started_monotonic_ns"]
        finished = record["observation_finished_monotonic_ns"]
        if (
            record["round_index"] != index
            or type(started) is not int
            or type(finished) is not int
            or started <= previous_finished
            or finished <= started
            or record["unprivileged_before"]
            != record["unprivileged_after"]
        ):
            raise _BootstrapMechanicalError(
                "MANAGER_TRANSCRIPT_INVALID",
                "manager epoch transcript ordering or join drifted",
            )
        previous_finished = finished
    if expected_epoch is not None:
        expected = _bootstrap_validate_manager_epoch(expected_epoch)
        for round_record in transcript["rounds"]:
            observed = round_record["unprivileged_after"]
            for field in (
                "boot_id",
                "dbus_unique_owner",
                "manager_features",
                "manager_pid",
                "manager_pid_starttime",
                "manager_version",
            ):
                if observed.get(field) != expected[field]:
                    raise _BootstrapMechanicalError(
                        "MANAGER_EPOCH_DRIFT",
                        "manager transcript does not join its expected epoch",
                    )
    return transcript


class _BootstrapMechanicalAuthority:
    """The sole executable pre-package authority surface.

    Planned project sources remain data: this object never imports, compiles,
    or executes them.  The independently accepted package may later launch
    package-pinned roles from retained descriptors.
    """

    AB16_ARMS = ("control", "treatment")
    AB16_CONFIGURATIONS = (
        "region-capacity",
        "shape-packing-hall",
        "power-hitting-set",
        "bundle",
    )
    AB16_ORDERS = ("ab", "ba")
    AuthorityError = _BootstrapMechanicalError
    REQUIRED_GATE1_TOOL_ROLES = frozenset(
        {
            "attestor_python",
            "busctl",
            "campaign_authority_v4",
            "gate1_campaign_bootstrap_v4",
            "gate1_campaign_driver_v4",
            "gate1_campaign_execution_v4",
            "gate1_payload_v4",
            "gate1_unit_orchestrator_v4",
            "independent_arithmetic_v4",
            "manager_attestor_v4",
            "positive_control_formal_v4",
            "positive_control_gate_v4",
            "positive_control_v4",
            "python3_13",
            "resource_lifecycle_v4",
            "resource_verifier_v4",
            "sudo",
            "systemctl",
            "systemd_run",
        }
    )
    SourceSpec = _BootstrapSourceSpec
    json = json

    canonical_json = staticmethod(_bootstrap_canonical_json)
    detached_identity = staticmethod(_bootstrap_detached_identity)
    full_identity = staticmethod(_bootstrap_full_identity)
    mkdir_exclusive = staticmethod(_bootstrap_mkdir_exclusive)
    snapshot_regular = staticmethod(_bootstrap_snapshot_regular)
    snapshot_tool = staticmethod(_bootstrap_snapshot_tool)
    strict_loads = staticmethod(_bootstrap_strict_loads)
    validate_detached_identity = staticmethod(
        _bootstrap_validate_detached_identity
    )
    validate_manager_epoch = staticmethod(
        _bootstrap_validate_manager_epoch
    )
    validate_manager_epoch_capture_transcript = staticmethod(
        _bootstrap_validate_manager_epoch_capture_transcript
    )
    write_exclusive = staticmethod(_bootstrap_write_exclusive)
    _reject_symlink_chain = staticmethod(_bootstrap_reject_symlink_chain)

    def build_package(
        self,
        package_dir: Path | str,
        sources: Sequence[_BootstrapSourceSpec],
        *,
        repository_head: str,
        run_nonce: str,
        manager_epoch: Mapping[str, object],
    ) -> dict[str, object]:
        """Build the sealed package without executing any source member."""

        if (
            GIT_SHA_RE.fullmatch(repository_head) is None
            or not run_nonce
            or len(run_nonce) > 128
            or not sources
        ):
            raise _BootstrapMechanicalError(
                "PACKAGE_INPUT_INVALID",
                "package HEAD, nonce, or source set is invalid",
            )
        self.validate_manager_epoch(manager_epoch)
        roles = [spec.role for spec in sources]
        if (
            len(set(roles)) != len(roles)
            or any(
                PACKAGE_ROLE_RE.fullmatch(role) is None
                or role in {"SHA256SUMS", "package-manifest.json"}
                or "/" in role
                for role in roles
            )
        ):
            raise _BootstrapMechanicalError(
                "SOURCE_SET_INVALID",
                "package source roles are invalid or duplicated",
            )
        output = self.mkdir_exclusive(package_dir)
        payload = self.mkdir_exclusive(output / "payload")
        snapshots = {
            spec.role: self.snapshot_regular(spec.path)
            for spec in sources
        }
        external_sources: list[dict[str, object]] = []
        members: list[dict[str, object]] = []
        member_raw: dict[str, bytes] = {}
        for spec in sorted(sources, key=lambda item: item.role):
            snapshot = snapshots[spec.role]
            if spec.parse_json:
                self.strict_loads(
                    snapshot.data,
                    f"package source {spec.role}",
                )
            relative = f"payload/{spec.role}"
            identity = self.write_exclusive(
                payload / spec.role,
                snapshot.data,
            )
            members.append(
                {
                    "path": relative,
                    "sha256": identity["sha256"],
                    "size_bytes": identity["size_bytes"],
                }
            )
            external_sources.append(
                {
                    "package_path": relative,
                    "parse_json": spec.parse_json,
                    "role": spec.role,
                    "source_identity": self.full_identity(snapshot),
                }
            )
            member_raw[relative] = snapshot.data
        manifest = {
            "authorization_semantics": (
                "byte qualification only; package PASS cannot launch any child"
            ),
            "external_sources": external_sources,
            "manager_epoch": dict(manager_epoch),
            "package_members": members,
            "repository_head": repository_head,
            "run_nonce": run_nonce,
            "schema": PACKAGE_MANIFEST_SCHEMA,
            "seal_contract": {
                "package_id": "sha256(SHA256SUMS exact bytes)",
                "sha256sums_domain": (
                    "all regular files below package except SHA256SUMS"
                ),
                "writes_after_seal": "forbidden",
            },
        }
        manifest_raw = self.canonical_json(manifest)
        manifest_identity = self.write_exclusive(
            output / "package-manifest.json",
            manifest_raw,
        )
        member_raw["package-manifest.json"] = manifest_raw
        seal_raw = "".join(
            f"{hashlib.sha256(member_raw[path]).hexdigest()}  {path}\n"
            for path in sorted(member_raw)
        ).encode("ascii")
        seal_identity = self.write_exclusive(
            output / "SHA256SUMS",
            seal_raw,
        )
        result = {
            "manifest_identity": manifest_identity,
            "package_dir": str(output),
            "package_id": seal_identity["sha256"],
            "schema": PACKAGE_SCHEMA,
            "seal_identity": seal_identity,
            "status": "SEALED",
        }
        replay = self.verify_package(
            output,
            expected_manager_epoch=manager_epoch,
            replay_external=True,
        )
        if replay["package_id"] != result["package_id"]:
            raise _BootstrapMechanicalError(
                "PACKAGE_REPLAY_DRIFT",
                "bootstrap package replay did not join its seal",
            )
        return result

    def verify_package(
        self,
        package_dir: Path | str,
        *,
        expected_manager_epoch: Mapping[str, object],
        replay_external: bool,
    ) -> dict[str, object]:
        """Mechanically replay the package; the later role remains independent."""

        self.validate_manager_epoch(expected_manager_epoch)
        root = Path(os.path.abspath(os.fspath(package_dir)))
        manifest_snapshot = self.snapshot_regular(
            root / "package-manifest.json"
        )
        seal_snapshot = self.snapshot_regular(root / "SHA256SUMS")
        manifest = _exact_keys(
            self.strict_loads(
                manifest_snapshot.data,
                "package manifest",
            ),
            {
                "authorization_semantics",
                "external_sources",
                "manager_epoch",
                "package_members",
                "repository_head",
                "run_nonce",
                "schema",
                "seal_contract",
            },
            "package manifest",
        )
        if (
            manifest["schema"] != PACKAGE_MANIFEST_SCHEMA
            or manifest["manager_epoch"] != expected_manager_epoch
            or self.canonical_json(manifest) != manifest_snapshot.data
            or not isinstance(manifest["package_members"], list)
            or not isinstance(manifest["external_sources"], list)
        ):
            raise _BootstrapMechanicalError(
                "PACKAGE_MANIFEST_DRIFT",
                "package manifest framing drifted",
            )
        expected: dict[str, tuple[str, int]] = {}
        for raw in manifest["package_members"]:
            record = _exact_keys(
                raw,
                {"path", "sha256", "size_bytes"},
                "package member",
            )
            relative = str(record["path"])
            path = PurePosixPath(relative)
            if (
                path.is_absolute()
                or len(path.parts) != 2
                or path.parts[0] != "payload"
                or relative in expected
                or type(record["sha256"]) is not str
                or SHA256_RE.fullmatch(record["sha256"]) is None
                or type(record["size_bytes"]) is not int
                or record["size_bytes"] < 0
            ):
                raise _BootstrapMechanicalError(
                    "PACKAGE_MANIFEST_DRIFT",
                    "package member identity is invalid",
                )
            expected[relative] = (
                record["sha256"],
                record["size_bytes"],
            )
        actual_names = {
            "package-manifest.json",
            "SHA256SUMS",
            *(
                f"payload/{entry.name}"
                for entry in os.scandir(root / "payload")
                if entry.is_file(follow_symlinks=False)
            ),
        }
        root_names = {entry.name for entry in os.scandir(root)}
        if (
            root_names != {"payload", "package-manifest.json", "SHA256SUMS"}
            or actual_names
            != {"package-manifest.json", "SHA256SUMS", *expected}
        ):
            raise _BootstrapMechanicalError(
                "PACKAGE_CLOSURE_DRIFT",
                "package member set drifted",
            )
        member_snapshots = {
            relative: self.snapshot_regular(root / relative)
            for relative in expected
        }
        if any(
            (
                member_snapshots[path].sha256,
                member_snapshots[path].size,
            )
            != identity
            for path, identity in expected.items()
        ):
            raise _BootstrapMechanicalError(
                "PACKAGE_MANIFEST_DRIFT",
                "package member bytes drifted",
            )
        seal_expected = {
            **{
                path: member_snapshots[path].sha256
                for path in member_snapshots
            },
            "package-manifest.json": manifest_snapshot.sha256,
        }
        try:
            seal_lines = seal_snapshot.data.decode("ascii").splitlines()
        except UnicodeDecodeError as exc:
            raise _BootstrapMechanicalError(
                "PACKAGE_SEAL_DRIFT",
                "package seal is not ASCII",
            ) from exc
        parsed: dict[str, str] = {}
        for line in seal_lines:
            if (
                len(line) < 67
                or line[64:66] != "  "
                or SHA256_RE.fullmatch(line[:64]) is None
                or line[66:] in parsed
            ):
                raise _BootstrapMechanicalError(
                    "PACKAGE_SEAL_DRIFT",
                    "package seal line is invalid",
                )
            parsed[line[66:]] = line[:64]
        if (
            not seal_snapshot.data.endswith(b"\n")
            or parsed != seal_expected
        ):
            raise _BootstrapMechanicalError(
                "PACKAGE_SEAL_DRIFT",
                "package seal member set or digest drifted",
            )
        if replay_external:
            sources = manifest["external_sources"]
            if len(sources) != len(expected):
                raise _BootstrapMechanicalError(
                    "PACKAGE_SOURCE_DRIFT",
                    "package external-source set drifted",
                )
            for raw in sources:
                source = _exact_keys(
                    raw,
                    {
                        "package_path",
                        "parse_json",
                        "role",
                        "source_identity",
                    },
                    "package external source",
                )
                identity = source["source_identity"]
                if not isinstance(identity, Mapping):
                    raise _BootstrapMechanicalError(
                        "PACKAGE_SOURCE_DRIFT",
                        "package source identity is malformed",
                    )
                current = self.snapshot_regular(str(identity["path"]))
                if (
                    self.full_identity(current) != identity
                    or current.data
                    != member_snapshots[str(source["package_path"])].data
                ):
                    raise _BootstrapMechanicalError(
                        "PACKAGE_SOURCE_DRIFT",
                        "package external source changed",
                    )
        return {
            "manifest_identity": self.detached_identity(
                manifest_snapshot
            ),
            "package_id": seal_snapshot.sha256,
            "seal_identity": self.detached_identity(seal_snapshot),
            "status": "PASS",
        }


_BOOTSTRAP_MECHANICAL_AUTHORITY = _BootstrapMechanicalAuthority()


_BUDGET_ARTIFACT_CLASSES = frozenset(
    {
        "closeout",
        "ledger",
        "metadata",
        "model",
        "normal",
        "publication",
        "scratch",
    }
)
_BUDGET_FALSE_AUTHORITY = {
    "changes_certified_exact": False,
    "changes_cut_state": False,
    "changes_lower_bound": False,
    "changes_production": False,
    "changes_upper_bound": False,
    "research_only": True,
}
_AB16_BUDGET_SLOTS = frozenset(
    f"{configuration}-{order}-{arm}"
    for configuration in (
        "region-capacity",
        "shape-packing-hall",
        "power-hitting-set",
        "bundle",
    )
    for order in ("ab", "ba")
    for arm in ("control", "treatment")
)
_AB16_ARM_ARTIFACT_CLASS_BY_LABEL = {
    "AB16 immediate stop": "closeout",
    "AB16 arm budget terminal": "closeout",
    "AB16 organic attempt artifact manifest": "publication",
    "AB16 organic attempt root replay": "closeout",
    "arm allocation unselected terminal": "closeout",
    "arm consumed incomplete": "closeout",
    "arm credibility gate": "publication",
    "arm launch environment": "metadata",
    "attach model evidence": "model",
    "attach solution-vector evidence": "publication",
    "compile attach journal segment": "ledger",
    "cut ledger segment": "ledger",
    "cut-free incumbent replay receipt": "publication",
    "independent arithmetic replay receipt": "publication",
    "independent resource terminal replay": "publication",
    "module-origin receipt": "metadata",
    "organic arm consumption": "closeout",
    "organic arm failure record": "closeout",
    "organic arm result": "publication",
    "organic arm selection": "metadata",
    "organic pre-run authority": "metadata",
    "organic pre-run candidate": "metadata",
    "preselection manager epoch": "metadata",
    "preselection manager transcript": "metadata",
    "raw incumbent export": "publication",
    "raw solution-vector export": "publication",
    "runtime cut segment": "ledger",
    "terminal classification": "publication",
}
_AB16_ARM_AGGREGATE_ALLOCATION = {
    "closeout": 64 * 1024 * 1024,
    "ledger": 128 * 1024 * 1024,
    "metadata": 32 * 1024 * 1024,
    "model": 480 * 1024 * 1024,
    "publication": 224 * 1024 * 1024,
}
_AB16_ARM_FIXED_PUBLICATION_BRANCH_MAXIMUM = 109
_AB16_BUDGET_JOURNAL_DERIVED_MINIMUM_ACTIONS = 12_480
_AB16_ARM_APPEND_CHANNELS = (
    (
        "compile-journal",
        "compile attach journal segment",
        "ledger/compile-attach-journal",
        221,
        (
            "3 genesis/seal records + 3 records per attach hook + "
            "at most one compiled-cut record per generated cut"
        ),
    ),
    (
        "cut-ledger",
        "cut ledger segment",
        "ledger/cut-ledger",
        258,
        (
            "2 genesis/seal records + at most one generated and one "
            "terminal disposition record per generated cut"
        ),
    ),
    (
        "runtime-cuts",
        "runtime cut segment",
        "checkpoint/runtime-cuts",
        0,
        (
            "certified_exact AB16 routes cut events through the cut ledger; "
            "runtime-cut publication is forbidden"
        ),
    ),
)
_AB16_MAXIMUM_ATTACH_HOOKS = 30
_AB16_MAXIMUM_GENERATED_CUTS = 128
_FORMAL_FIXED_RESERVATION_CONTRACT = {
    "formal-budget-terminal": {
        "artifact_class": "closeout",
        "maximum_bytes": 64 * 1024,
        "parent_path": "formal-closure",
        "parent_scope": "formal-root",
        "target_name": "budget-terminal.json",
    },
    "formal-closure-consumption": {
        "artifact_class": "metadata",
        "maximum_bytes": 4096,
        "parent_path": "locks",
        "parent_scope": "formal-root",
        "target_name": "formal-closure-consumption.json",
    },
    "formal-manifest": {
        "artifact_class": "metadata",
        "maximum_bytes": 64 * 1024,
        "parent_path": "formal-closure",
        "parent_scope": "formal-root",
        "target_name": "formal-manifest.json",
    },
    "recovery-closeout": {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * 1024 * 1024,
        "parent_path": "closeout",
        "parent_scope": "formal-root",
        "target_name": "formal-consumed-incomplete.json",
    },
    "recovery-disarm-terminal": {
        "artifact_class": "closeout",
        "maximum_bytes": 4 * 1024 * 1024,
        "parent_path": "formal-closure",
        "parent_scope": "formal-root",
        "target_name": "recovery-disarm-terminal.json",
    },
    "recovery-takeover-consumption": {
        "artifact_class": "metadata",
        "maximum_bytes": 4096,
        "parent_path": "locks",
        "parent_scope": "formal-root",
        "target_name": "recovery-takeover-consumption.json",
    },
    "failure-terminal-release": {
        "artifact_class": "closeout",
        "maximum_bytes": OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
        "parent_scope": "campaign-root",
        "target_name": "failure-terminal-release.json",
    },
    "formal-root-replay-alternate-receipt": {
        "artifact_class": "closeout",
        "maximum_bytes": OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
        "parent_scope": "campaign-root",
        "target_name": "formal-root-replay-alternate.json",
    },
    "formal-root-replay-primary-receipt": {
        "artifact_class": "closeout",
        "maximum_bytes": OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
        "parent_scope": "campaign-root",
        "target_name": "formal-root-replay-primary.json",
    },
    "success-dual-lock-release": {
        "artifact_class": "closeout",
        "maximum_bytes": OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
        "parent_path": OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
        "parent_scope": "campaign-root",
        "target_name": "dual-lock-release.json",
    },
}


def _budget_canonical_json(value: object) -> bytes:
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


def _budget_digest_without(record: Mapping[str, object], field: str) -> str:
    projected = dict(record)
    projected.pop(field, None)
    return hashlib.sha256(_budget_canonical_json(projected)).hexdigest()


def _budget_relative_path(value: object, label: str, *, allow_dot: bool = False) -> str:
    if type(value) is not str or not value or "\\" in value:
        raise BootstrapError(f"{label} is not one portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        if not (allow_dot and value == "."):
            raise BootstrapError(f"{label} is not one portable relative path")
    return value


def _budget_positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BootstrapError(f"{label} must be one positive integer")
    return value


def _budget_limits(value: object, label: str) -> dict[str, int]:
    if type(value) is not dict or not value:
        raise BootstrapError(f"{label} must be one nonempty category map")
    result: dict[str, int] = {}
    for artifact_class, maximum in value.items():
        if type(artifact_class) is not str or artifact_class not in _BUDGET_ARTIFACT_CLASSES:
            raise BootstrapError(f"{label} contains an unknown artifact class")
        result[artifact_class] = _budget_positive_int(
            maximum,
            f"{label}.{artifact_class}",
        )
    return result


def _budget_fixed_directories(value: object, label: str) -> dict[str, int]:
    if type(value) is not list or not value:
        raise BootstrapError(f"{label} must be one nonempty directory list")
    result: dict[str, int] = {}
    canonical: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        item = _exact_keys(
            raw,
            {"mode_octal", "path"},
            f"{label}[{index}]",
        )
        relative = _budget_relative_path(
            item["path"],
            f"{label}[{index}].path",
            allow_dot=True,
        )
        if item["mode_octal"] not in {"0500", "0700"} or relative in result:
            raise BootstrapError(f"{label} contains a duplicate or invalid directory")
        result[relative] = int(str(item["mode_octal"]), 8)
        canonical.append({"mode_octal": item["mode_octal"], "path": relative})
    if canonical != sorted(canonical, key=lambda item: str(item["path"]).encode("utf-8")):
        raise BootstrapError(f"{label} is not canonically ordered")
    if result.get(".") != 0o700:
        raise BootstrapError(f"{label} does not bind its root as mode 0700")
    return result


def _budget_artifact_maxima(
    value: object,
    label: str,
    *,
    directories: Mapping[str, int],
) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    if type(value) is not list or not value:
        raise BootstrapError(f"{label} must be one nonempty artifact list")
    records: dict[str, dict[str, object]] = {}
    paths: set[str] = set()
    per_class_totals: dict[str, int] = {}
    canonical: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        item = _exact_keys(
            raw,
            {
                "artifact_class",
                "label",
                "maximum_bytes",
                "path",
                "required_on_success",
            },
            f"{label}[{index}]",
        )
        artifact_label = _budget_relative_path(
            item["label"],
            f"{label}[{index}].label",
        )
        path = _budget_relative_path(item["path"], f"{label}[{index}].path")
        artifact_class = item["artifact_class"]
        maximum = _budget_positive_int(
            item["maximum_bytes"],
            f"{label}[{index}].maximum_bytes",
        )
        parent = PurePosixPath(path).parent.as_posix()
        if (
            type(artifact_class) is not str
            or artifact_class not in _BUDGET_ARTIFACT_CLASSES
            or type(item["required_on_success"]) is not bool
            or artifact_label in records
            or path in paths
            or parent not in directories
        ):
            raise BootstrapError(f"{label} contains an invalid or duplicate artifact")
        record = {
            "artifact_class": artifact_class,
            "label": artifact_label,
            "maximum_bytes": maximum,
            "path": path,
            "required_on_success": item["required_on_success"],
        }
        records[artifact_label] = record
        paths.add(path)
        per_class_totals[artifact_class] = (
            per_class_totals.get(artifact_class, 0) + maximum
        )
        canonical.append(record)
    if canonical != sorted(canonical, key=lambda item: str(item["label"]).encode("utf-8")):
        raise BootstrapError(f"{label} is not canonically ordered")
    return records, per_class_totals


def _budget_append_channels(
    value: object,
    label: str,
    *,
    directories: Mapping[str, int],
) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    if type(value) is not list or not value:
        raise BootstrapError(f"{label} must be one nonempty append-channel list")
    records: dict[str, dict[str, object]] = {}
    per_class_totals: dict[str, int] = {}
    canonical: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        item = _exact_keys(
            raw,
            {
                "artifact_class",
                "channel",
                "label",
                "maximum_bytes",
                "maximum_segments",
                "multiplicity_derivation",
                "parent_path",
            },
            f"{label}[{index}]",
        )
        channel = _budget_relative_path(
            item["channel"],
            f"{label}[{index}].channel",
        )
        channel_label = _budget_relative_path(
            item["label"],
            f"{label}[{index}].label",
        )
        parent = _budget_relative_path(
            item["parent_path"],
            f"{label}[{index}].parent_path",
        )
        artifact_class = item["artifact_class"]
        maximum = _budget_positive_int(
            item["maximum_bytes"],
            f"{label}[{index}].maximum_bytes",
        )
        maximum_segments = item["maximum_segments"]
        derivation = item["multiplicity_derivation"]
        if (
            type(artifact_class) is not str
            or artifact_class not in _BUDGET_ARTIFACT_CLASSES
            or isinstance(maximum_segments, bool)
            or not isinstance(maximum_segments, int)
            or maximum_segments < 0
            or type(derivation) is not dict
            or derivation.get("result_maximum_segments")
            != maximum_segments
            or channel in records
            or parent not in directories
        ):
            raise BootstrapError(
                f"{label} contains an invalid or duplicate channel"
            )
        record = {
            "artifact_class": artifact_class,
            "channel": channel,
            "label": channel_label,
            "maximum_bytes": maximum,
            "maximum_segments": maximum_segments,
            "multiplicity_derivation": dict(derivation),
            "parent_path": parent,
        }
        records[channel] = record
        per_class_totals[artifact_class] = (
            per_class_totals.get(artifact_class, 0)
            + maximum * maximum_segments
        )
        canonical.append(record)
    if canonical != sorted(
        canonical,
        key=lambda item: str(item["channel"]).encode("utf-8"),
    ):
        raise BootstrapError(f"{label} is not canonically ordered")
    return records, per_class_totals


def _budget_reserve(
    value: object,
    label: str,
    *,
    directories: Mapping[str, int],
    require_parent_scope: bool = False,
) -> dict[str, object]:
    expected_keys = {
        "artifact_class",
        "maximum_bytes",
        "parent_path",
        "purpose",
        "target_name",
    }
    if require_parent_scope:
        expected_keys.add("parent_scope")
    item = _exact_keys(
        value,
        expected_keys,
        label,
    )
    artifact_class = item["artifact_class"]
    parent = _budget_relative_path(
        item["parent_path"],
        f"{label}.parent_path",
        allow_dot=True,
    )
    parent_scope = item.get("parent_scope")
    purpose = _budget_relative_path(item["purpose"], f"{label}.purpose")
    target = _budget_relative_path(item["target_name"], f"{label}.target_name")
    if (
        type(artifact_class) is not str
        or artifact_class not in _BUDGET_ARTIFACT_CLASSES
        or (
            require_parent_scope
            and parent_scope not in {"campaign-root", "formal-root"}
        )
        or (
            parent_scope == "formal-root"
            and parent not in directories
        )
        or (
            parent_scope == "campaign-root"
            and parent != OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
        )
        or (not require_parent_scope and parent not in directories)
        or len(PurePosixPath(purpose).parts) != 1
        or len(PurePosixPath(target).parts) != 1
    ):
        raise BootstrapError(f"{label} is invalid")
    result: dict[str, object] = {
        "artifact_class": artifact_class,
        "maximum_bytes": _budget_positive_int(
            item["maximum_bytes"],
            f"{label}.maximum_bytes",
        ),
        "parent_path": parent,
        "purpose": purpose,
        "target_name": target,
    }
    if require_parent_scope:
        result["parent_scope"] = parent_scope
    return result


def _budget_reservations(
    value: object,
    label: str,
    *,
    directories: Mapping[str, int],
    required_contract: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    if type(value) is not list or not value:
        raise BootstrapError(f"{label} must be one nonempty reservation list")
    result: dict[str, dict[str, object]] = {}
    targets: set[tuple[str, str, str]] = set()
    canonical: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        reserve = _budget_reserve(
            raw,
            f"{label}[{index}]",
            directories=directories,
            require_parent_scope=True,
        )
        purpose = str(reserve["purpose"])
        target = (
            str(reserve["parent_scope"]),
            str(reserve["parent_path"]),
            str(reserve["target_name"]),
        )
        if purpose in result or target in targets:
            raise BootstrapError(
                f"{label} contains a duplicate purpose or target"
            )
        result[purpose] = reserve
        targets.add(target)
        canonical.append(reserve)
    if canonical != sorted(
        canonical,
        key=lambda item: str(item["purpose"]).encode("utf-8"),
    ):
        raise BootstrapError(f"{label} is not canonically ordered")
    if set(result) != set(required_contract):
        raise BootstrapError(
            f"{label} fixed purpose set drifted"
        )
    for purpose, expected in required_contract.items():
        reserve = result[purpose]
        if any(reserve.get(field) != value for field, value in expected.items()):
            raise BootstrapError(
                f"{label} contract drifted for {purpose}"
            )
    return result


def _sum_budget_limits(*values: Mapping[str, int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        for artifact_class, amount in value.items():
            result[artifact_class] = result.get(artifact_class, 0) + amount
    return result


def _budget_arm_cap_contract(
    *,
    label: str,
    slot: str,
) -> tuple[str, int, dict[str, object], dict[str, object]]:
    attempt = f"prospective/arms/{slot}"
    fixed_paths = {
        "AB16 immediate stop": "prospective/immediate-stop-a001.json",
        "AB16 arm budget terminal": f"budget/arm-terminals/{slot}.json",
        "AB16 organic attempt artifact manifest": (
            f"{attempt}/attempt-artifact-manifest.json"
        ),
        "AB16 organic attempt root replay": (
            f"replays/arm-attempt-roots/{slot}.json"
        ),
        "arm allocation unselected terminal": (
            f"{attempt}/arm-unselected-terminal.json"
        ),
        "arm consumed incomplete": (
            f"{attempt}/arm-consumed-incomplete.json"
        ),
        "arm credibility gate": (
            f"{attempt}/replays/arm-credibility.json"
        ),
        "arm launch environment": (
            "prospective/pre-run-candidates/"
            f"{slot}-launch-environment.json"
        ),
        "cut-free incumbent replay receipt": (
            f"{attempt}/replays/cut-free-incumbent.json"
        ),
        "independent arithmetic replay receipt": (
            f"{attempt}/replays/independent-arithmetic.json"
        ),
        "independent resource terminal replay": (
            f"{attempt}/replays/independent-resource-terminal.json"
        ),
        "module-origin receipt": f"{attempt}/module-origin-receipt.json",
        "organic arm consumption": f"prospective/consumptions/{slot}.json",
        "organic arm failure record": f"{attempt}/failure.json",
        "organic arm result": f"{attempt}/result.json",
        "organic arm selection": f"{attempt}/selection.json",
        "organic pre-run authority": (
            f"{attempt}/pre-run-authority.json"
        ),
        "organic pre-run candidate": (
            f"prospective/pre-run-candidates/{slot}.json"
        ),
        "preselection manager epoch": (
            "prospective/pre-run-candidates/"
            f"{slot}-preselection-epoch.json"
        ),
        "preselection manager transcript": (
            "prospective/pre-run-candidates/"
            f"{slot}-preselection-transcript.json"
        ),
        "raw incumbent export": f"{attempt}/raw-incumbent.json",
        "raw solution-vector export": (
            f"{attempt}/raw-solution-vector.json"
        ),
        "terminal classification": (
            "prospective/terminal-classification-a001.json"
        ),
    }
    if label == "attach model evidence":
        return (
            "common",
            60,
            {
                "kind": "attach-hook",
                "maximum_attach_hooks": _AB16_MAXIMUM_ATTACH_HOOKS,
                "publications_per_hook": 2,
            },
            {
                "allowed_phases": ["post", "pre"],
                "index_maximum": _AB16_MAXIMUM_ATTACH_HOOKS - 1,
                "index_minimum": 0,
                "index_name": "hook_id",
                "kind": "indexed-phase-template",
                "root": "formal-root",
                "root_relative_path_template": (
                    f"{attempt}/runtime/hook-{{hook_id:04d}}-"
                    "{phase}-model.pb"
                ),
            },
        )
    if label == "attach solution-vector evidence":
        return (
            "common",
            30,
            {
                "kind": "attach-hook",
                "maximum_attach_hooks": _AB16_MAXIMUM_ATTACH_HOOKS,
                "publications_per_hook": 1,
            },
            {
                "index_maximum": _AB16_MAXIMUM_ATTACH_HOOKS - 1,
                "index_minimum": 0,
                "index_name": "hook_id",
                "kind": "indexed-template",
                "root": "formal-root",
                "root_relative_path_template": (
                    f"{attempt}/runtime/hook-{{hook_id:04d}}-"
                    "solution-vector.json"
                ),
            },
        )
    channel_suffixes = {
        "compile attach journal segment": "compile-journal",
        "cut ledger segment": "cut-ledger",
        "runtime cut segment": "runtime-cuts",
    }
    if label in channel_suffixes:
        return (
            "common",
            0,
            {
                "kind": "append-channel-only",
                "maximum_fixed_publications": 0,
            },
            {
                "channel": f"arm-{slot}-{channel_suffixes[label]}",
                "kind": "append-channel",
                "root": "formal-root",
            },
        )
    if label in {
        "arm launch environment",
        "module-origin receipt",
        "organic arm selection",
        "organic pre-run authority",
        "organic pre-run candidate",
        "preselection manager epoch",
        "preselection manager transcript",
    }:
        return (
            "common",
            1,
            {
                "kind": "single-fixed-path",
                "maximum_fixed_publications": 1,
            },
            {
                "kind": "fixed",
                "root": "formal-root",
                "root_relative_path": fixed_paths[label],
            },
        )
    branch = (
        "failure"
        if label
        in {
            "AB16 immediate stop",
            "arm allocation unselected terminal",
            "arm consumed incomplete",
            "organic arm failure record",
        }
        else "success"
    )
    if label not in fixed_paths:
        raise BootstrapError(
            f"AB16 arm artifact cap label is unsupported: {label}"
        )
    return (
        branch,
        1,
        {
            "kind": "terminal-branch-fixed-path",
            "maximum_fixed_publications": 1,
            "terminal_branch": branch,
        },
        {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": fixed_paths[label],
        },
    )


def _budget_arm_expected_maximum(
    *,
    label: str,
    artifact_class: str,
) -> int:
    """Recompute the package cohort's per-publication cap independently."""

    if artifact_class == "model":
        return 8 * 1024 * 1024
    if artifact_class == "ledger":
        return 256 * 1024
    if artifact_class == "metadata":
        return 4 * 1024 * 1024
    if artifact_class == "closeout":
        return 8 * 1024 * 1024
    if artifact_class != "publication":
        raise BootstrapError(
            f"AB16 arm artifact class is unsupported: {label}"
        )
    if label in {
        "arm credibility gate",
        "attach solution-vector evidence",
        "independent arithmetic replay receipt",
        "independent resource terminal replay",
        "raw incumbent export",
        "raw solution-vector export",
        "terminal classification",
    }:
        return 4 * 1024 * 1024
    return 16 * 1024 * 1024


def _budget_arm_artifact_caps(
    value: object,
    *,
    allocations: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, dict[str, object]]]:
    slots = _exact_keys(
        value,
        set(_AB16_BUDGET_SLOTS),
        "AB16 arm artifact caps",
    )
    checked: dict[str, dict[str, dict[str, object]]] = {}
    expected_labels = set(_AB16_ARM_ARTIFACT_CLASS_BY_LABEL)
    for slot in sorted(_AB16_BUDGET_SLOTS):
        raw_caps = _exact_keys(
            slots[slot],
            expected_labels,
            f"AB16 arm artifact caps {slot}",
        )
        slot_limits = allocations[slot]
        slot_caps: dict[str, dict[str, object]] = {}
        for label in sorted(expected_labels, key=lambda item: item.encode("utf-8")):
            item = _exact_keys(
                raw_caps[label],
                {
                    "artifact_class",
                    "branch",
                    "maximum_bytes",
                    "maximum_publications",
                    "multiplicity_source",
                    "path_contract",
                },
                f"AB16 arm artifact cap {slot}.{label}",
            )
            expected_class = _AB16_ARM_ARTIFACT_CLASS_BY_LABEL[label]
            maximum = _budget_positive_int(
                item["maximum_bytes"],
                f"AB16 arm artifact cap {slot}.{label}.maximum_bytes",
            )
            branch, count, multiplicity, path_contract = (
                _budget_arm_cap_contract(label=label, slot=slot)
            )
            if (
                item["artifact_class"] != expected_class
                or item["branch"] != branch
                or maximum
                != _budget_arm_expected_maximum(
                    label=label,
                    artifact_class=expected_class,
                )
                or item["maximum_publications"] != count
                or item["multiplicity_source"] != multiplicity
                or item["path_contract"] != path_contract
                or expected_class not in slot_limits
                or maximum > slot_limits[expected_class]
            ):
                raise BootstrapError(
                    f"AB16 arm artifact cap differs from its allocation: {slot}.{label}"
                )
            slot_caps[label] = {
                "artifact_class": expected_class,
                "branch": branch,
                "maximum_bytes": maximum,
                "maximum_publications": count,
                "multiplicity_source": multiplicity,
                "path_contract": path_contract,
            }
        checked[slot] = slot_caps
    return checked


def _budget_arm_append_channels(
    value: object,
    *,
    artifact_caps: Mapping[str, Mapping[str, Mapping[str, object]]],
    directories: Mapping[str, int],
) -> dict[str, list[dict[str, object]]]:
    slots = _exact_keys(
        value,
        set(_AB16_BUDGET_SLOTS),
        "AB16 arm append channels",
    )
    checked: dict[str, list[dict[str, object]]] = {}
    for slot in sorted(_AB16_BUDGET_SLOTS):
        records = slots[slot]
        if type(records) is not list or len(records) != len(_AB16_ARM_APPEND_CHANNELS):
            raise BootstrapError(
                f"AB16 arm append-channel set differs for {slot}"
            )
        expected = sorted(
            (
                {
                    "artifact_class": "ledger",
                    "channel": f"arm-{slot}-{suffix}",
                    "label": label,
                    "maximum_bytes": artifact_caps[slot][label]["maximum_bytes"],
                    "maximum_segments": maximum_segments,
                    "multiplicity_derivation": {
                        "formula": derivation,
                        "maximum_attach_hooks": (
                            _AB16_MAXIMUM_ATTACH_HOOKS
                        ),
                        "maximum_generated_cuts": (
                            _AB16_MAXIMUM_GENERATED_CUTS
                        ),
                        "result_maximum_segments": maximum_segments,
                    },
                    "parent_path": f"prospective/arms/{slot}/{relative_parent}",
                }
                for (
                    suffix,
                    label,
                    relative_parent,
                    maximum_segments,
                    derivation,
                ) in _AB16_ARM_APPEND_CHANNELS
            ),
            key=lambda item: str(item["channel"]).encode("utf-8"),
        )
        if records != expected:
            raise BootstrapError(
                f"AB16 arm append-channel contract drifted for {slot}"
            )
        for item in expected:
            if item["parent_path"] not in directories:
                raise BootstrapError(
                    f"AB16 arm append-channel parent is absent for {slot}"
                )
        checked[slot] = expected
    return checked


def _budget_validate_arm_workload_contract(
    value: object,
    *,
    allocations: Mapping[str, Mapping[str, int]],
    caps: Mapping[str, Mapping[str, Mapping[str, object]]],
    channels: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    record = _exact_keys(
        value,
        {
            "allocation_formula",
            "allocation_margin_bytes",
            "branch_contract",
            "hard_limits",
            "historical_size_planning_input",
            "independent_failure_closeout_reserve",
            "model_export_contract",
            "per_file_cap_derivation",
            "required_category_bytes",
            "scratch_contract",
        },
        "AB16 arm workload contract",
    )
    if (
        record["allocation_formula"]
        != (
            "common[including the independent failure-closeout reserve] + "
            "per-class "
            "max(success branch, failure branch) + "
            "append[segment cap * maximum segments] + explicit margin"
        )
        or record["branch_contract"]
        != {
            "common": {"mutually_exclusive_with": []},
            "failure": {"mutually_exclusive_with": ["success"]},
            "success": {"mutually_exclusive_with": ["failure"]},
        }
        or record["hard_limits"]
        != {
            "maximum_attach_hooks": {
                "basis": "formal runtime maximum Benders iterations",
                "exhaustion": "arm-consumed-incomplete",
                "value": _AB16_MAXIMUM_ATTACH_HOOKS,
            },
            "maximum_generated_cuts": {
                "basis": (
                    "policy-defined bounded workload cap; next power of two "
                    "above four generated cuts per maximum attach hook"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before the first generated-cut write beyond the cap; "
                    "arm-consumed-incomplete"
                ),
                "sufficiency_claim": False,
                "value": _AB16_MAXIMUM_GENERATED_CUTS,
            },
        }
        or record["independent_failure_closeout_reserve"]
        != {
            "artifact_class": "closeout",
            "label": "organic arm failure record",
            "maximum_bytes": 8 * 1024 * 1024,
            "physical_accounting_branch": "common",
            "publication_branch": "failure",
            "release_policy": (
                "non-refundable; remains available after any partial or "
                "complete success-branch staging"
            ),
        }
        or record["scratch_contract"]
        != {
            "aggregate_allocation_bytes": 0,
            "known_retained_writer_count": 0,
            "tmp_directory_mode_octal": "0500",
            "write_attempt_result": "fail-closed",
        }
    ):
        raise BootstrapError(
            "AB16 arm workload hard-limit/branch contract drifted"
        )
    expected_required: dict[str, int] | None = None
    for slot in sorted(_AB16_BUDGET_SLOTS):
        by_branch: dict[str, dict[str, int]] = {
            "common": {},
            "failure": {},
            "success": {},
        }
        for cap_label, cap in caps[slot].items():
            artifact_class = str(cap["artifact_class"])
            branch = str(cap["branch"])
            allocation_branch = (
                "common"
                if cap_label == "organic arm failure record"
                else branch
            )
            amount = int(cap["maximum_bytes"]) * int(
                cap["maximum_publications"]
            )
            by_branch[allocation_branch][artifact_class] = (
                by_branch[allocation_branch].get(artifact_class, 0)
                + amount
            )
        append_totals: dict[str, int] = {}
        for channel in channels[slot]:
            artifact_class = str(channel["artifact_class"])
            append_totals[artifact_class] = (
                append_totals.get(artifact_class, 0)
                + int(channel["maximum_bytes"])
                * int(channel["maximum_segments"])
            )
        classes = (
            set(by_branch["common"])
            | set(by_branch["failure"])
            | set(by_branch["success"])
            | set(append_totals)
            | {"scratch"}
        )
        required = {
            artifact_class: (
                by_branch["common"].get(artifact_class, 0)
                + max(
                    by_branch["success"].get(artifact_class, 0),
                    by_branch["failure"].get(artifact_class, 0),
                )
                + append_totals.get(artifact_class, 0)
            )
            for artifact_class in sorted(classes)
        }
        if expected_required is None:
            expected_required = required
        elif required != expected_required:
            raise BootstrapError(
                "AB16 arm workload differs between slots"
            )
        margins = {
            artifact_class: (
                allocations[slot].get(artifact_class, 0) - amount
            )
            for artifact_class, amount in required.items()
        }
        if any(amount < 0 for amount in margins.values()):
            raise BootstrapError(
                f"AB16 arm workload underallocates slot {slot}"
            )
        if (
            record["required_category_bytes"] != required
            or record["allocation_margin_bytes"] != margins
        ):
            raise BootstrapError(
                "AB16 arm workload aggregate arithmetic drifted"
            )
    historical = record["historical_size_planning_input"]
    model_export = record["model_export_contract"]
    cap_derivation = record["per_file_cap_derivation"]
    if (
        type(historical) is not dict
        or set(historical)
        != {
            "authority",
            "observations",
            "runtime_dependency",
            "sample_id",
        }
        or historical["authority"]
        != "planning-input-only-not-calibration-authority"
        or historical["runtime_dependency"] is not False
        or type(historical["observations"]) is not list
        or not historical["observations"]
        or type(model_export) is not dict
        or set(model_export)
        != {
            "cap_source",
            "export_open_mode",
            "rlimit_fsize",
            "sealed_memfd_required",
        }
        or model_export["export_open_mode"] != "O_TRUNC"
        or model_export["sealed_memfd_required"] is not True
        or type(cap_derivation) is not dict
        or set(cap_derivation)
        != {
            "ledger_segment",
            "model",
            "temporary_canonical_record",
            "vector_or_incumbent",
        }
        or cap_derivation["ledger_segment"]
        != {
            "basis": (
                "policy-defined retained-segment cap pending comparable "
                "calibration"
            ),
            "evidence_status": "unmeasured-temporary",
            "exhaustion": (
                "fail before an oversized append publication; "
                "arm-consumed-incomplete"
            ),
            "result_maximum_bytes": 256 * 1024,
            "sufficiency_claim": False,
        }
    ):
        raise BootstrapError(
            "AB16 arm workload provenance/model contract drifted"
        )


def validate_resource_budget_profile(value: object) -> Mapping[str, Any]:
    """Validate the future profile without granting launch authority."""

    record = _exact_keys(
        value,
        {
            "authority",
            "bootstrap",
            "execution_surface_sha256",
            "formal_root",
            "launch_ready",
            "profile_id",
            "profile_sha256",
            "schema_version",
        },
        "AB16 resource-budget profile",
    )
    authority_record = _exact_keys(
        record["authority"],
        set(_BUDGET_FALSE_AUTHORITY),
        "AB16 resource-budget profile authority",
    )
    if dict(authority_record) != _BUDGET_FALSE_AUTHORITY:
        raise BootstrapError("AB16 resource-budget profile expands authority")
    bootstrap = _exact_keys(
        record["bootstrap"],
        {
            "artifact_maxima",
            "category_limits",
            "failure_closeout_reserve",
            "fixed_directories",
            "root_relative_path",
        },
        "AB16 bootstrap budget profile",
    )
    bootstrap_directories = _budget_fixed_directories(
        bootstrap["fixed_directories"],
        "AB16 bootstrap fixed directories",
    )
    bootstrap_artifacts, bootstrap_artifact_maxima = _budget_artifact_maxima(
        bootstrap["artifact_maxima"],
        "AB16 bootstrap artifact maxima",
        directories=bootstrap_directories,
    )
    bootstrap_reserve = _budget_reserve(
        bootstrap["failure_closeout_reserve"],
        "AB16 bootstrap failure closeout reserve",
        directories=bootstrap_directories,
    )
    bootstrap_limits = _budget_limits(
        bootstrap["category_limits"],
        "AB16 bootstrap category limits",
    )
    bootstrap_reserve_limits = {
        str(bootstrap_reserve["artifact_class"]): int(
            bootstrap_reserve["maximum_bytes"]
        )
    }
    bootstrap_payload_limits = dict(bootstrap_limits)
    for artifact_class, reserved in bootstrap_reserve_limits.items():
        available = bootstrap_payload_limits.get(artifact_class, 0) - reserved
        if available < 0:
            raise BootstrapError(
                "AB16 bootstrap closeout reserve exceeds its aggregate category limit"
            )
        bootstrap_payload_limits[artifact_class] = available
    if bootstrap["root_relative_path"] != "." or any(
        maximum > bootstrap_payload_limits.get(artifact_class, 0)
        for artifact_class, maximum in bootstrap_artifact_maxima.items()
    ):
        raise BootstrapError("AB16 bootstrap budget arithmetic does not close")

    formal = _exact_keys(
        record["formal_root"],
        {
            "append_channels",
            "arm_append_channels",
            "arm_allocations",
            "arm_artifact_caps",
            "arm_workload_contract",
            "artifact_maxima",
            "category_limits",
            "fixed_directories",
            "fixed_overhead_category_limits",
            "fixed_purpose_reservations",
            "root_relative_path",
        },
        "AB16 formal-root budget profile",
    )
    formal_directories = _budget_fixed_directories(
        formal["fixed_directories"],
        "AB16 formal-root fixed directories",
    )
    _formal_artifacts, formal_artifact_maxima = _budget_artifact_maxima(
        formal["artifact_maxima"],
        "AB16 formal-root artifact maxima",
        directories=formal_directories,
    )
    formal_channels, formal_channel_maxima = _budget_append_channels(
        formal["append_channels"],
        "AB16 formal-root append channels",
        directories=formal_directories,
    )
    if (
        set(formal_channels)
        != {"ab16-baseline-rebuild-cuts", "budget-journal"}
        or formal_channels["ab16-baseline-rebuild-cuts"]
        != {
            "artifact_class": "ledger",
            "channel": "ab16-baseline-rebuild-cuts",
            "label": "AB16 baseline cut segment",
            "maximum_bytes": 1024 * 1024,
            "maximum_segments": 128,
            "multiplicity_derivation": {
                "basis": (
                    "temporary unmeasured conservative baseline append cap"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": "formal-consumed-incomplete",
                "result_maximum_segments": 128,
            },
            "parent_path": "prospective/baseline/checkpoint/benders-cuts",
        }
        or formal_channels["budget-journal"]
        != {
            "artifact_class": "metadata",
            "channel": "budget-journal",
            "label": "AB16 formal budget journal segment",
            "maximum_bytes": 4096,
            "maximum_segments": 16_384,
            "multiplicity_derivation": {
                "basis": (
                    "profile-derived data-plane maxima plus explicit "
                    "temporary control-plane allowances"
                ),
                "bootstrap_and_formal_control_allowance": 2048,
                    "derived_minimum_actions": (
                        _AB16_BUDGET_JOURNAL_DERIVED_MINIMUM_ACTIONS
                    ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before the next broker-journal append; "
                    "formal-consumed-incomplete"
                ),
                "formal_arm_count": 16,
                "maximum_segment_bytes": 4096,
                "per_arm_append_maximum": 479,
                "per_arm_control_allowance": 64,
                    "per_arm_fixed_publication_branch_maximum": (
                        _AB16_ARM_FIXED_PUBLICATION_BRANCH_MAXIMUM
                    ),
                "retained_allocation_bytes": 67_108_864,
                "result_maximum_segments": 16_384,
                "segment_cap_basis": (
                    "policy-defined canonical action-record cap pending "
                    "comparable calibration"
                ),
                "segment_count_rounding": (
                    "next power of two above derived minimum actions"
                ),
                "sufficiency_claim": False,
            },
            "parent_path": "channels/budget-journal",
        }
    ):
        raise BootstrapError("AB16 formal append-channel contract drifted")
    fixed_reservations = _budget_reservations(
        formal["fixed_purpose_reservations"],
        "AB16 formal fixed-purpose reservations",
        directories=formal_directories,
        required_contract=_FORMAL_FIXED_RESERVATION_CONTRACT,
    )
    fixed_limits = _budget_limits(
        formal["fixed_overhead_category_limits"],
        "AB16 formal fixed-overhead category limits",
    )
    formal_reserve_limits = _sum_budget_limits(
        *(
            {
                str(reserve["artifact_class"]): int(
                    reserve["maximum_bytes"]
                )
            }
            for reserve in fixed_reservations.values()
        ),
    )
    formal_payload_limits = dict(fixed_limits)
    for artifact_class, reserved in formal_reserve_limits.items():
        available = formal_payload_limits.get(artifact_class, 0) - reserved
        if available < 0:
            raise BootstrapError(
                "AB16 formal closeout reserves exceed their aggregate category limit"
            )
        formal_payload_limits[artifact_class] = available
    formal_payload_maxima = _sum_budget_limits(
        formal_artifact_maxima,
        formal_channel_maxima,
    )
    if any(
        maximum > formal_payload_limits.get(artifact_class, 0)
        for artifact_class, maximum in formal_payload_maxima.items()
    ):
        raise BootstrapError("AB16 formal fixed-overhead arithmetic does not close")
    arm_allocations = _exact_keys(
        formal["arm_allocations"],
        set(_AB16_BUDGET_SLOTS),
        "AB16 arm budget allocations",
    )
    checked_arms = {
        slot: _budget_limits(value, f"AB16 arm budget allocation {slot}")
        for slot, value in arm_allocations.items()
    }
    if any(
        allocation != _AB16_ARM_AGGREGATE_ALLOCATION
        for allocation in checked_arms.values()
    ):
        raise BootstrapError(
            "AB16 arm aggregate allocation cohort drifted"
        )
    arm_artifact_caps = _budget_arm_artifact_caps(
        formal["arm_artifact_caps"],
        allocations=checked_arms,
    )
    arm_append_channels = _budget_arm_append_channels(
        formal["arm_append_channels"],
        artifact_caps=arm_artifact_caps,
        directories=formal_directories,
    )
    _budget_validate_arm_workload_contract(
        formal["arm_workload_contract"],
        allocations=checked_arms,
        caps=arm_artifact_caps,
        channels=arm_append_channels,
    )
    formal_limits = _budget_limits(
        formal["category_limits"],
        "AB16 formal-root category limits",
    )
    expected_formal_limits = _sum_budget_limits(
        fixed_limits,
        *checked_arms.values(),
    )
    if (
        formal["root_relative_path"] != "formal-ab16/artifacts"
        or formal_limits != expected_formal_limits
    ):
        raise BootstrapError("AB16 formal-root budget arithmetic does not close")
    if (
        record["schema_version"] != RESOURCE_BUDGET_PROFILE_SCHEMA
        or type(record["launch_ready"]) is not bool
        or type(record["profile_id"]) is not str
        or not record["profile_id"]
        or type(record["execution_surface_sha256"]) is not str
        or SHA256_RE.fullmatch(record["execution_surface_sha256"]) is None
        or type(record["profile_sha256"]) is not str
        or record["profile_sha256"]
        != _budget_digest_without(record, "profile_sha256")
    ):
        raise BootstrapError("AB16 resource-budget profile identity drifted")
    # ``execution_surface_sha256`` binds only the stable workload/execution-core
    # bytes.  It deliberately excludes this profile, PROJECT_LOCK, code-assets,
    # docs, and calibration receipts; those control identities are joined
    # separately by the calibration declaration, avoiding cryptographic
    # self-reference.
    #
    # Retain the validated projections only as local parsing evidence.  The
    # canonical input object remains the byte-level authority.
    _ = bootstrap_artifacts
    return record


def _resource_budget_profile(
    path: Path | str,
    *,
    require_launch_ready: bool,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    absolute = _absolute(path)
    snapshot = authority.snapshot_regular(absolute, size_limit=64 << 20)
    if (
        snapshot.stat_result.st_nlink != 1
        or snapshot.stat_result.st_uid != os.getuid()
        or stat.S_IMODE(snapshot.stat_result.st_mode) != 0o444
    ):
        raise BootstrapError(
            "AB16 resource-budget profile identity or mode is invalid"
        )
    value = authority.strict_loads(snapshot.data, "AB16 resource-budget profile")
    if authority.canonical_json(value) != snapshot.data:
        raise BootstrapError("AB16 resource-budget profile is not canonical")
    profile = validate_resource_budget_profile(value)
    if require_launch_ready and profile["launch_ready"] is not True:
        raise BootstrapError(
            "AB16 resource-budget profile is not launch ready"
        )
    identity = {
        "mode": 0o444,
        **authority.detached_identity(snapshot),
    }
    return profile, identity


def _resource_calibration_bundle_sources(
    paths: Mapping[str, Path | str],
) -> tuple[dict[str, Path], dict[str, dict[str, object]]]:
    if (
        type(paths) is not dict
        or set(paths) != set(RESOURCE_CALIBRATION_STAGES)
    ):
        raise BootstrapError(
            "resource calibration bundle stage set drifted"
        )
    resolved: dict[str, Path] = {}
    identities: dict[str, dict[str, object]] = {}
    for stage in RESOURCE_CALIBRATION_STAGES:
        raw_path = paths[stage]
        if not isinstance(raw_path, (str, os.PathLike)):
            raise BootstrapError(
                f"resource calibration bundle path is malformed: {stage}"
            )
        path = _absolute(Path(os.fspath(raw_path)))
        snapshot = authority.snapshot_regular(path)
        if stat.S_IMODE(snapshot.stat_result.st_mode) != 0o444:
            raise BootstrapError(
                f"resource calibration bundle is not immutable: {stage}"
            )
        record = authority.strict_loads(
            snapshot.data,
            f"{stage} resource calibration bundle",
        )
        if authority.canonical_json(record) != snapshot.data:
            raise BootstrapError(
                f"resource calibration bundle is not canonical: {stage}"
            )
        resolved[stage] = path
        identities[stage] = authority.detached_identity(snapshot)
    if (
        len({identity["path"] for identity in identities.values()}) != 3
        or len({identity["sha256"] for identity in identities.values()})
        != 3
    ):
        raise BootstrapError(
            "resource calibration bundle identities are not stage-distinct"
        )
    return resolved, identities


def _validate_resource_calibration_bundle_identities(
    value: object,
    *,
    label: str,
) -> dict[str, dict[str, object]]:
    records = _exact_keys(
        value,
        set(RESOURCE_CALIBRATION_STAGES),
        label,
    )
    checked: dict[str, dict[str, object]] = {}
    for stage in RESOURCE_CALIBRATION_STAGES:
        identity = _exact_keys(
            records[stage],
            {"path", "sha256", "size_bytes"},
            f"{label} {stage}",
        )
        if (
            type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or isinstance(identity["size_bytes"], bool)
            or not isinstance(identity["size_bytes"], int)
            or identity["size_bytes"] <= 0
        ):
            raise BootstrapError(
                f"{label} {stage} identity is malformed"
            )
        checked[stage] = dict(identity)
    if (
        len({identity["path"] for identity in checked.values()}) != 3
        or len({identity["sha256"] for identity in checked.values()}) != 3
    ):
        raise BootstrapError(
            f"{label} identities are not stage-distinct"
        )
    return checked


def _calibration_tool_content_identities(
    planned: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Project Gate-B planned sources into the exact calibration tool cohort."""

    result: dict[str, dict[str, object]] = {}
    for role, planned_role in sorted(
        CALIBRATION_TOOL_PLANNED_ROLES.items()
    ):
        identity = planned.get(planned_role)
        if (
            type(identity) is not dict
            or type(identity.get("sha256")) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or isinstance(identity.get("size_bytes"), bool)
            or not isinstance(identity.get("size_bytes"), int)
            or identity["size_bytes"] <= 0
        ):
            raise BootstrapError(
                f"planned calibration tool identity is absent or malformed: {role}"
            )
        result[role] = {
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
        }
    return result


def _planned_budget_contracts(
    *,
    campaign_dir: Path,
    profile: Mapping[str, Any],
    profile_identity: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    formal_root = campaign_dir / "formal-ab16/artifacts"
    formal_path = formal_root / "formal-root-budget-contract.json"
    formal_record = {
        "authority": dict(_BUDGET_FALSE_AUTHORITY),
        "budget_profile_identity": dict(profile_identity),
        "budget_profile_sha256": profile["profile_sha256"],
        "category_limits": dict(profile["formal_root"]["category_limits"]),
        "fixed_overhead_category_limits": dict(
            profile["formal_root"]["fixed_overhead_category_limits"]
        ),
        "root_path": str(formal_root),
        "run_nonce": campaign_dir.name,
        "schema_version": FORMAL_ROOT_BUDGET_CONTRACT_SCHEMA,
    }
    formal_raw = _budget_canonical_json(formal_record)
    formal_identity = {
        "path": str(formal_path),
        "sha256": hashlib.sha256(formal_raw).hexdigest(),
        "size_bytes": len(formal_raw),
    }
    bootstrap_path = (
        campaign_dir / "bootstrap-authority/bootstrap-budget-contract.json"
    )
    bootstrap_record = {
        "authority": dict(_BUDGET_FALSE_AUTHORITY),
        "budget_profile_identity": dict(profile_identity),
        "budget_profile_sha256": profile["profile_sha256"],
        "category_limits": dict(profile["bootstrap"]["category_limits"]),
        "formal_root_contract_identity": formal_identity,
        "root_path": str(campaign_dir),
        "run_nonce": campaign_dir.name,
        "schema_version": BOOTSTRAP_BUDGET_CONTRACT_SCHEMA,
    }
    bootstrap_raw = _budget_canonical_json(bootstrap_record)
    bootstrap_identity = {
        "path": str(bootstrap_path),
        "sha256": hashlib.sha256(bootstrap_raw).hexdigest(),
        "size_bytes": len(bootstrap_raw),
    }
    return {
        "bootstrap_record": bootstrap_record,
        "bootstrap_identity": bootstrap_identity,
        "formal_record": formal_record,
        "formal_identity": formal_identity,
    }


class _BootstrapBudgetContractError(RuntimeError):
    """Fail-closed error for the in-bootstrap physical budget authority."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _bootstrap_budget_fd_identity(
    descriptor: int,
) -> dict[str, int | str]:
    metadata = os.fstat(descriptor)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
        "uid": metadata.st_uid,
    }


def _bootstrap_budget_relative_parts(value: str) -> tuple[str, ...]:
    if (
        type(value) is not str
        or not value
        or "\x00" in value
        or "\\" in value
    ):
        raise _BootstrapBudgetContractError(
            "INVALID_RELATIVE_PATH",
            "budget path is not one portable relative path",
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[-1].startswith(".ab16-budget-staging-")
    ):
        raise _BootstrapBudgetContractError(
            "INVALID_RELATIVE_PATH",
            f"unsafe budget path: {value!r}",
        )
    return path.parts


def _bootstrap_budget_open_directory(
    root_fd: int,
    relative: str,
) -> int:
    parts = () if relative == "." else _bootstrap_budget_relative_parts(relative)
    current = os.dup(root_fd)
    try:
        for part in parts:
            successor = os.open(
                part,
                os.O_RDONLY
                | os.O_CLOEXEC
                | os.O_DIRECTORY
                | os.O_NOFOLLOW,
                dir_fd=current,
            )
            os.close(current)
            current = successor
        return current
    except BaseException:
        os.close(current)
        raise


def _bootstrap_budget_rejoin_root(
    root: Path,
    descriptor: int,
) -> None:
    current = os.stat(root, follow_symlinks=False)
    retained = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(current.st_mode)
        or not stat.S_ISDIR(retained.st_mode)
        or (
            current.st_dev,
            current.st_ino,
            stat.S_IFMT(current.st_mode),
            current.st_uid,
        )
        != (
            retained.st_dev,
            retained.st_ino,
            stat.S_IFMT(retained.st_mode),
            retained.st_uid,
        )
    ):
        raise _BootstrapBudgetContractError(
            "ROOT_IDENTITY_DRIFT",
            "budget root no longer joins its retained descriptor",
        )


def _bootstrap_budget_preallocate(
    descriptor: int,
    maximum_bytes: int,
) -> None:
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or maximum_bytes <= 0
    ):
        raise _BootstrapBudgetContractError(
            "INVALID_BUDGET",
            "staging maximum must be positive",
        )
    try:
        os.posix_fallocate(descriptor, 0, maximum_bytes)
    except (AttributeError, OSError) as exc:
        raise _BootstrapBudgetContractError(
            "PHYSICAL_RESERVATION_FAILED",
            f"physical staging reservation failed: {exc}",
        ) from exc
    metadata = os.fstat(descriptor)
    if (
        metadata.st_size != maximum_bytes
        or metadata.st_blocks * 512 < maximum_bytes
    ):
        raise _BootstrapBudgetContractError(
            "PHYSICAL_RESERVATION_FAILED",
            "staging physical extent differs from its maximum",
        )


def _bootstrap_budget_write_extent(
    descriptor: int,
    raw: bytes,
    *,
    maximum_bytes: int,
) -> None:
    if not isinstance(raw, bytes) or len(raw) > maximum_bytes:
        raise _BootstrapBudgetContractError(
            "ARTIFACT_LIMIT_EXCEEDED",
            "payload exceeds its preallocated staging extent",
        )
    offset = 0
    while offset < len(raw):
        written = os.pwrite(descriptor, raw[offset:], offset)
        if written <= 0:
            raise _BootstrapBudgetContractError(
                "STAGING_SHORT_WRITE",
                "staging write made no progress",
            )
        offset += written
    os.ftruncate(descriptor, len(raw))
    os.fsync(descriptor)
    replay = _read_stable_fd(
        descriptor,
        limit=maximum_bytes,
        label="bootstrap staging extent",
    )
    if replay != raw:
        raise _BootstrapBudgetContractError(
            "STAGING_REPLAY_DRIFT",
            "staging same-FD replay differs from the exact payload",
        )


class _BootstrapRetainedDirectory:
    """One single-owner retained directory capability."""

    def __init__(
        self,
        *,
        descriptor: int,
        directory_path: str,
        owner_nonce: str,
        path: Path,
        purpose: str,
    ) -> None:
        self._descriptor = descriptor
        self._directory_path = directory_path
        self._owner_nonce = owner_nonce
        self._path = path
        self._purpose = purpose
        self._closed = False
        self._identity = _bootstrap_budget_fd_identity(descriptor)

    def fileno(self) -> int:
        if self._closed:
            raise _BootstrapBudgetContractError(
                "CAPABILITY_CLOSED",
                "retained directory is closed",
            )
        return self._descriptor

    def record(self) -> dict[str, object]:
        """Return the live capability identity without transferring ownership."""

        self.fileno()
        return {
            "directory_identity": dict(self._identity),
            "directory_path": self._directory_path,
            "owner_nonce": self._owner_nonce,
            "purpose": self._purpose,
        }

    def transfer_ownership(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[_BootstrapRetainedDirectory, dict[str, object]]:
        descriptor = os.dup(self.fileno())
        successor = _BootstrapRetainedDirectory(
            descriptor=descriptor,
            directory_path=self._directory_path,
            owner_nonce=to_owner_nonce,
            path=self._path,
            purpose=self._purpose,
        )
        record: dict[str, object] = {
            "from_owner_nonce": self._owner_nonce,
            "from_owner_nonce_sha256": hashlib.sha256(
                self._owner_nonce.encode("ascii")
            ).hexdigest(),
            "identity": dict(self._identity),
            "directory_path": self._directory_path,
            "path": str(self._path),
            "purpose": self._purpose,
            "schema_version": BOOTSTRAP_RETAINED_DIRECTORY_HANDOFF_SCHEMA,
            "to_owner_nonce": to_owner_nonce,
            "to_owner_nonce_sha256": hashlib.sha256(
                to_owner_nonce.encode("ascii")
            ).hexdigest(),
            "transfer_nonce": secrets.token_hex(16),
        }
        self.close()
        return successor, record

    def export_structural_handoff(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[dict[str, object], tuple[int, ...]]:
        successor, record = self.transfer_ownership(
            to_owner_nonce=to_owner_nonce
        )
        descriptor = successor.fileno()
        successor._closed = True
        return record, (descriptor,)

    def close(self) -> None:
        if self._closed:
            raise _BootstrapBudgetContractError(
                "CAPABILITY_ALREADY_CLOSED",
                "retained directory cannot close twice",
            )
        self._closed = True
        os.close(self._descriptor)


class _BootstrapRetainedStaging:
    """One nonrefundable same-directory preallocated staging inode."""

    def __init__(
        self,
        *,
        artifact_class: str,
        descriptor: int,
        maximum_bytes: int,
        owner_nonce: str,
        parent_fd: int,
        parent_path: Path,
        purpose: str,
        staging_name: str,
    ) -> None:
        self._artifact_class = artifact_class
        self._descriptor = descriptor
        self._maximum_bytes = maximum_bytes
        self._owner_nonce = owner_nonce
        self._parent_fd = parent_fd
        self._parent_path = parent_path
        self._purpose = purpose
        self._staging_name = staging_name
        self._closed = False
        self._consumed = False
        self._identity = _bootstrap_budget_fd_identity(descriptor)

    def fileno(self) -> int:
        if self._closed:
            raise _BootstrapBudgetContractError(
                "RESERVATION_CLOSED",
                "retained staging reservation is closed",
            )
        return self._descriptor

    def publish_bytes(
        self,
        target_name: str,
        raw: bytes,
        *,
        final_mode: int = 0o444,
    ) -> dict[str, object]:
        if self._closed or self._consumed:
            raise _BootstrapBudgetContractError(
                "RESERVATION_CONSUMED",
                "retained staging reservation is unavailable",
            )
        if len(_bootstrap_budget_relative_parts(target_name)) != 1:
            raise _BootstrapBudgetContractError(
                "INVALID_TARGET",
                "retained staging target must be one component",
            )
        self._consumed = True
        primary: BaseException | None = None
        try:
            _bootstrap_budget_write_extent(
                self._descriptor,
                raw,
                maximum_bytes=self._maximum_bytes,
            )
            os.fchmod(self._descriptor, final_mode)
            os.fsync(self._descriptor)
            _rename_noreplace_at(
                self._parent_fd,
                self._staging_name,
                target_name,
            )
            os.fsync(self._parent_fd)
            named = os.stat(
                target_name,
                dir_fd=self._parent_fd,
                follow_symlinks=False,
            )
            retained = os.fstat(self._descriptor)
            if (
                _fd_signature(named) != _fd_signature(retained)
                or stat.S_IMODE(retained.st_mode) != final_mode
            ):
                raise _BootstrapBudgetContractError(
                    "PUBLICATION_IDENTITY_DRIFT",
                    "published staging inode did not retain its identity",
                )
            return {
                "path": str(self._parent_path / target_name),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                self.close()
            except BaseException as cleanup_error:
                if primary is None:
                    raise
                primary.add_note(
                    "retained staging publication cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )

    def transfer_ownership(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[_BootstrapRetainedStaging, dict[str, object]]:
        if self._closed or self._consumed:
            raise _BootstrapBudgetContractError(
                "RESERVATION_CONSUMED",
                "retained staging reservation cannot transfer",
            )
        successor = _BootstrapRetainedStaging(
            artifact_class=self._artifact_class,
            descriptor=os.dup(self._descriptor),
            maximum_bytes=self._maximum_bytes,
            owner_nonce=to_owner_nonce,
            parent_fd=os.dup(self._parent_fd),
            parent_path=self._parent_path,
            purpose=self._purpose,
            staging_name=self._staging_name,
        )
        record = {
            "artifact_class": self._artifact_class,
            "from_owner_nonce": self._owner_nonce,
            "from_owner_nonce_sha256": hashlib.sha256(
                self._owner_nonce.encode("ascii")
            ).hexdigest(),
            "maximum_bytes": self._maximum_bytes,
            "parent_identity": _bootstrap_budget_fd_identity(
                self._parent_fd
            ),
            "parent_path": str(self._parent_path),
            "purpose": self._purpose,
            "schema_version": BOOTSTRAP_STAGING_HANDOFF_SCHEMA,
            "shared_parent_fd": False,
            "staging_identity": dict(self._identity),
            "staging_name": self._staging_name,
            "to_owner_nonce": to_owner_nonce,
            "to_owner_nonce_sha256": hashlib.sha256(
                to_owner_nonce.encode("ascii")
            ).hexdigest(),
            "transfer_nonce": secrets.token_hex(16),
        }
        self.close()
        return successor, record

    def export_structural_handoff(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[dict[str, object], tuple[int, ...]]:
        successor, record = self.transfer_ownership(
            to_owner_nonce=to_owner_nonce
        )
        descriptors = (successor._parent_fd, successor._descriptor)
        successor._closed = True
        return record, descriptors

    def export_staging_only_handoff(
        self,
        *,
        to_owner_nonce: str,
        shared_parent_identity: Mapping[str, object],
    ) -> tuple[dict[str, object], tuple[int, ...]]:
        """Detach only the staging FD when one shared parent FD is transferred."""

        if (
            self._closed
            or self._consumed
            or dict(shared_parent_identity)
            != _bootstrap_budget_fd_identity(self._parent_fd)
        ):
            raise _BootstrapBudgetContractError(
                "SHARED_PARENT_IDENTITY_DRIFT",
                "outside staging does not join the shared parent",
            )
        staging_fd = os.dup(self._descriptor)
        if (
            _bootstrap_budget_fd_identity(staging_fd)
            != _bootstrap_budget_fd_identity(self._descriptor)
        ):
            os.close(staging_fd)
            raise _BootstrapBudgetContractError(
                "HANDOFF_IDENTITY_DRIFT",
                "detached outside staging identity drifted",
            )
        record = {
            "artifact_class": self._artifact_class,
            "from_owner_nonce": self._owner_nonce,
            "from_owner_nonce_sha256": hashlib.sha256(
                self._owner_nonce.encode("ascii")
            ).hexdigest(),
            "maximum_bytes": self._maximum_bytes,
            "parent_identity": dict(shared_parent_identity),
            "parent_path": str(self._parent_path),
            "purpose": self._purpose,
            "schema_version": BOOTSTRAP_STAGING_HANDOFF_SCHEMA,
            "shared_parent_fd": True,
            "staging_identity": dict(self._identity),
            "staging_name": self._staging_name,
            "to_owner_nonce": to_owner_nonce,
            "to_owner_nonce_sha256": hashlib.sha256(
                to_owner_nonce.encode("ascii")
            ).hexdigest(),
            "transfer_nonce": secrets.token_hex(16),
        }
        try:
            self.close()
        except BaseException:
            os.close(staging_fd)
            raise
        return record, (staging_fd,)

    def close(self) -> None:
        if self._closed:
            raise _BootstrapBudgetContractError(
                "RESERVATION_ALREADY_CLOSED",
                "retained staging reservation cannot close twice",
            )
        self._closed = True
        primary: BaseException | None = None
        for descriptor in (self._descriptor, self._parent_fd):
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "second retained-staging FD close also failed"
                    )
        if primary is not None:
            raise primary


class _BootstrapBudgetAccount:
    """Bootstrap-native hierarchical budget and physical staging owner."""

    def __init__(
        self,
        *,
        root: Path,
        root_fd: int,
        category_limits: Mapping[str, int],
        owner_nonce: str,
    ) -> None:
        self.root = root
        self._root_fd = root_fd
        self._limits = dict(category_limits)
        self._debited = {name: 0 for name in self._limits}
        self._owner_nonce = owner_nonce
        self._arms: dict[str, dict[str, int]] = {}
        self._arm_debits: dict[str, dict[str, int]] = {}
        self._closed = False
        self._staging_counter = 0
        self._root_identity = _bootstrap_budget_fd_identity(root_fd)
        self._published: list[dict[str, object]] = []

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        category_limits: Mapping[str, int],
        owner_nonce: str,
    ) -> _BootstrapBudgetAccount:
        absolute = Path(os.path.abspath(root))
        _bootstrap_mkdir_exclusive(absolute, mode=0o700)
        root_fd = os.open(
            absolute,
            os.O_RDONLY
            | os.O_CLOEXEC
            | os.O_DIRECTORY
            | os.O_NOFOLLOW,
        )
        return cls(
            root=absolute,
            root_fd=root_fd,
            category_limits=category_limits,
            owner_nonce=owner_nonce,
        )

    def _require_open(self) -> None:
        if self._closed:
            raise _BootstrapBudgetContractError(
                "ACCOUNT_CLOSED",
                "bootstrap budget account is closed",
            )
        _bootstrap_budget_rejoin_root(self.root, self._root_fd)

    def _debit(
        self,
        artifact_class: str,
        amount: int,
        *,
        arm_slot: str | None,
    ) -> None:
        self._require_open()
        if artifact_class not in self._limits:
            raise _BootstrapBudgetContractError(
                "INVALID_ARTIFACT_CLASS",
                f"artifact class is not budgeted: {artifact_class}",
            )
        if amount <= 0 or self._debited[artifact_class] + amount > self._limits[artifact_class]:
            raise _BootstrapBudgetContractError(
                "BUDGET_EXHAUSTED",
                f"formal-root {artifact_class} budget is exhausted",
            )
        if arm_slot is not None:
            if arm_slot not in self._arms:
                raise _BootstrapBudgetContractError(
                    "ARM_NOT_ALLOCATED",
                    f"arm slot is not allocated: {arm_slot}",
                )
            arm_limits = self._arms[arm_slot]
            arm_debits = self._arm_debits[arm_slot]
            if (
                artifact_class not in arm_limits
                or arm_debits[artifact_class] + amount
                > arm_limits[artifact_class]
            ):
                raise _BootstrapBudgetContractError(
                    "ARM_BUDGET_EXHAUSTED",
                    f"arm {arm_slot} {artifact_class} budget is exhausted",
                )
            arm_debits[artifact_class] += amount
        self._debited[artifact_class] += amount

    def allocate_arm(
        self,
        arm_slot: str,
        *,
        category_limits: Mapping[str, int],
    ) -> dict[str, object]:
        self._require_open()
        if arm_slot in self._arms:
            raise _BootstrapBudgetContractError(
                "ARM_ALREADY_ALLOCATED",
                f"arm slot was already allocated: {arm_slot}",
            )
        checked = {
            key: int(value)
            for key, value in category_limits.items()
            if key in self._limits
        }
        if (
            set(checked) != set(category_limits)
            or any(value <= 0 for value in checked.values())
            or any(
                checked[key] > self._limits[key]
                for key in checked
            )
        ):
            raise _BootstrapBudgetContractError(
                "INVALID_ARM_BUDGET",
                "arm allocation exceeds its formal-root category",
            )
        self._arms[arm_slot] = checked
        self._arm_debits[arm_slot] = {
            key: 0 for key in checked
        }
        return {
            "arm_slot": arm_slot,
            "category_limits": dict(checked),
            "state": "ALLOCATED_NONREFUNDABLE",
        }

    def register_directory(
        self,
        relative: str,
        *,
        mode: int = 0o700,
    ) -> Path:
        self._require_open()
        parts = _bootstrap_budget_relative_parts(relative)
        current = os.dup(self._root_fd)
        built = self.root
        try:
            for part in parts:
                built /= part
                try:
                    os.mkdir(part, mode, dir_fd=current)
                except FileExistsError:
                    pass
                successor = os.open(
                    part,
                    os.O_RDONLY
                    | os.O_CLOEXEC
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW,
                    dir_fd=current,
                )
                metadata = os.fstat(successor)
                if (
                    not stat.S_ISDIR(metadata.st_mode)
                    or metadata.st_uid != os.getuid()
                ):
                    os.close(successor)
                    raise _BootstrapBudgetContractError(
                        "DIRECTORY_IDENTITY_DRIFT",
                        f"budget directory identity drifted: {built}",
                    )
                os.close(current)
                current = successor
            os.fchmod(current, mode)
            os.fsync(current)
        finally:
            os.close(current)
        return built

    def retain_directory(
        self,
        relative: str,
        *,
        purpose: str,
    ) -> _BootstrapRetainedDirectory:
        self._require_open()
        descriptor = _bootstrap_budget_open_directory(
            self._root_fd,
            relative,
        )
        return _BootstrapRetainedDirectory(
            descriptor=descriptor,
            directory_path=relative,
            owner_nonce=self._owner_nonce,
            path=self.root / relative,
            purpose=purpose,
        )

    def reserve_retained_staging(
        self,
        parent: str,
        *,
        maximum_bytes: int,
        artifact_class: str,
        purpose: str,
        arm_slot: str | None = None,
    ) -> _BootstrapRetainedStaging:
        self._debit(
            artifact_class,
            maximum_bytes,
            arm_slot=arm_slot,
        )
        parent_fd = _bootstrap_budget_open_directory(
            self._root_fd,
            parent,
        )
        self._staging_counter += 1
        staging_name = (
            ".ab16-budget-staging-"
            f"{self._staging_counter:08d}-{secrets.token_hex(12)}"
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                staging_name,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            _bootstrap_budget_preallocate(
                descriptor,
                maximum_bytes,
            )
            os.fsync(descriptor)
            os.fsync(parent_fd)
            result = _BootstrapRetainedStaging(
                artifact_class=artifact_class,
                descriptor=descriptor,
                maximum_bytes=maximum_bytes,
                owner_nonce=self._owner_nonce,
                parent_fd=parent_fd,
                parent_path=self.root / parent,
                purpose=purpose,
                staging_name=staging_name,
            )
            descriptor = None
            parent_fd = -1
            return result
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if parent_fd >= 0:
                os.close(parent_fd)

    def reserve_retained_staging_at_parent(
        self,
        parent: _BootstrapRetainedDirectory,
        *,
        maximum_bytes: int,
        artifact_class: str,
        purpose: str,
        arm_slot: str | None = None,
    ) -> _BootstrapRetainedStaging:
        """Debit this account while staging in one separately retained parent."""

        self._debit(
            artifact_class,
            maximum_bytes,
            arm_slot=arm_slot,
        )
        parent_fd = os.dup(parent.fileno())
        self._staging_counter += 1
        staging_name = (
            ".ab16-budget-staging-"
            f"{self._staging_counter:08d}-{secrets.token_hex(12)}"
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                staging_name,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            _bootstrap_budget_preallocate(
                descriptor,
                maximum_bytes,
            )
            os.fsync(descriptor)
            os.fsync(parent_fd)
            result = _BootstrapRetainedStaging(
                artifact_class=artifact_class,
                descriptor=descriptor,
                maximum_bytes=maximum_bytes,
                owner_nonce=self._owner_nonce,
                parent_fd=parent_fd,
                parent_path=parent._path,
                purpose=purpose,
                staging_name=staging_name,
            )
            descriptor = None
            parent_fd = -1
            return result
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if parent_fd >= 0:
                os.close(parent_fd)

    def publish_bytes(
        self,
        relative: str,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
        final_mode: int = 0o444,
    ) -> dict[str, object]:
        parts = _bootstrap_budget_relative_parts(relative)
        parent = PurePosixPath(*parts[:-1]).as_posix()
        if parent == ".":
            parent = "."
        reservation = self.reserve_retained_staging(
            parent,
            maximum_bytes=maximum_bytes,
            artifact_class=artifact_class,
            purpose=f"publish-{hashlib.sha256(relative.encode()).hexdigest()}",
            arm_slot=arm_slot,
        )
        primary: BaseException | None = None
        try:
            published = reservation.publish_bytes(
                parts[-1],
                raw,
                final_mode=final_mode,
            )
            record = {**published, "path": relative}
            self._published.append(record)
            return record
        except BaseException as exc:
            primary = exc
            raise
        finally:
            if not reservation._closed:
                try:
                    reservation.close()
                except BaseException as cleanup_error:
                    if primary is None:
                        raise
                    primary.add_note(
                        "published staging FD cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )

    def published_artifacts(self) -> list[dict[str, object]]:
        return [dict(record) for record in self._published]

    def transfer_ownership(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[_BootstrapBudgetAccount, dict[str, object]]:
        self._require_open()
        successor = _BootstrapBudgetAccount(
            root=self.root,
            root_fd=os.dup(self._root_fd),
            category_limits=self._limits,
            owner_nonce=to_owner_nonce,
        )
        successor._debited = dict(self._debited)
        successor._arms = {
            key: dict(value) for key, value in self._arms.items()
        }
        successor._arm_debits = {
            key: dict(value)
            for key, value in self._arm_debits.items()
        }
        successor._published = [
            dict(record) for record in self._published
        ]
        record = {
            "arm_allocations": successor._arms,
            "arm_debits": successor._arm_debits,
            "category_debits": dict(successor._debited),
            "category_limits": dict(successor._limits),
            "from_owner_nonce_sha256": hashlib.sha256(
                self._owner_nonce.encode("ascii")
            ).hexdigest(),
            "from_owner_nonce": self._owner_nonce,
            "root_identity": dict(self._root_identity),
            "root_path": str(self.root),
            "schema_version": BOOTSTRAP_BUDGET_ACCOUNT_HANDOFF_SCHEMA,
            "to_owner_nonce": to_owner_nonce,
            "to_owner_nonce_sha256": hashlib.sha256(
                to_owner_nonce.encode("ascii")
            ).hexdigest(),
            "transfer_nonce": secrets.token_hex(16),
        }
        self.close()
        return successor, record

    def export_structural_handoff(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[dict[str, object], tuple[int, ...]]:
        successor, record = self.transfer_ownership(
            to_owner_nonce=to_owner_nonce
        )
        descriptor = successor._root_fd
        successor._closed = True
        return record, (descriptor,)

    def close(self) -> None:
        if self._closed:
            raise _BootstrapBudgetContractError(
                "ACCOUNT_ALREADY_CLOSED",
                "bootstrap budget account cannot close twice",
            )
        self._closed = True
        os.close(self._root_fd)


class _BootstrapBudgetAuthority:
    """Route the sole bootstrap actor's retained writes through one broker."""

    def __init__(
        self,
        *,
        base: Any,
        broker: _BootstrapBudgetAccount,
        profile: Mapping[str, Any],
        arm_slot: str = "bootstrap-authority",
        budget_module: Any | None = None,
    ) -> None:
        del budget_module
        self._base = base
        self._broker = broker
        self._root = Path(broker.root)
        bootstrap = profile["bootstrap"]
        self._directories = {
            str(item["path"]): int(str(item["mode_octal"]), 8)
            for item in bootstrap["fixed_directories"]
        }
        self._artifacts_by_path = {
            str(item["path"]): dict(item)
            for item in bootstrap["artifact_maxima"]
        }
        self._used_paths: set[str] = set()
        self._arm_slot = arm_slot

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def _relative(self, path: Path | str, label: str) -> str:
        absolute = Path(os.path.abspath(path))
        try:
            relative = absolute.relative_to(self._root).as_posix()
        except ValueError as exc:
            raise BootstrapError(
                f"{label} escaped the bootstrap budget root"
            ) from exc
        return "." if relative == "." else _budget_relative_path(relative, label)

    def mkdir_exclusive(
        self,
        path: Path | str,
        *,
        mode: int = 0o755,
    ) -> Path:
        relative = self._relative(path, "budgeted bootstrap directory")
        if relative == ".":
            if Path(os.path.abspath(path)) != self._root:
                raise BootstrapError("bootstrap budget root identity drifted")
            return self._root
        if relative not in self._directories:
            raise BootstrapError(
                f"bootstrap directory is absent from fixed budget profile: {relative}"
            )
        if isinstance(mode, bool) or not isinstance(mode, int):
            raise BootstrapError("bootstrap directory requested an invalid mode")
        self._broker.register_directory(relative, mode=0o700)
        return self._root / relative

    def write_exclusive(
        self,
        path: Path | str,
        raw: bytes,
        *,
        mode: int = 0o600,
    ) -> dict[str, object]:
        relative = self._relative(path, "budgeted bootstrap artifact")
        try:
            artifact = self._artifacts_by_path[relative]
        except KeyError as exc:
            raise BootstrapError(
                f"bootstrap artifact is absent from fixed budget profile: {relative}"
            ) from exc
        if relative in self._used_paths:
            raise BootstrapError(
                f"bootstrap artifact publication was already attempted: {relative}"
            )
        self._used_paths.add(relative)
        if not isinstance(raw, bytes):
            raise BootstrapError("bootstrap artifact payload is not exact bytes")
        final_mode = 0o555 if mode & 0o111 else 0o444
        try:
            published = self._broker.publish_bytes(
                relative,
                raw,
                maximum_bytes=int(artifact["maximum_bytes"]),
                artifact_class=str(artifact["artifact_class"]),
                arm_slot=self._arm_slot,
                final_mode=final_mode,
            )
        except _BootstrapBudgetContractError as exc:
            raise BootstrapError(
                f"bootstrap budget publication failed closed: {exc.code}"
            ) from exc
        snapshot = self._base.snapshot_regular(self._root / relative)
        identity = self._base.detached_identity(snapshot)
        if (
            identity["sha256"] != published["sha256"]
            or identity["size_bytes"] != published["size_bytes"]
            or stat.S_IMODE(snapshot.stat_result.st_mode) != final_mode
        ):
            raise BootstrapError(
                f"bootstrap budget publication replay drifted: {relative}"
            )
        return identity

    def required_success_paths(self) -> set[str]:
        return {
            path
            for path, item in self._artifacts_by_path.items()
            if item["required_on_success"] is True
        }

    def assert_success_writes_complete(self) -> None:
        missing = self.required_success_paths() - self._used_paths
        if missing:
            raise BootstrapError(
                "bootstrap required budgeted artifacts were not published: "
                f"{sorted(missing)!r}"
            )

    def seal_directories(self) -> None:
        for relative, mode in sorted(
            self._directories.items(),
            key=lambda item: (-len(PurePosixPath(item[0]).parts), item[0]),
        ):
            if relative != "." and mode == 0o500:
                self._broker.register_directory(relative, mode=0o500)


def _formal_profile_artifact(
    profile: Mapping[str, Any],
    *,
    relative_path: str,
) -> Mapping[str, Any]:
    matches = [
        item
        for item in profile["formal_root"]["artifact_maxima"]
        if item["path"] == relative_path
    ]
    if len(matches) != 1:
        raise BootstrapError(
            f"formal budget profile lacks one exact artifact: {relative_path}"
        )
    return matches[0]


def _bootstrap_runtime_budget_bindings(
    *,
    campaign_dir: Path,
    profile: Mapping[str, Any],
    path_preregistration: Mapping[str, Any],
) -> dict[str, object]:
    reserve = _exact_keys(
        profile["bootstrap"]["failure_closeout_reserve"],
        {
            "artifact_class",
            "maximum_bytes",
            "parent_path",
            "purpose",
            "target_name",
        },
        "bootstrap failure closeout reserve",
    )
    expected_failure_path = (
        campaign_dir
        / str(reserve["parent_path"])
        / str(reserve["target_name"])
    )
    if (
        expected_failure_path
        != Path(path_preregistration["bootstrap_package_failure_closeout_path"])
        or reserve["artifact_class"] != "closeout"
        or reserve["purpose"] != "bootstrap-failure-closeout"
    ):
        raise BootstrapError(
            "bootstrap failure reserve differs from the preregistered path"
        )
    handoff = _formal_profile_artifact(
        profile,
        relative_path="formal-root-budget-handoff.json",
    )
    if (
        handoff["artifact_class"] != "metadata"
        or handoff["required_on_success"] is not True
        or isinstance(handoff["maximum_bytes"], bool)
        or not isinstance(handoff["maximum_bytes"], int)
        or handoff["maximum_bytes"] <= 0
        or Path(path_preregistration["formal_root_budget_handoff_path"])
        != (
            campaign_dir
            / "formal-ab16/artifacts/formal-root-budget-handoff.json"
        )
    ):
        raise BootstrapError(
            "formal-root budget handoff artifact binding drifted"
        )
    return {
        "artifact_class": "metadata",
        "maximum_bytes": handoff["maximum_bytes"],
        "relative_path": "formal-root-budget-handoff.json",
    }


def _create_bootstrap_budget_runtime(
    *,
    campaign_dir: Path,
    profile: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, object]],
    budget_source_bytes: bytes | None = None,
    budget_source_identity: Mapping[str, object] | None = None,
    # Compatibility-only call shape for existing zero-authority tests.  The
    # objects are deliberately ignored: no external project module may become
    # executable before package verification.
    base_authority: Any | None = None,
    budget_module: Any | None = None,
    budget_module_bytes: bytes | None = None,
    budget_module_source_identity: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Establish bootstrap budget plus the formal-root/arm hierarchy first."""

    del base_authority, budget_module
    source_bytes = (
        budget_source_bytes
        if budget_source_bytes is not None
        else budget_module_bytes
    )
    source_identity = (
        budget_source_identity
        if budget_source_identity is not None
        else budget_module_source_identity
    )
    if source_bytes is None or source_identity is None:
        raise BootstrapError(
            "planned budget source bytes/identity are required as data"
        )
    expected_budget_source = _exact_keys(
        source_identity,
        {
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "sha256",
            "size_bytes",
        },
        "fixed-HEAD budget authority source",
    )
    if (
        hashlib.sha256(source_bytes).hexdigest()
        != expected_budget_source["sha256"]
        or len(source_bytes) != expected_budget_source["size_bytes"]
    ):
        raise BootstrapError(
            "planned fixed-HEAD budget authority bytes drifted"
        )
    bootstrap_limits = dict(profile["bootstrap"]["category_limits"])
    formal_limits = dict(profile["formal_root"]["category_limits"])
    bootstrap_broker = _BootstrapBudgetAccount.create(
        campaign_dir,
        category_limits=bootstrap_limits,
        owner_nonce="bootstrap-owner",
    )
    formal_broker: Any | None = None
    bootstrap_failure: Any | None = None
    control_parent: Any | None = None
    final_release_parent: Any | None = None
    formal_reservations: dict[str, Any] = {}
    primary: BaseException | None = None
    try:
        bootstrap_broker.allocate_arm(
            "bootstrap-authority",
            category_limits=bootstrap_limits,
        )
        adapter = _BootstrapBudgetAuthority(
            base=_BOOTSTRAP_MECHANICAL_AUTHORITY,
            broker=bootstrap_broker,
            profile=profile,
        )
        bootstrap_broker.register_directory("bootstrap-authority")
        bootstrap_broker.register_directory("formal-ab16")
        bootstrap_broker.register_directory("formal-ab16/control")
        bootstrap_broker.register_directory(
            OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
        )
        control_parent = bootstrap_broker.retain_directory(
            "formal-ab16/control",
            purpose="formal-control-parent",
        )
        final_release_parent = bootstrap_broker.retain_directory(
            OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
            purpose="outside-formal-root-final-release-parent",
        )
        # Establish the later formal hierarchy before any package/bootstrap
        # payload byte.  This is a separate broker rooted exactly at
        # ``formal-ab16``; it never receives a campaign-root writable FD.
        formal_broker = _BootstrapBudgetAccount.create(
            campaign_dir / "formal-ab16/artifacts",
            category_limits=formal_limits,
            owner_nonce="bootstrap-formal-owner",
        )
        formal_directories = {
            str(item["path"]): int(str(item["mode_octal"]), 8)
            for item in profile["formal_root"]["fixed_directories"]
        }
        for relative in sorted(
            (path for path in formal_directories if path != "."),
            key=lambda path: (len(PurePosixPath(path).parts), path),
        ):
            formal_broker.register_directory(relative, mode=0o700)
        bootstrap_reserve = profile["bootstrap"]["failure_closeout_reserve"]
        bootstrap_parent = str(bootstrap_reserve["parent_path"])
        if bootstrap_parent != ".":
            bootstrap_broker.register_directory(bootstrap_parent)
        # The externally frozen contract already exists as canonical bytes in
        # memory.  This first retained inode is the physical closeout reserve
        # that makes every later package failure terminalizable.
        bootstrap_failure = bootstrap_broker.reserve_retained_staging(
            bootstrap_parent,
            maximum_bytes=int(bootstrap_reserve["maximum_bytes"]),
            artifact_class=str(bootstrap_reserve["artifact_class"]),
            purpose=str(bootstrap_reserve["purpose"]),
            arm_slot="bootstrap-authority",
        )
        for reservation_profile in profile["formal_root"][
            "fixed_purpose_reservations"
        ]:
            purpose = str(reservation_profile["purpose"])
            parent_scope = str(reservation_profile["parent_scope"])
            reservation_parent = str(
                reservation_profile["parent_path"]
            )
            if parent_scope == "campaign-root":
                if (
                    purpose not in OUTSIDE_FINAL_RELEASE_RESERVATIONS
                    or reservation_profile["artifact_class"] != "closeout"
                    or int(reservation_profile["maximum_bytes"])
                    != OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES
                    or reservation_parent
                    != OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
                    or str(reservation_profile["target_name"])
                    != OUTSIDE_FINAL_RELEASE_RESERVATIONS[purpose]
                ):
                    raise BootstrapError(
                        "outside final-release reservation profile drifted"
                    )
                formal_reservations[purpose] = (
                    formal_broker.reserve_retained_staging_at_parent(
                        final_release_parent,
                        maximum_bytes=OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
                        artifact_class="closeout",
                        purpose=purpose,
                    )
                )
                continue
            if (
                parent_scope != "formal-root"
                or purpose in OUTSIDE_FINAL_RELEASE_RESERVATIONS
            ):
                raise BootstrapError(
                    "formal-root reservation scope drifted"
                )
            if reservation_parent != ".":
                formal_broker.register_directory(reservation_parent)
            formal_reservations[purpose] = (
                formal_broker.reserve_retained_staging(
                    reservation_parent,
                    maximum_bytes=int(
                        reservation_profile["maximum_bytes"]
                    ),
                    artifact_class=str(
                        reservation_profile["artifact_class"]
                    ),
                    purpose=purpose,
                )
            )
        adapter.write_exclusive(
            contracts["bootstrap_identity"]["path"],
            _budget_canonical_json(contracts["bootstrap_record"]),
            mode=0o444,
        )

        formal_contract_relative = "formal-root-budget-contract.json"
        formal_contract_artifact = _formal_profile_artifact(
            profile,
            relative_path=formal_contract_relative,
        )
        formal_contract_raw = _budget_canonical_json(
            contracts["formal_record"]
        )
        formal_contract_record = formal_broker.publish_bytes(
            formal_contract_relative,
            formal_contract_raw,
            maximum_bytes=int(formal_contract_artifact["maximum_bytes"]),
            artifact_class=str(formal_contract_artifact["artifact_class"]),
        )
        if {
            key: formal_contract_record[key]
            for key in ("path", "sha256", "size_bytes")
        } != {
            "path": "formal-root-budget-contract.json",
            "sha256": contracts["formal_identity"]["sha256"],
            "size_bytes": contracts["formal_identity"]["size_bytes"],
        }:
            raise BootstrapError("formal-root budget contract publication drifted")
        for relative, mode in sorted(
            formal_directories.items(),
            key=lambda item: (-len(PurePosixPath(item[0]).parts), item[0]),
        ):
            if relative != "." and mode == 0o500:
                formal_broker.register_directory(relative, mode=mode)

        return {
            "adapter": adapter,
            "bootstrap_account": bootstrap_broker,
            "bootstrap_failure_reservation": bootstrap_failure,
            # Transitional aliases for callers being migrated in this cohort.
            # Package adoption must consume only export_structural_handoff()
            # records and retained FDs, never these Python object identities.
            "bootstrap_broker": bootstrap_broker,
            "control_parent_capability": control_parent,
            "final_release_parent_capability": final_release_parent,
            "formal_account": formal_broker,
            "formal_broker": formal_broker,
            "formal_reservations": formal_reservations,
        }
    except BaseException as exc:
        primary = exc
        if bootstrap_failure is not None:
            reserve = profile["bootstrap"]["failure_closeout_reserve"]
            try:
                bootstrap_failure.publish_bytes(
                    str(reserve["target_name"]),
                    _budget_canonical_json(
                        {
                            "authority": dict(_BUDGET_FALSE_AUTHORITY),
                            "error_type": type(exc).__name__,
                            "formal_campaign_creation_authorized": False,
                            "root_path": str(campaign_dir),
                            "schema_version": (
                                BOOTSTRAP_PACKAGE_FAILURE_CLOSEOUT_SCHEMA
                            ),
                            "state": "markerless-incomplete",
                            "status": "FAIL_CLOSED",
                        }
                    ),
                )
            except BaseException as closeout_error:
                exc.add_note(
                    "bootstrap failure closeout also failed: "
                    f"{type(closeout_error).__name__}: {closeout_error}"
                )
        raise
    finally:
        if primary is not None:
            if control_parent is not None:
                try:
                    control_parent.close()
                except BaseException as cleanup_error:
                    primary.add_note(
                        "formal control-parent cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            if final_release_parent is not None:
                try:
                    final_release_parent.close()
                except BaseException as cleanup_error:
                    primary.add_note(
                        "outside final-release parent cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            try:
                bootstrap_broker.close()
            except BaseException as cleanup_error:
                primary.add_note(
                    "bootstrap budget broker cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
            for purpose, reservation in reversed(
                tuple(formal_reservations.items())
            ):
                try:
                    reservation.close()
                except BaseException as cleanup_error:
                    primary.add_note(
                        f"formal {purpose} reserve cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            if formal_broker is not None:
                try:
                    formal_broker.close()
                except BaseException as cleanup_error:
                    primary.add_note(
                        "formal budget broker cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )


def _export_bootstrap_structural_handoff(
    *,
    budget_runtime: Mapping[str, object],
    replay_authorization: VerifiedPackageIndependentReplay,
    to_owner_nonce: str,
) -> tuple[dict[str, object], tuple[int, ...]]:
    """Irreversibly detach the exact post-verifier package adoption cohort."""

    if (
        not isinstance(
            replay_authorization,
            VerifiedPackageIndependentReplay,
        )
        or replay_authorization.result.get("schema")
        != PACKAGE_INDEPENDENT_REPLAY_SCHEMA
        or replay_authorization.result.get("status") != "PASS"
    ):
        raise BootstrapError(
            "verified package authorization is required before structural adoption"
        )
    replay_authorization.fileno()
    if (
        type(to_owner_nonce) is not str
        or len(to_owner_nonce) != 64
        or any(character not in "0123456789abcdef" for character in to_owner_nonce)
    ):
        raise BootstrapError("structural handoff owner nonce is malformed")
    formal = budget_runtime.get("formal_account")
    reservations = budget_runtime.get("formal_reservations")
    control = budget_runtime.get("control_parent_capability")
    outside_parent = budget_runtime.get("final_release_parent_capability")
    if (
        not isinstance(formal, _BootstrapBudgetAccount)
        or not isinstance(reservations, Mapping)
        or set(reservations) != set(_FORMAL_FIXED_RESERVATION_CONTRACT)
        or not isinstance(control, _BootstrapRetainedDirectory)
        or not isinstance(outside_parent, _BootstrapRetainedDirectory)
    ):
        raise BootstrapError(
            "bootstrap structural handoff object cohort drifted"
        )
    typed_reservations = cast(
        Mapping[str, _BootstrapRetainedStaging],
        reservations,
    )
    descriptors: list[int] = []
    fd_roles: list[str] = []
    reservation_records: dict[str, dict[str, object]] = {}
    primary: BaseException | None = None

    def append(
        role_prefix: str,
        record_and_fds: tuple[dict[str, object], tuple[int, ...]],
        *,
        suffixes: Sequence[str],
    ) -> dict[str, object]:
        record, owned = record_and_fds
        for descriptor in owned:
            if (
                isinstance(descriptor, bool)
                or not isinstance(descriptor, int)
                or descriptor < 0
                or descriptor in descriptors
            ):
                raise BootstrapError(
                    f"structural handoff FD identity drifted: {role_prefix}"
                )
            descriptors.append(descriptor)
        if len(owned) != len(suffixes):
            raise BootstrapError(
                f"structural handoff FD count drifted: {role_prefix}"
            )
        fd_roles.extend(
            f"{role_prefix}:{suffix}" for suffix in suffixes
        )
        return record

    try:
        account_record = append(
            "formal-account",
            formal.export_structural_handoff(
                to_owner_nonce=to_owner_nonce
            ),
            suffixes=("root",),
        )
        for purpose in sorted(
            set(typed_reservations)
            - set(OUTSIDE_FINAL_RELEASE_RESERVATIONS)
        ):
            reservation_records[purpose] = append(
                f"reservation:{purpose}",
                typed_reservations[purpose].export_structural_handoff(
                    to_owner_nonce=to_owner_nonce
                ),
                suffixes=("parent", "staging"),
            )
        outside_parent_record = append(
            "outside-final-release",
            outside_parent.export_structural_handoff(
                to_owner_nonce=to_owner_nonce
            ),
            suffixes=("parent",),
        )
        outside_parent_identity = cast(
            Mapping[str, object],
            outside_parent_record["identity"],
        )
        for purpose in sorted(OUTSIDE_FINAL_RELEASE_RESERVATIONS):
            reservation_records[purpose] = append(
                f"reservation:{purpose}",
                typed_reservations[
                    purpose
                ].export_staging_only_handoff(
                    to_owner_nonce=to_owner_nonce,
                    shared_parent_identity=outside_parent_identity,
                ),
                suffixes=("staging",),
            )
        control_record = append(
            "formal-control",
            control.export_structural_handoff(
                to_owner_nonce=to_owner_nonce
            ),
            suffixes=("parent",),
        )
        record = {
            "account": account_record,
            "control_parent": control_record,
            "fd_count": len(descriptors),
            "fd_roles": fd_roles,
            "outside_final_release_parent": outside_parent_record,
            "reservations": {
                purpose: reservation_records[purpose]
                for purpose in sorted(reservation_records)
            },
            "schema_version": BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA,
            "to_owner_nonce_sha256": hashlib.sha256(
                to_owner_nonce.encode("ascii")
            ).hexdigest(),
        }
        # One formal root, six ordinary FD pairs, one shared outside parent,
        # four outside staging FDs, and one formal-control parent.
        if len(descriptors) != 19:
            raise BootstrapError(
                "bootstrap structural handoff exact FD cohort drifted"
            )
        return record, tuple(descriptors)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if primary is not None:
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except BaseException as cleanup_error:
                    primary.add_note(
                        "detached structural handoff FD cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )


@contextmanager
def _activate_bootstrap_budget_authority(
    adapter: _BootstrapBudgetAuthority,
) -> Iterator[None]:
    """Install the explicit AB16-only backend for the sole bootstrap call."""

    global authority
    previous_authority = authority
    base = adapter._base
    previous_write = base.write_exclusive
    previous_mkdir = base.mkdir_exclusive
    authority = adapter
    base.write_exclusive = adapter.write_exclusive
    base.mkdir_exclusive = adapter.mkdir_exclusive
    try:
        yield
    finally:
        base.mkdir_exclusive = previous_mkdir
        base.write_exclusive = previous_write
        authority = previous_authority


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


def _load_authority_from_fixed_head() -> tuple[
    _BootstrapMechanicalAuthority,
    dict[str, Any],
]:
    """Bind planned fixed-HEAD bytes as data without executing either source."""

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
        budget_relative = BUDGET_AUTHORITY_PATH.relative_to(repository).as_posix()
        budget_source = _bootstrap_git(
            binding,
            "show",
            f"{head}:{budget_relative}",
            output_limit=16 << 20,
        )
        binding.update(
            {
                "authority_bytes": source,
                "budget_authority_bytes": budget_source,
                "authority_source_identity": {
                    "path": str(V4_AUTHORITY_PATH),
                    "sha256": hashlib.sha256(source).hexdigest(),
                    "size_bytes": len(source),
                },
                "budget_authority_source_identity": {
                    "path": str(BUDGET_AUTHORITY_PATH),
                    "sha256": hashlib.sha256(budget_source).hexdigest(),
                    "size_bytes": len(budget_source),
                },
                "repository_head": head,
                "repository_tree": tree,
            }
        )
        return _BOOTSTRAP_MECHANICAL_AUTHORITY, binding
    except BaseException:
        os.close(git_fd)
        os.close(parent_fd)
        raise


_PREPACKAGE_STATE: tuple[
    _BootstrapMechanicalAuthority,
    dict[str, Any],
] | None = None
_PREPACKAGE_STATE_LOCK = threading.Lock()


def _prepackage_state() -> tuple[
    _BootstrapMechanicalAuthority,
    dict[str, Any],
]:
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
    budget_relative = BUDGET_AUTHORITY_PATH.relative_to(repository).as_posix()
    bootstrap_head = _bootstrap_git(binding, "show", f"{head}:{bootstrap_relative}", output_limit=16 << 20)
    authority_head = _bootstrap_git(binding, "show", f"{head}:{authority_relative}", output_limit=16 << 20)
    budget_head = _bootstrap_git(
        binding,
        "show",
        f"{head}:{budget_relative}",
        output_limit=16 << 20,
    )
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
        or budget_head != binding["budget_authority_bytes"]
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


def _native_helper_elf_capability(
    raw: bytes,
    *,
    source_identity: Mapping[str, object],
) -> dict[str, object]:
    """Mechanically bind the only supported prebuilt native-helper ABI."""

    if sys.platform != "linux" or os.uname().machine != "x86_64":
        raise BootstrapError(
            "native budget helper requires the registered Linux x86_64 host"
        )
    if (
        source_identity.get("sha256") != NATIVE_BUDGET_HELPER_SHA256
        or source_identity.get("size_bytes") != NATIVE_BUDGET_HELPER_SIZE_BYTES
        or source_identity.get("mode") != NATIVE_BUDGET_HELPER_MODE
        or len(raw) != NATIVE_BUDGET_HELPER_SIZE_BYTES
        or hashlib.sha256(raw).hexdigest() != NATIVE_BUDGET_HELPER_SHA256
    ):
        raise BootstrapError("native budget helper fixed byte identity drifted")
    if (
        len(raw) < 64
        or raw[:4] != b"\x7fELF"
        or raw[4] != 2  # ELFCLASS64
        or raw[5] != 1  # ELFDATA2LSB
        or raw[6] != 1  # EV_CURRENT
        or raw[7] != 0  # ELFOSABI_SYSV
        or int.from_bytes(raw[16:18], "little") != 3  # ET_DYN
        or int.from_bytes(raw[18:20], "little") != 62  # EM_X86_64
        or int.from_bytes(raw[20:24], "little") != 1
    ):
        raise BootstrapError("native budget helper ELF identity drifted")
    program_offset = int.from_bytes(raw[32:40], "little")
    program_entry_size = int.from_bytes(raw[54:56], "little")
    program_count = int.from_bytes(raw[56:58], "little")
    if program_entry_size != 56 or program_count <= 0:
        raise BootstrapError("native budget helper ELF program table drifted")
    build_ids: list[str] = []
    for index in range(program_count):
        start = program_offset + index * program_entry_size
        end = start + program_entry_size
        if end > len(raw):
            raise BootstrapError("native budget helper ELF program table is truncated")
        if int.from_bytes(raw[start : start + 4], "little") != 4:  # PT_NOTE
            continue
        note_offset = int.from_bytes(raw[start + 8 : start + 16], "little")
        note_size = int.from_bytes(raw[start + 32 : start + 40], "little")
        note_end = note_offset + note_size
        if note_end > len(raw):
            raise BootstrapError("native budget helper ELF note table is truncated")
        cursor = note_offset
        while cursor < note_end:
            if cursor + 12 > note_end:
                raise BootstrapError("native budget helper ELF note header is truncated")
            name_size = int.from_bytes(raw[cursor : cursor + 4], "little")
            desc_size = int.from_bytes(raw[cursor + 4 : cursor + 8], "little")
            note_type = int.from_bytes(raw[cursor + 8 : cursor + 12], "little")
            cursor += 12
            name_end = cursor + name_size
            desc_start = (name_end + 3) & ~3
            desc_end = desc_start + desc_size
            next_note = (desc_end + 3) & ~3
            if name_end > note_end or desc_end > note_end or next_note > note_end:
                raise BootstrapError("native budget helper ELF note payload is truncated")
            name = raw[cursor:name_end]
            if note_type == 3 and name.rstrip(b"\0") == b"GNU":
                build_ids.append(raw[desc_start:desc_end].hex())
            cursor = next_note
    if build_ids != [NATIVE_BUDGET_HELPER_BUILD_ID_SHA1]:
        raise BootstrapError("native budget helper GNU BuildID drifted")
    return _native_helper_expected_capability()


def _native_helper_expected_capability() -> dict[str, object]:
    """Return the fixed package/runtime capability without opening a path."""

    return {
        "binary_format": "ELF64",
        "build_id_sha1": NATIVE_BUDGET_HELPER_BUILD_ID_SHA1,
        "byte_order": "little",
        "elf_abi": "SYSV",
        "elf_machine": 62,
        "elf_type": 3,
        "elf_version": 1,
        "host_machine": "x86_64",
        "host_platform": "linux",
        "mode": NATIVE_BUDGET_HELPER_MODE,
        "package_path": NATIVE_BUDGET_HELPER_PACKAGE_PATH,
        "sha256": NATIVE_BUDGET_HELPER_SHA256,
        "size_bytes": NATIVE_BUDGET_HELPER_SIZE_BYTES,
        "wrapper_package_path": NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH,
    }


def _native_helper_capability_from_full(
    full_identity: Mapping[str, object],
) -> dict[str, object]:
    snapshot = authority.snapshot_regular(str(full_identity["path"]))
    if authority.full_identity(
        snapshot,
        requested_path=str(full_identity["requested_path"]),
    ) != dict(full_identity):
        raise BootstrapError("native budget helper source identity drifted")
    return _native_helper_elf_capability(
        snapshot.data,
        source_identity=full_identity,
    )


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
        raw, full = authority.snapshot_tool(raw_path)
        if role == "native_budget_helper":
            _native_helper_elf_capability(raw, source_identity=full)
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
            "bootstrap_budget_contract_identity",
            "candidate_id",
            "candidate_only",
            "created_at_utc",
            "formal_campaign_creation_authorized",
            "formal_root_budget_contract_identity",
            "gate_a_receipt_identity",
            "native_budget_helper_source_identity",
            "package_verifier_source_identity",
            "path_preregistration_identity",
            "planned_source_identities",
            "planned_source_set_digest",
            "purpose",
            "resource_calibration_bundle_identities",
            "repository_head",
            "repository_root",
            "resource_budget_profile_identity",
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
    profile_identity = _mode_identity(
        record["resource_budget_profile_identity"],
        "candidate resource-budget profile",
    )
    _validate_resource_calibration_bundle_identities(
        record["resource_calibration_bundle_identities"],
        label="candidate resource calibration bundles",
    )
    planned_budget_identities: dict[str, Mapping[str, Any]] = {}
    for field in (
        "bootstrap_budget_contract_identity",
        "formal_root_budget_contract_identity",
    ):
        identity = _exact_keys(
            record[field],
            {"path", "sha256", "size_bytes"},
            f"candidate {field}",
        )
        if (
            type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] <= 0
        ):
            raise BootstrapError(f"candidate {field} is malformed")
        planned_budget_identities[field] = identity
    sources = _validate_source_identities(record["planned_source_identities"])
    verifier_source = _exact_keys(
        record["package_verifier_source_identity"],
        {"device", "inode", "mode", "mode_octal", "path", "sha256", "size_bytes"},
        "candidate package verifier source identity",
    )
    native_helper_source = _exact_keys(
        record["native_budget_helper_source_identity"],
        {
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "requested_path",
            "sha256",
            "size_bytes",
        },
        "candidate native budget helper source identity",
    )
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
        or verifier_source != sources["script.package_independent_verifier_v1"]
        or native_helper_source != sources["system.native_budget_helper"]
        or profile_identity["mode"] != 0o444
        or planned_budget_identities["bootstrap_budget_contract_identity"]["path"]
        != str(
            Path(record["target_campaign_dir"])
            / "bootstrap-authority/bootstrap-budget-contract.json"
        )
        or planned_budget_identities["formal_root_budget_contract_identity"]["path"]
        != str(
                Path(record["target_campaign_dir"])
                / "formal-ab16/artifacts/formal-root-budget-contract.json"
            )
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
                "pre_full_resource_gate_identity",
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
            "bootstrap_budget_contract_identity",
            "candidate_identity",
            "created_at_utc",
            "decision",
            "final_full_preflight_receipt_identity",
            "formal_campaign_creation_authorized",
            "formal_root_budget_contract_identity",
            "gate",
            "gate_a_receipt_identity",
            "gate_b_epoch_observation_identity",
            "native_budget_helper_source_identity",
            "package_verifier_source_identity",
            "planned_source_set_digest",
            "pre_full_resource_gate_identity",
            "pre_publication_resource_gate_identity",
            "publisher",
            "purpose",
            "resource_calibration_bundle_identities",
            "repository_head",
            "repository_root",
            "resource_budget_profile_identity",
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
    pre_full_resource_identity = _mode_identity(
        record["pre_full_resource_gate_identity"],
        "Gate-B pre-full resource gate",
    )
    pre_publication_resource_identity = _mode_identity(
        record["pre_publication_resource_gate_identity"],
        "Gate-B pre-publication resource gate",
    )
    verifier_source = _exact_keys(
        record["package_verifier_source_identity"],
        {"device", "inode", "mode", "mode_octal", "path", "sha256", "size_bytes"},
        "Gate-B package verifier source identity",
    )
    native_helper_source = _exact_keys(
        record["native_budget_helper_source_identity"],
        {
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "requested_path",
            "sha256",
            "size_bytes",
        },
        "Gate-B native budget helper source identity",
    )
    resource_budget_profile_identity = _mode_identity(
        record["resource_budget_profile_identity"],
        "Gate-B resource-budget profile",
    )
    _validate_resource_calibration_bundle_identities(
        record["resource_calibration_bundle_identities"],
        label="Gate-B resource calibration bundles",
    )
    for field in (
        "bootstrap_budget_contract_identity",
        "formal_root_budget_contract_identity",
    ):
        identity = _exact_keys(
            record[field],
            {"path", "sha256", "size_bytes"},
            f"Gate-B {field}",
        )
        if (
            type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] <= 0
        ):
            raise BootstrapError(f"Gate-B {field} is malformed")
    _validate_gate_b_publisher(
        record["publisher"],
        expected_output_path=record["publisher"]["output_path"],
    )
    if (
        final_identity["mode"] != 0o444
        or epoch_identity["mode"] != 0o444
        or pre_full_resource_identity["mode"] != 0o444
        or pre_publication_resource_identity["mode"] != 0o444
        or _snapshot_mode_identity(final_identity["path"]) != final_identity
        or _snapshot_mode_identity(epoch_identity["path"]) != epoch_identity
        or _snapshot_mode_identity(pre_full_resource_identity["path"])
        != pre_full_resource_identity
        or _snapshot_mode_identity(pre_publication_resource_identity["path"])
        != pre_publication_resource_identity
        or len(
            {
                final_identity["path"],
                epoch_identity["path"],
                pre_full_resource_identity["path"],
                pre_publication_resource_identity["path"],
                record["publisher"]["output_path"],
            }
        )
        != 5
        or record["schema_version"] != GATE_B_SCHEMA
        or record["purpose"] != GATE_B_PURPOSE
        or record["gate"] != "B"
        or record["decision"] != "APPROVED"
        or record["formal_campaign_creation_authorized"] is not True
        or record["arm_launch_authorized"] is not False
        or resource_budget_profile_identity["mode"] != 0o444
        or native_helper_source["mode"] != NATIVE_BUDGET_HELPER_MODE
        or native_helper_source["sha256"] != NATIVE_BUDGET_HELPER_SHA256
        or native_helper_source["size_bytes"] != NATIVE_BUDGET_HELPER_SIZE_BYTES
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
        or type(verifier_source["path"]) is not str
        or not Path(verifier_source["path"]).is_absolute()
        or type(verifier_source["sha256"]) is not str
        or SHA256_RE.fullmatch(verifier_source["sha256"]) is None
        or type(verifier_source["size_bytes"]) is not int
        or verifier_source["size_bytes"] <= 0
        or type(verifier_source["mode"]) is not int
        or verifier_source["mode_octal"] != f"{verifier_source['mode']:04o}"
        or type(verifier_source["device"]) is not int
        or type(verifier_source["inode"]) is not int
    ):
        raise BootstrapError("Gate-B approval does not authorize identity creation")
    return record


def _validate_closed_preflight_scratch(
    value: object,
    *,
    receipt_directory: Path,
    label: str,
) -> None:
    record = _exact_keys(
        value,
        {
            "basetemp_identity",
            "basetemp_path",
            "initial_identity",
            "path",
            "policy",
            "retention_policy",
            "status",
        },
        f"{label} pytest scratch",
    )
    identity = _exact_keys(
        record["initial_identity"],
        {"device", "inode", "mode", "uid"},
        f"{label} pytest scratch initial identity",
    )
    basetemp_identity = _exact_keys(
        record["basetemp_identity"],
        {"device", "inode", "mode", "uid"},
        f"{label} pytest basetemp identity",
    )
    if (
        any(type(identity[field]) is not int for field in identity)
        or any(type(basetemp_identity[field]) is not int for field in basetemp_identity)
        or identity["device"] < 0
        or identity["inode"] <= 0
        or identity["mode"] != 0o700
        or identity["uid"] != os.geteuid()
        or basetemp_identity["device"] < 0
        or basetemp_identity["inode"] <= 0
        or basetemp_identity["mode"] != 0o700
        or basetemp_identity["uid"] != os.geteuid()
        or record["path"] != str(receipt_directory / FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME)
        or record["basetemp_path"]
        != str(
            receipt_directory
            / FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME
            / FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME
        )
        or record["policy"] != FINAL_FULL_PREFLIGHT_SCRATCH_POLICY
        or record["retention_policy"] != "failed"
        or record["status"] != "CLOSED_EMPTY_BASETEMP_RETAINED_AFTER_PASS"
    ):
        raise BootstrapError(f"{label} pytest scratch is not an exact closed PASS")
    descriptor: int | None = None
    basetemp_descriptor: int | None = None
    try:
        _absolute_scratch, descriptor = _open_directory_fd(Path(record["path"]))
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or observed.st_dev != identity["device"]
            or observed.st_ino != identity["inode"]
            or stat.S_IMODE(observed.st_mode) != identity["mode"]
            or observed.st_uid != identity["uid"]
        ):
            raise BootstrapError(f"{label} pytest scratch identity drifted")
        with os.scandir(descriptor) as iterator:
            entries = list(iterator)
        if len(entries) != 1 or entries[0].name != FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME:
            raise BootstrapError(f"{label} pytest scratch tree drifted")
        named = entries[0].stat(follow_symlinks=False)
        if not stat.S_ISDIR(named.st_mode):
            raise BootstrapError(f"{label} pytest basetemp type drifted")
        basetemp_descriptor = os.open(
            FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=descriptor,
        )
        opened = os.fstat(basetemp_descriptor)
        if (
            (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_dev != basetemp_identity["device"]
            or opened.st_ino != basetemp_identity["inode"]
            or stat.S_IMODE(opened.st_mode) != basetemp_identity["mode"]
            or opened.st_uid != basetemp_identity["uid"]
        ):
            raise BootstrapError(f"{label} pytest basetemp identity drifted")
        with os.scandir(basetemp_descriptor) as iterator:
            if next(iterator, None) is not None:
                raise BootstrapError(f"{label} pytest basetemp is not empty")
    except BaseException as exc:
        for opened_descriptor in (basetemp_descriptor, descriptor):
            if opened_descriptor is None:
                continue
            try:
                os.close(opened_descriptor)
            except OSError as close_error:
                exc.add_note(
                    f"{label} pytest scratch cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise BootstrapError(f"{label} pytest scratch closure check failed") from exc
        raise
    close_error: OSError | None = None
    for opened_descriptor in (basetemp_descriptor, descriptor):
        try:
            os.close(opened_descriptor)
        except OSError as exc:
            if close_error is None:
                close_error = exc
    if close_error is not None:
        raise BootstrapError(f"{label} pytest scratch descriptor close failed") from close_error


def _validate_preflight_output_root(
    value: object,
    *,
    receipt_directory: Path,
    label: str,
) -> None:
    identity = _exact_keys(
        value,
        {"device", "inode", "mode", "uid"},
        f"{label} output-root identity",
    )
    if (
        any(type(identity[field]) is not int for field in identity)
        or identity["device"] < 0
        or identity["inode"] <= 0
        or identity["mode"] != 0o700
        or identity["uid"] != os.geteuid()
    ):
        raise BootstrapError(f"{label} output-root identity is malformed")
    descriptor: int | None = None
    try:
        _absolute_output, descriptor = _open_directory_fd(receipt_directory)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or observed.st_dev != identity["device"]
            or observed.st_ino != identity["inode"]
            or stat.S_IMODE(observed.st_mode) != identity["mode"]
            or observed.st_uid != identity["uid"]
        ):
            raise BootstrapError(f"{label} output-root identity drifted")
        with os.scandir(descriptor) as iterator:
            entries = {entry.name for entry in iterator}
        if entries != {
            FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME,
            "receipt.commit.json",
            "receipt.json",
            "stderr.log",
            "stdout.log",
        }:
            raise BootstrapError(f"{label} output-root member set drifted")
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    f"{label} output-root cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise BootstrapError(f"{label} output-root validation failed") from exc
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise BootstrapError(f"{label} output-root descriptor close failed") from exc


def _validate_preflight_publication_commit(
    *,
    receipt_identity: Mapping[str, object],
    output_root_identity: object,
    label: str,
) -> None:
    receipt_path = Path(str(receipt_identity["path"]))
    record, identity = _unterminated_canonical_mode_record(
        receipt_path.parent / "receipt.commit.json",
        f"{label} publication commit",
    )
    commit = _exact_keys(
        record,
        {
            "output_root_identity",
            "receipt_identity",
            "schema_version",
            "status",
        },
        f"{label} publication commit",
    )
    if (
        identity["mode"] != 0o444
        or commit["schema_version"] != FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA
        or commit["status"] != "COMMITTED"
        or commit["receipt_identity"] != receipt_identity
        or commit["output_root_identity"] != output_root_identity
    ):
        raise BootstrapError(f"{label} publication commit is invalid")


def _validate_preflight_collection_projection(
    value: object,
    *,
    label: str,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "collection_count",
            "collection_sha256",
            "manifest_sha256",
            "markexpr",
            "schema_version",
            "stage_module_origin_count",
            "stage_sha256",
            "terminal_module_origin_count",
            "terminal_sha256",
            "workflow",
        },
        f"{label} pytest collection projection",
    )
    if (
        type(record["collection_count"]) is not int
        or record["collection_count"] <= 0
        or type(record["stage_module_origin_count"]) is not int
        or record["stage_module_origin_count"] < 0
        or type(record["terminal_module_origin_count"]) is not int
        or record["terminal_module_origin_count"] < 0
        or any(
            type(record[field]) is not str
            or SHA256_RE.fullmatch(record[field]) is None
            for field in (
                "collection_sha256",
                "manifest_sha256",
                "stage_sha256",
                "terminal_sha256",
            )
        )
        or record["markexpr"] != "not slow"
        or record["schema_version"]
        != "noncert-cuts-ab16-pytest-collection-binding-v1"
        or record["workflow"] != "full"
    ):
        raise BootstrapError(f"{label} pytest collection projection is malformed")
    return record


def _expected_preflight_qualification_argv(
    record: Mapping[str, Any],
    *,
    python: Mapping[str, object],
    qualification: Mapping[str, object],
    preflight: Mapping[str, object],
    protocol: Mapping[str, object],
    plugin: Mapping[str, object],
    label: str,
) -> list[object]:
    collection = _validate_preflight_collection_projection(
        record["pytest_collection"],
        label=label,
    )
    repository = Path(record["repository_root"])
    scratch = _exact_keys(
        record["pytest_scratch"],
        {
            "basetemp_identity",
            "basetemp_path",
            "initial_identity",
            "path",
            "policy",
            "retention_policy",
            "status",
        },
        f"{label} pytest scratch",
    )
    basetemp = Path(scratch["basetemp_path"])
    try:
        basetemp_relative = basetemp.relative_to(repository)
    except ValueError as exc:
        raise BootstrapError(f"{label} basetemp is outside its repository") from exc
    return [
        python["path"],
        "-I",
        "-B",
        qualification["path"],
        "--repository-root",
        str(repository),
        "--basetemp",
        str(basetemp),
        "--basetemp-relative",
        basetemp_relative.as_posix(),
        "--expected-count",
        str(collection["collection_count"]),
        "--expected-sha256",
        collection["collection_sha256"],
        "--preflight-source",
        preflight["path"],
        "--collection-protocol-source",
        protocol["path"],
        "--collection-plugin-source",
        plugin["path"],
        "--full",
    ]


def _load_resource_admission_replayer(
    expected_source: Mapping[str, object],
    *,
    label: str,
) -> tuple[types.ModuleType, str | None]:
    ambient = sys.modules.get("ab16_resource_admission_v1")
    if ambient is not None:
        module_path = getattr(ambient, "__file__", None)
        if (
            not isinstance(ambient, types.ModuleType)
            or type(module_path) is not str
            or _snapshot_mode_identity(module_path) != expected_source
        ):
            raise BootstrapError(
                f"{label} pinned resource-admission alias identity drifted"
            )
        return ambient, None
    if not _is_live_prepackage_closure_entry():
        raise BootstrapError(
            f"{label} lacks a pinned resource-admission replay module"
        )
    snapshot = authority.snapshot_regular(expected_source["path"])
    observed = {
        "mode": stat.S_IMODE(snapshot.stat_result.st_mode),
        **authority.detached_identity(snapshot),
    }
    if observed != dict(expected_source):
        raise BootstrapError(
            f"{label} live resource-admission source identity drifted"
        )
    module_name = (
        "_ab16_bootstrap_resource_admission_replay_"
        f"{expected_source['sha256']}"
    )
    if module_name in sys.modules:
        raise BootstrapError(
            f"{label} resource-admission replay module name is occupied"
        )
    module = types.ModuleType(module_name)
    module.__file__ = str(expected_source["path"])
    module.__package__ = None
    module.__cached__ = None
    sys.modules[module_name] = module
    try:
        exec(
            compile(
                snapshot.data,
                module.__file__,
                "exec",
                dont_inherit=True,
            ),
            module.__dict__,
            module.__dict__,
        )
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module, module_name


def _validate_preflight_resource_admission(
    record: Mapping[str, Any],
    *,
    planned: Mapping[str, Mapping[str, object]],
    receipt_directory: Path,
    label: str,
) -> None:
    try:
        expected_source = _project_mode_identity(
            planned["script.ab16_resource_admission_v1"],
            "AB16 resource admission",
        )
    except KeyError as exc:
        raise BootstrapError(
            f"{label} lacks the planned resource-admission source"
        ) from exc
    if record["resource_admission_source_identity"] != expected_source:
        raise BootstrapError(f"{label} resource-admission source identity drifted")
    resource_replayer, cleanup_module_name = _load_resource_admission_replayer(
        expected_source,
        label=label,
    )

    resource_record = record["resource_admission"]
    if type(resource_record) is not dict:
        raise BootstrapError(f"{label} resource admission is malformed")
    lock_check = resource_record.get("lock_check")
    if type(lock_check) is not dict:
        raise BootstrapError(f"{label} resource lock check is malformed")
    lock_identities = lock_check.get("identities")
    expected_observation_context = {
        "authority_id": record["pre_run_authority_identity"]["sha256"],
        "disk_path": record["repository_root"],
        "kind": "GATE_A_FULL_PREFLIGHT",
        "ordinal": 0,
        "scope_id": record["planned_source_set_digest"],
        "sequence": 1,
        "slot": "",
        "target": str(receipt_directory),
    }
    try:
        try:
            checked_resource = resource_replayer.validate_resource_admission_receipt(
                resource_record,
                expected_stage=resource_replayer.FULL_PREFLIGHT,
                expected_lock_identities=lock_identities,
                expected_lock_identity_format=resource_replayer.GATE_B_LOCK_IDENTITY_FORMAT,
                expected_observation_context=expected_observation_context,
            )
        except resource_replayer.ResourceAdmissionError as exc:
            raise BootstrapError(
                f"{label} resource admission replay failed: {exc}"
            ) from exc
    finally:
        if cleanup_module_name is not None:
            loaded = sys.modules.get(cleanup_module_name)
            if loaded is resource_replayer:
                sys.modules.pop(cleanup_module_name, None)
    if (
        checked_resource != resource_record
        or record["resource_lock_release_identities"] != lock_identities
    ):
        raise BootstrapError(f"{label} resource admission/release join drifted")

    disk_target = resource_record["disk_target"]
    if type(disk_target) is not dict:
        raise BootstrapError(f"{label} resource disk target is malformed")
    descriptor: int | None = None
    try:
        _repository, descriptor = _open_directory_fd(Path(record["repository_root"]))
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or disk_target
            != {
                "device": observed.st_dev,
                "inode": observed.st_ino,
                "mode": stat.S_IMODE(observed.st_mode),
                "path": record["repository_root"],
                "type": "directory",
                "uid": observed.st_uid,
            }
        ):
            raise BootstrapError(f"{label} resource disk target identity drifted")
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    f"{label} resource disk-target cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise BootstrapError(
                f"{label} resource disk-target replay failed"
            ) from exc
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise BootstrapError(
            f"{label} resource disk-target descriptor close failed"
        ) from exc


def _read_gate_b_resource_gate(
    identity_value: object,
    *,
    planned: Mapping[str, Mapping[str, object]],
    calibration_authorization_bundle: Mapping[str, object],
    calibration_authorization_bundle_identity: Mapping[str, object],
    expected_actor: Mapping[str, object],
    expected_session_id: str,
    expected_lock_identities: Sequence[Mapping[str, object]],
    expected_path: Path,
    expected_profile_stage: str,
    expected_stage: str,
    expected_disk_path: Path,
    expected_kind: str,
    expected_sequence: int,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    label = f"Gate-B {expected_stage} resource gate"
    identity = _mode_identity(identity_value, label)
    if identity["mode"] != 0o444 or identity["path"] != str(expected_path):
        raise BootstrapError(f"{label} fixed path or mode drifted")
    record, observed_identity = _canonical_mode_record(expected_path, label)
    if observed_identity != identity:
        raise BootstrapError(f"{label} byte identity drifted")
    checked = _exact_keys(
        record,
        {
            "admission",
            "authorizations",
            "created_at_utc",
            "lock_identities",
            "owner_actor",
            "qualification_session_id",
            "schema_version",
            "stage",
            "status",
        },
        label,
    )
    _utc(checked["created_at_utc"], f"{label} created_at_utc")
    if (
        checked["schema_version"] != GATE_B_RESOURCE_GATE_SCHEMA
        or checked["status"] != "PASS"
        or checked["stage"] != expected_stage
        or checked["authorizations"]
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        }
        or checked["owner_actor"] != dict(expected_actor)
        or checked["qualification_session_id"] != expected_session_id
        or checked["lock_identities"]
        != [dict(item) for item in expected_lock_identities]
    ):
        raise BootstrapError(f"{label} owner/session/lock binding drifted")

    try:
        expected_source = _project_mode_identity(
            planned["script.ab16_resource_admission_v1"],
            "AB16 resource admission",
        )
    except KeyError as exc:
        raise BootstrapError(f"{label} lacks its planned validator source") from exc
    resource_replayer, cleanup_module_name = _load_resource_admission_replayer(
        expected_source,
        label=label,
    )
    expected_context = {
        "authority_id": expected_session_id,
        "disk_path": str(expected_disk_path),
        "kind": expected_kind,
        "ordinal": 0,
        "scope_id": expected_session_id,
        "sequence": expected_sequence,
        "slot": "",
        "target": expected_stage,
    }
    try:
        try:
            replayed = (
                resource_replayer.validate_prospective_resource_admission_receipt(
                checked["admission"],
                expected_stage=expected_profile_stage,
                expected_lock_identities=expected_lock_identities,
                expected_lock_identity_format=resource_replayer.GATE_B_LOCK_IDENTITY_FORMAT,
                expected_observation_context=expected_context,
                calibration_authorization_bundle=(
                    calibration_authorization_bundle
                ),
                calibration_authorization_bundle_identity=(
                    calibration_authorization_bundle_identity
                ),
                expected_calibration_tool_identities=(
                    _calibration_tool_content_identities(planned)
                ),
                enforced_budget_profile=None,
                enforced_budget_profile_identity=None,
            )
            )
        except resource_replayer.ResourceAdmissionError as exc:
            raise BootstrapError(f"{label} admission replay failed: {exc}") from exc
    finally:
        if cleanup_module_name is not None:
            loaded = sys.modules.get(cleanup_module_name)
            if loaded is resource_replayer:
                sys.modules.pop(cleanup_module_name, None)
    if replayed != checked["admission"]:
        raise BootstrapError(f"{label} admission canonical replay drifted")

    disk_target = replayed["disk_target"]
    descriptor: int | None = None
    try:
        _absolute_disk_path, descriptor = _open_directory_fd(expected_disk_path)
        observed = os.fstat(descriptor)
        if disk_target != {
            "device": observed.st_dev,
            "inode": observed.st_ino,
            "mode": stat.S_IMODE(observed.st_mode),
            "path": str(expected_disk_path),
            "type": "directory",
            "uid": observed.st_uid,
        }:
            raise BootstrapError(f"{label} disk target identity drifted")
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    f"{label} disk-target cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise BootstrapError(f"{label} disk-target replay failed") from exc
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise BootstrapError(
            f"{label} disk-target descriptor close failed"
        ) from exc
    return checked, observed_identity


def _validate_final_full_preflight(
    value: object,
    *,
    gate_a: Mapping[str, Any],
    planned: Mapping[str, Mapping[str, object]],
    receipt_identity: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _exact_keys(value, FINAL_FULL_PREFLIGHT_KEYS, "Gate-B final full-preflight receipt")
    _utc(record["started_at_utc"], "Gate-B final full-preflight started_at_utc")
    _utc(record["finished_at_utc"], "Gate-B final full-preflight finished_at_utc")
    for field in (
        "authority_ready_identity",
        "detached_replay_identity",
        "pre_run_authority_identity",
        "qualification_runner_identity",
        "preflight_script_identity",
        "pytest_collection_plugin_identity",
        "pytest_collection_protocol_identity",
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
    expected_qualification = _project_mode_identity(
        planned["script.ab16_preflight_qualification_v1"],
        "AB16 preflight qualification runner",
    )
    expected_protocol = _project_mode_identity(
        planned["script.ab16_pytest_collection_protocol_v1"],
        "AB16 pytest collection protocol",
    )
    expected_plugin = _project_mode_identity(
        planned["script.ab16_pytest_collection_plugin_v1"],
        "AB16 pytest collection plugin",
    )
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
        or gate_a_preflight["preflight_script_identity"] != expected_preflight
        or gate_a_preflight["qualification_runner_identity"] != expected_qualification
        or gate_a_preflight["pytest_collection_protocol_identity"] != expected_protocol
        or gate_a_preflight["pytest_collection_plugin_identity"] != expected_plugin
        or gate_a_preflight["python_identity"] != expected_python
        or gate_a_preflight["runner_tool_identity"] != expected_runner
        or gate_a_command["execution_strategy"] != FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY
        or gate_a_command["argv"]
        != _expected_preflight_qualification_argv(
            gate_a_preflight,
            python=expected_python,
            qualification=expected_qualification,
            preflight=expected_preflight,
            protocol=expected_protocol,
            plugin=expected_plugin,
            label="Gate-A full-preflight receipt",
        )
        or loader != gate_a_loader
    ):
        raise BootstrapError("Gate-A full-preflight receipt no longer joins Gate A")
    gate_a_receipt_directory = Path(gate_a["full_preflight_receipt_identity"]["path"]).parent
    _validate_preflight_publication_commit(
        receipt_identity=gate_a["full_preflight_receipt_identity"],
        output_root_identity=gate_a_preflight["output_root_identity"],
        label="Gate-A full-preflight receipt",
    )
    _validate_preflight_output_root(
        gate_a_preflight["output_root_identity"],
        receipt_directory=gate_a_receipt_directory,
        label="Gate-A full-preflight receipt",
    )
    _validate_closed_preflight_scratch(
        gate_a_preflight["pytest_scratch"],
        receipt_directory=gate_a_receipt_directory,
        label="Gate-A full-preflight receipt",
    )
    _validate_preflight_resource_admission(
        gate_a_preflight,
        planned=planned,
        receipt_directory=gate_a_receipt_directory,
        label="Gate-A full-preflight receipt",
    )
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
        or record["qualification_runner_identity"] != expected_qualification
        or record["pytest_collection_protocol_identity"] != expected_protocol
        or record["pytest_collection_plugin_identity"] != expected_plugin
        or record["python_identity"] != expected_python
        or record["runner_tool_identity"] != expected_runner
        or command["execution_strategy"] != FINAL_FULL_PREFLIGHT_EXECUTION_STRATEGY
        or command["argv"]
        != _expected_preflight_qualification_argv(
            record,
            python=expected_python,
            qualification=expected_qualification,
            preflight=expected_preflight,
            protocol=expected_protocol,
            plugin=expected_plugin,
            label="Gate-B final full-preflight receipt",
        )
    ):
        raise BootstrapError("Gate-B final full-preflight is not one exact current-HEAD PASS")
    final_receipt_directory = Path(receipt_identity["path"]).parent
    _validate_preflight_publication_commit(
        receipt_identity=receipt_identity,
        output_root_identity=record["output_root_identity"],
        label="Gate-B final full-preflight receipt",
    )
    _validate_preflight_output_root(
        record["output_root_identity"],
        receipt_directory=final_receipt_directory,
        label="Gate-B final full-preflight receipt",
    )
    _validate_closed_preflight_scratch(
        record["pytest_scratch"],
        receipt_directory=final_receipt_directory,
        label="Gate-B final full-preflight receipt",
    )
    _validate_preflight_resource_admission(
        record,
        planned=planned,
        receipt_directory=final_receipt_directory,
        label="Gate-B final full-preflight receipt",
    )
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
    pre_full_resource_gate_identity: Mapping[str, object],
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
            "pre_full_resource_gate_identity",
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
        or record["pre_full_resource_gate_identity"]
        != pre_full_resource_gate_identity
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
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            next_descriptor = os.open(
                component,
                flags,
                dir_fd=descriptor,
            )
            try:
                os.close(descriptor)
            except BaseException as exc:
                try:
                    os.close(next_descriptor)
                except OSError as close_error:
                    exc.add_note(
                        "directory-chain cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
                raise
            descriptor = next_descriptor
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "directory-chain cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise BootstrapError("directory path is invalid or symlinked") from exc
        raise
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
    approved_observation: Mapping[str, object],
    system_paths: Mapping[str, Path],
) -> dict[str, object]:
    """Rejoin the already qualified epoch without another project executor."""

    observation = _exact_keys(
        approved_observation,
        {
            "authorizations",
            "candidate_identity",
            "capture_transcript",
            "created_at_utc",
            "final_full_preflight_receipt_identity",
            "gate_a_receipt_identity",
            "manager_epoch",
            "planned_source_set_digest",
            "pre_full_resource_gate_identity",
            "publisher",
            "purpose",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "status",
            "target_campaign_dir",
        },
        "approved Gate-B epoch observation",
    )
    epoch = authority.validate_manager_epoch(observation["manager_epoch"])
    authority.validate_manager_epoch_capture_transcript(
        observation["capture_transcript"],
        expected_epoch=epoch,
    )
    boot_fd = os.open(
        "/proc/sys/kernel/random/boot_id",
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        boot_raw = _read_stable_fd(
            boot_fd,
            limit=128,
            label="current kernel boot_id",
        )
    finally:
        os.close(boot_fd)
    try:
        current_boot = boot_raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise BootstrapError("current boot_id is not ASCII") from exc
    pid = int(epoch["manager_pid"])
    if (
        current_boot != epoch["boot_id"]
        or _proc_starttime(pid) != epoch["manager_pid_starttime"]
    ):
        raise BootstrapError(
            "current manager/boot identity differs from Gate-B observation"
        )
    busctl = system_paths["busctl"]
    completed = subprocess.run(
        [
            str(busctl),
            "--user",
            "--json=short",
            "call",
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetNameOwner",
            "s",
            "org.freedesktop.systemd1",
        ],
        check=False,
        close_fds=True,
        env={
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin",
            "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if (
        completed.returncode != 0
        or completed.stderr
        or not completed.stdout
        or len(completed.stdout) > 1 << 20
    ):
        raise BootstrapError("current D-Bus manager owner query failed")
    owner_reply = _exact_keys(
        authority.strict_loads(
            completed.stdout,
            "current D-Bus manager owner",
        ),
        {"data", "type"},
        "current D-Bus manager owner",
    )
    if (
        owner_reply["type"] != "s"
        or not isinstance(owner_reply["data"], list)
        or owner_reply["data"] != [epoch["dbus_unique_owner"]]
    ):
        raise BootstrapError(
            "current D-Bus manager owner differs from Gate-B observation"
        )
    return {
        "manager_epoch": dict(epoch),
        "transcript": dict(observation["capture_transcript"]),
    }


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


def _selected_byte_launch_contract(
    external_platform_schema: str,
) -> dict[str, object]:
    """Return exactly one selected-FD cohort without cross-version fallback."""

    if external_platform_schema == HISTORICAL_EXTERNAL_PLATFORM_SCHEMA:
        return {
            "direct_fd_map": {
                "authority": 5,
                "loader": 4,
                "python": 3,
            },
            "execution_strategy": SELECTED_BYTE_EXECUTION_STRATEGY_V1,
            "literal_identity": _literal_identity(
                SELECTED_BYTE_LAUNCH_V1
            ),
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
    if external_platform_schema == EXTERNAL_PLATFORM_SCHEMA:
        return {
            "direct_fd_map": {
                "authority": 5,
                "budget_broker": 8,
                "loader": 4,
                "native_helper": 7,
                "native_helper_wrapper": 6,
                "python": 3,
            },
            "execution_strategy": SELECTED_BYTE_EXECUTION_STRATEGY_V2,
            "literal_identity": _literal_identity(
                SELECTED_BYTE_LAUNCH_V2
            ),
            "systemd_fd_map": {
                "authority": 5,
                "budget_broker": 8,
                "loader": 4,
                "native_helper": 7,
                "native_helper_wrapper": 6,
                "python": 3,
            },
            "systemd_fd_names": [
                "ab16-python",
                "ab16-loader",
                "ab16-authority",
                "ab16-native-helper-wrapper",
                "ab16-native-helper",
                "ab16-budget-broker",
            ],
        }
    raise BootstrapError(
        "selected-byte launch external-platform version is unsupported"
    )


def _validate_selected_byte_launch_contract(
    external_platform_schema: str,
    record: Mapping[str, object],
) -> None:
    expected = _selected_byte_launch_contract(external_platform_schema)
    if type(record) is not dict or dict(record) != expected:
        raise BootstrapError(
            "selected-byte launch cohort or version is mixed"
        )


def _external_platform_record(
    *,
    repository_head: str,
    native_helper_identity: Mapping[str, object],
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
        "formal_launch_owner_driver": _literal_identity(FORMAL_LAUNCH_OWNER_DRIVER_V2),
        "gate_b_owner_driver": _literal_identity(GATE_B_OWNER_DRIVER_V1),
        "mechanical_oexcl_publisher": _literal_identity(OWNER_OEXCL_PUBLISH_V1),
        "native_budget_helper": _native_helper_capability_from_full(
            native_helper_identity
        ),
        "ortools_version": importlib.metadata.version("ortools"),
        "protobuf_version": importlib.metadata.version("protobuf"),
        "python_identity": {
            key: python_identity[key] for key in ("mode", "path", "sha256", "size_bytes")
        },
        "repository_head": repository_head,
        "schema_version": EXTERNAL_PLATFORM_SCHEMA,
        "selected_byte_launch": _selected_byte_launch_contract(
            EXTERNAL_PLATFORM_SCHEMA
        ),
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
    writer: Any | None = None,
) -> dict[str, object]:
    publication = authority if writer is None else writer
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
    snapshot_sources = publication.mkdir_exclusive(bootstrap_dir / "repository-snapshot-sources")
    archive_path = snapshot_sources / "repository-snapshot.zip"
    manifest_path = snapshot_sources / "repository-snapshot.json"
    platform_path = snapshot_sources / "external-platform-assumptions.json"
    publication.write_exclusive(archive_path, archive_raw, mode=0o444)
    publication.write_exclusive(manifest_path, authority.canonical_json(manifest), mode=0o444)
    publication.write_exclusive(
        platform_path,
        authority.canonical_json(
            _external_platform_record(
                repository_head=repository_head,
                native_helper_identity=system_full["native_budget_helper"],
                python_identity=system_full["python3_13"],
            )
        ),
        mode=0o444,
    )

    staged_dir = publication.mkdir_exclusive(bootstrap_dir / "package-source-staging")
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
        publication.write_exclusive(staged_scripts[role], raw, mode=0o444)
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
        publication.write_exclusive(staged_inputs[role], raw, mode=0o444)
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
    writer: Any | None = None,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    publication = authority if writer is None else writer
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
    root = publication.mkdir_exclusive(campaign_dir / "campaign-authority" / "source-snapshot-a001")
    repository = publication.mkdir_exclusive(root / "repository")
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
        publication.mkdir_exclusive(repository / relative)
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
            publication.write_exclusive(destination, raw, mode=int(member["materialized_mode"]))
    overlay = expected.get("data/preprocessed/candidate_placements.json")
    if (
        not isinstance(overlay, Mapping)
        or overlay.get("source_kind") != "package_overlay"
        or overlay.get("raw_sha256") != candidate_snapshot.sha256
        or overlay.get("size_bytes") != candidate_snapshot.size
    ):
        raise BootstrapError("candidate overlay binding drifted")
    overlay_path = repository / "data/preprocessed/candidate_placements.json"
    publication.write_exclusive(overlay_path, candidate_snapshot.data, mode=0o444)
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
    receipt_identity = publication.write_exclusive(
        root / "materialization-receipt.json",
        authority.canonical_json(receipt),
        mode=0o444,
    )
    return {"receipt": receipt, "receipt_identity": receipt_identity}, identities


def _path_preregistration(
    campaign_dir: Path | str,
    *,
    budget_binding: Mapping[str, object],
) -> dict[str, object]:
    """Build the deterministic AB16 child-path registry without writing it."""

    campaign = _absolute(campaign_dir)
    formal = campaign / "formal-ab16"
    formal_artifacts = formal / "artifacts"
    prospective = formal_artifacts / "prospective"
    baseline = prospective / "baseline"
    formal_attempt = formal_artifacts / "formal-attempt-a001"
    package_payload = campaign / "campaign-authority" / "package" / "payload"
    snapshot_authority = campaign / "campaign-authority" / "source-snapshot-a001"
    slots = tuple(
        f"{configuration}-{order}-{arm}"
        for configuration in authority.AB16_CONFIGURATIONS
        for order in authority.AB16_ORDERS
        for arm in authority.AB16_ARMS
    )
    attempt_dirs = {slot: str(prospective / "arms" / slot) for slot in slots}
    binding = _exact_keys(
        budget_binding,
        {
            "bootstrap_budget_contract_identity",
            "formal_root_budget_contract_identity",
            "resource_calibration_bundle_identities",
            "resource_budget_profile_identity",
        },
        "AB16 path preregistration budget binding",
    )
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
        "baseline_checkpoint_dir": str(baseline / "checkpoint"),
        "baseline_fixed_replay_path": str(baseline / "fixed-replay-a001.json"),
        "baseline_incumbent_path": str(baseline / "incumbent.json"),
        "baseline_rebuild_result_path": str(baseline / "rebuild-result.json"),
        "baseline_rebuilt_metadata_path": str(baseline / "rebuilt-model-metadata.json"),
        "baseline_rebuilt_model_path": str(baseline / "cut-free-model.bin"),
        "baseline_tmp_dir": str(baseline / "tmp"),
        "binding_paths": {slot: str(prospective / "bindings" / f"{slot}.json") for slot in slots},
        "campaign_dir": str(campaign),
        "bootstrap_budget_contract_identity": dict(
            binding["bootstrap_budget_contract_identity"]
        ),
        "bootstrap_budget_contract_path": str(
            campaign
            / "bootstrap-authority"
            / "bootstrap-budget-contract.json"
        ),
        "bootstrap_budget_terminal_path": str(
            campaign
            / "bootstrap-authority"
            / "bootstrap-budget-terminal.json"
        ),
        "bootstrap_package_failure_closeout_path": str(
            campaign
            / "bootstrap-authority"
            / "bootstrap-package-failure-closeout.json"
        ),
        "budget_broker_control_socket_path": str(
            formal / "control" / "budget-broker.sock"
        ),
        "budget_broker_retired_socket_path": str(
            formal / "control" / "budget-broker.sock.retired"
        ),
        "classification_contract_path": str(package_payload / "tool.ab16_contract_v1.py"),
        "common_prestate_path": str(
            prospective / "common" / "common-prestate-a001.json"
        ),
        "child_audit_path": str(formal_attempt / "child-audit.json"),
        "cut_free_replay_paths": {
            slot: str(Path(attempt_dirs[slot]) / "replays/cut-free-incumbent.json") for slot in slots
        },
        "formal_admission_path": str(
            formal_artifacts / "formal-launch-admission-a001.json"
        ),
        "formal_artifact_root": str(formal_artifacts),
        "formal_attempt_dir": str(formal_attempt),
        "formal_budget_terminal_path": str(
            formal_artifacts / "formal-closure" / "budget-terminal.json"
        ),
        "formal_root_budget_contract_identity": dict(
            binding["formal_root_budget_contract_identity"]
        ),
        "resource_calibration_bundle_identities": {
            stage: dict(identity)
            for stage, identity in sorted(
                _validate_resource_calibration_bundle_identities(
                    binding["resource_calibration_bundle_identities"],
                    label=(
                        "AB16 path preregistration resource calibration "
                        "bundles"
                    ),
                ).items()
            )
        },
        "formal_root_budget_contract_path": str(
            formal_artifacts / "formal-root-budget-contract.json"
        ),
        "formal_root_budget_handoff_path": str(
            formal_artifacts / "formal-root-budget-handoff.json"
        ),
        "formal_closure_manifest_path": str(
            formal_artifacts / "formal-closure" / "formal-manifest.json"
        ),
        "formal_consumed_incomplete_path": str(
            formal_artifacts / "closeout" / "formal-consumed-incomplete.json"
        ),
        "formal_failure_terminal_release_path": str(
            formal_artifacts / "failure-terminal-release.json"
        ),
        "formal_closure_consumption_path": str(
            formal_artifacts / "locks/formal-closure-consumption.json"
        ),
        "formal_recovery_disarm_terminal_path": str(
            formal_artifacts
            / "formal-closure"
            / "recovery-disarm-terminal.json"
        ),
        "formal_recovery_takeover_consumption_path": str(
            formal_artifacts / "locks/recovery-takeover-consumption.json"
        ),
        "formal_selection_path": str(formal_attempt / "selection.json"),
        "gate1_prelaunch_ownership_path": str(formal_attempt / "gate1-prelaunch-ownership.json"),
        "guardian_control_socket_path": str(
            formal / "control" / "guardian-control.sock"
        ),
        "guardian_control_retired_socket_path": str(
            formal / "control" / "guardian-control.sock.retired"
        ),
        "guardian_ready_path": str(
            formal_artifacts / "outer-guardian-ready-a001.json"
        ),
        "immediate_stop_path": str(prospective / "immediate-stop-a001.json"),
        "manifest_path": str(prospective / "manifest-a001.json"),
        "launch_environment_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-launch-environment.json") for slot in slots
        },
        "outer_barrier_path": str(formal_attempt / "outer-barrier-release.json"),
        "package_independent_replay_path": str(
            campaign / "bootstrap-authority" / "package-independent-replay.json"
        ),
        "package_independent_replay_staging_path": str(
            campaign
            / "bootstrap-authority"
            / ".package-independent-replay.json.staged"
        ),
        "outer_receipt_paths": {
            "detached_closeout": str(formal_attempt / "detached-closeout.json"),
            "detached_incomplete_closeout": str(
                formal_attempt / "detached-incomplete-closeout.json"
            ),
            "dual_lock_release": str(
                formal_artifacts / "dual-lock-release.json"
            ),
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
            "reference_connection_close": str(
                formal_attempt / "reference-connection-close.json"
            ),
            "reference_release": str(formal_attempt / "reference-release.json"),
            "reference_terminal": str(
                formal_attempt / "reference-terminal.json"
            ),
            "supervisor_raw_lock_release": str(
                formal_attempt / "supervisor-raw-lock-release.json"
            ),
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
        "resource_budget_profile_identity": dict(
            binding["resource_budget_profile_identity"]
        ),
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
    budget_binding: Mapping[str, object],
) -> Mapping[str, Any]:
    """Reject any path registry that differs from the fixed v4 child topology."""

    expected = _path_preregistration(
        campaign_dir,
        budget_binding=budget_binding,
    )
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
        "baseline_checkpoint_dir",
        "baseline_fixed_replay_path",
        "baseline_incumbent_path",
        "baseline_rebuild_result_path",
        "baseline_rebuilt_metadata_path",
        "baseline_rebuilt_model_path",
        "baseline_tmp_dir",
        "bootstrap_budget_contract_path",
        "bootstrap_budget_terminal_path",
        "bootstrap_package_failure_closeout_path",
        "budget_broker_control_socket_path",
        "budget_broker_retired_socket_path",
        "classification_contract_path",
        "child_audit_path",
        "common_prestate_path",
        "formal_admission_path",
        "formal_artifact_root",
        "formal_attempt_dir",
        "formal_budget_terminal_path",
        "formal_root_budget_contract_path",
        "formal_root_budget_handoff_path",
        "formal_closure_manifest_path",
        "formal_consumed_incomplete_path",
        "formal_failure_terminal_release_path",
        "formal_closure_consumption_path",
        "formal_recovery_disarm_terminal_path",
        "formal_recovery_takeover_consumption_path",
        "formal_selection_path",
        "gate1_prelaunch_ownership_path",
        "guardian_control_socket_path",
        "guardian_control_retired_socket_path",
        "guardian_ready_path",
        "immediate_stop_path",
        "manifest_path",
        "outer_barrier_path",
        "package_independent_replay_path",
        "package_independent_replay_staging_path",
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
    budget_binding: Mapping[str, object],
) -> None:
    """Join the package-pinned registry to the unchanged v4 campaign root."""

    record = validate_path_preregistration(
        value,
        campaign_dir=campaign_dir,
        budget_binding=budget_binding,
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
    resource_budget_profile: Path | str,
    resource_calibration_bundle_paths: Mapping[str, Path | str],
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
    budget_profile, budget_profile_identity = _resource_budget_profile(
        resource_budget_profile,
        require_launch_ready=True,
    )
    (
        _resource_calibration_paths,
        resource_calibration_bundle_identities,
    ) = _resource_calibration_bundle_sources(
        resource_calibration_bundle_paths
    )
    budget_contracts = _planned_budget_contracts(
        campaign_dir=campaign_dir,
        profile=budget_profile,
        profile_identity=budget_profile_identity,
    )
    budget_binding = {
        "bootstrap_budget_contract_identity": budget_contracts[
            "bootstrap_identity"
        ],
        "formal_root_budget_contract_identity": budget_contracts[
            "formal_identity"
        ],
        "resource_calibration_bundle_identities": (
            resource_calibration_bundle_identities
        ),
        "resource_budget_profile_identity": budget_profile_identity,
    }
    preregistration = _path_preregistration(
        campaign_dir,
        budget_binding=budget_binding,
    )
    validate_path_preregistration(
        preregistration,
        campaign_dir=campaign_dir,
        budget_binding=budget_binding,
    )
    preregistration_identity = authority.write_exclusive(
        preregistration_output,
        authority.canonical_json(preregistration),
    )
    candidate: dict[str, object] = {
        "arm_launch_authorized": False,
        "bootstrap_budget_contract_identity": budget_contracts[
            "bootstrap_identity"
        ],
        "candidate_id": "",
        "candidate_only": True,
        "created_at_utc": timestamp,
        "formal_campaign_creation_authorized": False,
        "formal_root_budget_contract_identity": budget_contracts[
            "formal_identity"
        ],
        "gate_a_receipt_identity": gate_a_identity,
        "native_budget_helper_source_identity": dict(
            planned["system.native_budget_helper"]
        ),
        "package_verifier_source_identity": dict(
            planned["script.package_independent_verifier_v1"]
        ),
        "path_preregistration_identity": preregistration_identity,
        "planned_source_identities": planned,
        "planned_source_set_digest": digest,
        "purpose": CANDIDATE_PURPOSE,
        "resource_calibration_bundle_identities": {
            stage: dict(identity)
            for stage, identity in sorted(
                resource_calibration_bundle_identities.items()
            )
        },
        "repository_head": observed_head,
        "repository_root": str(repository),
        "resource_budget_profile_identity": budget_profile_identity,
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
    pre_full_resource_gate_path: Path,
    pre_publication_resource_gate_path: Path,
    capture_path: Path,
    path_preregistration_path: Path,
    snapshot_archive_path: Path,
    snapshot_manifest_path: Path,
    external_platform_path: Path,
    resource_budget_profile_path: Path,
    resource_calibration_bundle_paths: Mapping[str, Path],
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
    for stage in RESOURCE_CALIBRATION_STAGES:
        input_role = RESOURCE_CALIBRATION_INPUT_ROLES[stage]
        package_role = f"input.{input_role}.json"
        input_roles[input_role] = package_role
        specs.append(
            authority.SourceSpec(
                package_role,
                resource_calibration_bundle_paths[stage],
                parse_json=True,
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
        (
            "ab16_gate_b_pre_full_resource_gate",
            GATE_INPUT_ROLES["ab16_gate_b_pre_full_resource_gate"],
            pre_full_resource_gate_path,
        ),
        (
            "ab16_gate_b_pre_publication_resource_gate",
            GATE_INPUT_ROLES["ab16_gate_b_pre_publication_resource_gate"],
            pre_publication_resource_gate_path,
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
    input_roles[RESOURCE_BUDGET_PROFILE_INPUT_ROLE] = (
        RESOURCE_BUDGET_PROFILE_PACKAGE_ROLE
    )
    specs.append(
        authority.SourceSpec(
            RESOURCE_BUDGET_PROFILE_PACKAGE_ROLE,
            resource_budget_profile_path,
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
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("schema") != PACKAGE_MANIFEST_SCHEMA
        or not isinstance(manifest.get("external_sources"), list)
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


def _read_exact_fd(
    descriptor: int,
    size_bytes: int,
    *,
    label: str,
) -> bytes:
    if type(size_bytes) is not int or size_bytes < 0:
        raise BootstrapError(f"{label} size is invalid")
    raw = bytearray()
    offset = 0
    while offset < size_bytes:
        try:
            block = os.pread(
                descriptor,
                min(1024 * 1024, size_bytes - offset),
                offset,
            )
        except OSError as exc:
            raise BootstrapError(f"{label} retained-FD read failed") from exc
        if not block:
            raise BootstrapError(f"{label} retained-FD read was short")
        raw.extend(block)
        offset += len(block)
    return bytes(raw)


def _close_descriptors_with_primary(
    descriptors: Sequence[int],
    *,
    primary: BaseException | None,
) -> None:
    close_errors: list[OSError] = []
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except OSError as exc:
            close_errors.append(exc)
    if not close_errors:
        return
    detail = "; ".join(f"{type(exc).__name__}: {exc}" for exc in close_errors)
    if primary is not None:
        primary.add_note(f"descriptor cleanup failed: {detail}")
        return
    raise BootstrapError(f"descriptor cleanup failed: {detail}")


def _package_verifier_pin(
    source_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _exact_keys(
        source_identity,
        {"device", "inode", "mode", "mode_octal", "path", "sha256", "size_bytes"},
        "package verifier planned source identity",
    )
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] <= 0
        or type(record["device"]) is not int
        or type(record["inode"]) is not int
        or type(record["mode"]) is not int
        or record["mode_octal"] != f"{record['mode']:04o}"
    ):
        raise BootstrapError("package verifier planned source identity is malformed")
    return {
        "package_path": PACKAGE_INDEPENDENT_VERIFIER_PACKAGE_PATH,
        "sha256": record["sha256"],
        "size_bytes": record["size_bytes"],
    }


def _native_helper_pin(
    source_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _exact_keys(
        source_identity,
        {
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "requested_path",
            "sha256",
            "size_bytes",
        },
        "native budget helper planned source identity",
    )
    capability = _native_helper_capability_from_full(record)
    return dict(capability)


def _require_package_verifier_source_binding(
    *,
    planned: Mapping[str, Mapping[str, object]],
    candidate: Mapping[str, object],
    gate_b: Mapping[str, object],
) -> Mapping[str, object]:
    try:
        expected = planned["script.package_independent_verifier_v1"]
        candidate_identity = candidate["package_verifier_source_identity"]
        gate_b_identity = gate_b["package_verifier_source_identity"]
    except KeyError as exc:
        raise BootstrapError(
            "package verifier source binding is incomplete"
        ) from exc
    if candidate_identity != expected or gate_b_identity != expected:
        raise BootstrapError(
            "Gate-A candidate/Gate-B/current package verifier source binding drifted"
        )
    _package_verifier_pin(expected)
    return expected


def _require_native_helper_source_binding(
    *,
    planned: Mapping[str, Mapping[str, object]],
    candidate: Mapping[str, object],
    gate_b: Mapping[str, object],
) -> Mapping[str, object]:
    try:
        expected = planned["system.native_budget_helper"]
        candidate_identity = candidate["native_budget_helper_source_identity"]
        gate_b_identity = gate_b["native_budget_helper_source_identity"]
    except KeyError as exc:
        raise BootstrapError(
            "native budget helper source binding is incomplete"
        ) from exc
    if candidate_identity != expected or gate_b_identity != expected:
        raise BootstrapError(
            "Gate-A candidate/Gate-B/current native budget helper source "
            "binding drifted"
        )
    _native_helper_pin(expected)
    return expected


def _open_retained_package_verifier(
    package_dir: Path,
    *,
    expected_pin: Mapping[str, object],
    retained_package_fd: int | None = None,
) -> tuple[int, int]:
    package_fd: int | None = None
    payload_fd: int | None = None
    verifier_fd: int | None = None
    primary: BaseException | None = None
    try:
        if retained_package_fd is None:
            absolute, package_fd = _open_directory_fd(package_dir)
            if absolute != _absolute(package_dir):
                raise BootstrapError("package root absolute identity drifted")
        else:
            retained_before = os.fstat(retained_package_fd)
            package_fd = os.dup(retained_package_fd)
            absolute, joined_fd = _open_directory_fd(package_dir)
            try:
                if (
                    absolute != _absolute(package_dir)
                    or _stat_signature(os.fstat(package_fd))
                    != _stat_signature(retained_before)
                    or _stat_signature(os.fstat(joined_fd))
                    != _stat_signature(retained_before)
                    or _stat_signature(os.fstat(retained_package_fd))
                    != _stat_signature(retained_before)
                ):
                    raise BootstrapError(
                        "retained package root absolute identity drifted"
                    )
            finally:
                os.close(joined_fd)
        payload_named = os.stat(
            "payload",
            dir_fd=package_fd,
            follow_symlinks=False,
        )
        payload_fd = os.open(
            "payload",
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=package_fd,
        )
        payload_opened = os.fstat(payload_fd)
        if (
            not stat.S_ISDIR(payload_named.st_mode)
            or _stat_signature(payload_named) != _stat_signature(payload_opened)
        ):
            raise BootstrapError("package payload directory identity drifted")
        member_name = Path(PACKAGE_INDEPENDENT_VERIFIER_PACKAGE_PATH).name
        verifier_named = os.stat(
            member_name,
            dir_fd=payload_fd,
            follow_symlinks=False,
        )
        verifier_fd = os.open(
            member_name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=payload_fd,
        )
        verifier_opened = os.fstat(verifier_fd)
        expected = _exact_keys(
            expected_pin,
            {"package_path", "sha256", "size_bytes"},
            "package verifier external pin",
        )
        if (
            expected["package_path"] != PACKAGE_INDEPENDENT_VERIFIER_PACKAGE_PATH
            or not stat.S_ISREG(verifier_named.st_mode)
            or verifier_named.st_nlink != 1
            or _stat_signature(verifier_named) != _stat_signature(verifier_opened)
            or verifier_opened.st_nlink != 1
            or verifier_opened.st_size != expected["size_bytes"]
            or hashlib.sha256(
                _read_exact_fd(
                    verifier_fd,
                    verifier_opened.st_size,
                    label="package verifier member",
                )
            ).hexdigest()
            != expected["sha256"]
            or _stat_signature(verifier_opened)
            != _stat_signature(os.fstat(verifier_fd))
        ):
            raise BootstrapError(
                "package verifier member differs from the external pre-registration"
            )
        os.close(payload_fd)
        payload_fd = None
        result = (package_fd, verifier_fd)
        package_fd = None
        verifier_fd = None
        return result
    except BaseException as exc:
        primary = exc
        raise
    finally:
        _close_descriptors_with_primary(
            [
                descriptor
                for descriptor in (verifier_fd, payload_fd, package_fd)
                if descriptor is not None
            ],
            primary=primary,
        )


def _read_bounded_pipe(
    descriptor: int,
    *,
    limit: int,
    sink: list[object],
) -> None:
    raw = bytearray()
    try:
        while True:
            block = os.read(descriptor, 65536)
            if not block:
                break
            raw.extend(block)
            if len(raw) > limit:
                raise BootstrapError("package verifier result exceeded its fixed limit")
        sink.append(bytes(raw))
    except BaseException as exc:
        sink.append(exc)
    finally:
        try:
            os.close(descriptor)
        except OSError as exc:
            sink.append(exc)


def _validate_package_independent_result(
    value: object,
    *,
    expected_pin: Mapping[str, object],
    package: Mapping[str, object],
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
    expected_native_helper: Mapping[str, object],
) -> Mapping[str, Any]:
    result = _exact_keys(
        value,
        {
            "arm_launch_authorized",
            "artifact_manifest",
            "artifact_manifest_sha256",
            "authority_scope",
            "classification_authorized",
            "landlock",
            "manager_epoch",
            "manifest_identity",
            "native_helper_identity",
            "package_id",
            "repository_head",
            "run_nonce",
            "schema",
            "seal_identity",
            "status",
            "verifier_identity",
            "whole_campaign_authorized",
        },
        "package-independent replay",
    )
    pin = _exact_keys(
        result["verifier_identity"],
        {"package_path", "sha256", "size_bytes"},
        "package-independent replay verifier identity",
    )
    native_helper = _exact_keys(
        result["native_helper_identity"],
        {
            "binary_format",
            "build_id_sha1",
            "byte_order",
            "elf_abi",
            "elf_machine",
            "elf_type",
            "elf_version",
            "host_machine",
            "host_platform",
            "mode",
            "package_path",
            "sha256",
            "size_bytes",
            "wrapper_package_path",
        },
        "package-independent replay native helper identity",
    )
    manifest_identity = _exact_keys(
        result["manifest_identity"],
        {"path", "sha256", "size_bytes"},
        "package-independent replay manifest identity",
    )
    seal_identity = _exact_keys(
        result["seal_identity"],
        {"path", "sha256", "size_bytes"},
        "package-independent replay seal identity",
    )
    landlock = _exact_keys(
        result["landlock"],
        {"abi_version", "handled_access_fs", "new_path_opens_denied", "policy"},
        "package-independent replay Landlock result",
    )
    artifacts = result["artifact_manifest"]
    if type(artifacts) is not list or not artifacts:
        raise BootstrapError("package-independent replay artifact manifest is malformed")
    paths: set[str] = set()
    regular_paths: set[str] = set()
    for index, raw_entry in enumerate(artifacts):
        if type(raw_entry) is not dict or raw_entry.get("type") not in {
            "directory",
            "regular",
        }:
            raise BootstrapError(
                f"package-independent replay artifact {index} is malformed"
            )
        expected_keys = (
            {"path", "type"}
            if raw_entry["type"] == "directory"
            else {"path", "sha256", "size_bytes", "type"}
        )
        entry = _exact_keys(
            raw_entry,
            expected_keys,
            f"package-independent replay artifact {index}",
        )
        path = entry["path"]
        if (
            type(path) is not str
            or not path
            or path.startswith("/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or path in paths
        ):
            raise BootstrapError(
                "package-independent replay artifact path is invalid or duplicated"
            )
        paths.add(path)
        if entry["type"] == "regular":
            if (
                type(entry["sha256"]) is not str
                or SHA256_RE.fullmatch(entry["sha256"]) is None
                or type(entry["size_bytes"]) is not int
                or entry["size_bytes"] < 0
            ):
                raise BootstrapError(
                    "package-independent replay regular identity is malformed"
                )
            regular_paths.add(path)
    package_manifest = _exact_keys(
        package,
        {
            "manifest_identity",
            "package_dir",
            "package_id",
            "schema",
            "seal_identity",
            "status",
        },
        "package record",
    )
    expected_manifest = authority.validate_detached_identity(
        package_manifest["manifest_identity"],
        "package manifest identity",
    )
    expected_seal = authority.validate_detached_identity(
        package_manifest["seal_identity"],
        "package seal identity",
    )
    if (
        result["schema"] != PACKAGE_INDEPENDENT_REPLAY_SCHEMA
        or result["status"] != "PASS"
        or result["authority_scope"] != "AB16_RESEARCH_ONLY"
        or result["arm_launch_authorized"] is not False
        or result["classification_authorized"] is not False
        or result["whole_campaign_authorized"] is not False
        or dict(pin) != dict(expected_pin)
        or dict(native_helper) != dict(expected_native_helper)
        or package_manifest["schema"] != PACKAGE_SCHEMA
        or package_manifest["status"] != "SEALED"
        or type(package_manifest["package_dir"]) is not str
        or package_manifest["package_dir"] != str(
            _absolute(package_manifest["package_dir"])
        )
        or result["package_id"] != package_manifest["package_id"]
        or result["repository_head"] != repository_head
        or result["run_nonce"] != run_nonce
        or result["manager_epoch"] != manager_epoch
        or manifest_identity
        != {
            "path": "package-manifest.json",
            "sha256": expected_manifest["sha256"],
            "size_bytes": expected_manifest["size_bytes"],
        }
        or seal_identity
        != {
            "path": "SHA256SUMS",
            "sha256": expected_seal["sha256"],
            "size_bytes": expected_seal["size_bytes"],
        }
        or landlock["new_path_opens_denied"] is not True
        or type(landlock["abi_version"]) is not int
        or landlock["abi_version"] < 1
        or type(landlock["handled_access_fs"]) is not int
        or landlock["handled_access_fs"] <= 0
        or landlock["policy"] != "deny-all-filesystem-after-retained-fd-open-v1"
        or hashlib.sha256(authority.canonical_json(artifacts)).hexdigest()
        != result["artifact_manifest_sha256"]
        or not {
            "package-manifest.json",
            "SHA256SUMS",
            PACKAGE_INDEPENDENT_VERIFIER_PACKAGE_PATH,
            NATIVE_BUDGET_HELPER_PACKAGE_PATH,
            NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH,
        }
        <= regular_paths
    ):
        raise BootstrapError("package-independent replay result binding drifted")
    return result


def _run_package_independent_verifier(
    *,
    package_dir: Path,
    package: Mapping[str, object],
    verifier_source_identity: Mapping[str, object],
    python_path: Path,
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
    native_helper_source_identity: Mapping[str, object],
    retained_package_fd: int | None = None,
) -> bytes:
    pin = _package_verifier_pin(verifier_source_identity)
    native_helper_pin = _native_helper_pin(native_helper_source_identity)
    package_fd, verifier_fd = _open_retained_package_verifier(
        package_dir,
        expected_pin=pin,
        retained_package_fd=retained_package_fd,
    )
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    collected: list[object] = []
    reader = threading.Thread(
        target=_read_bounded_pipe,
        kwargs={
            "descriptor": read_fd,
            "limit": PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
            "sink": collected,
        },
        name="ab16-package-independent-verifier-result",
        daemon=False,
    )
    process: subprocess.Popen[bytes] | None = None
    primary: BaseException | None = None
    try:
        pin_json = authority.canonical_json(pin).decode("utf-8").rstrip("\n")
        native_helper_pin_json = authority.canonical_json(
            native_helper_pin
        ).decode("utf-8").rstrip("\n")
        command = [
            str(python_path),
            "-I",
            "-B",
            "-S",
            "-c",
            PACKAGE_VERIFIER_SELECTED_FD_LOADER_V1,
            str(verifier_fd),
            str(pin["size_bytes"]),
            str(pin["sha256"]),
            "--package-fd",
            str(package_fd),
            "--verifier-fd",
            str(verifier_fd),
            "--result-fd",
            str(write_fd),
            "--expected-verifier-json",
            pin_json,
            "--expected-native-helper-json",
            native_helper_pin_json,
        ]
        reader.start()
        process = subprocess.Popen(
            command,
            cwd="/",
            env={
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            pass_fds=(package_fd, verifier_fd, write_fd),
        )
        os.close(write_fd)
        write_fd = -1
        os.close(package_fd)
        package_fd = -1
        os.close(verifier_fd)
        verifier_fd = -1
        try:
            stdout, stderr = process.communicate(
                timeout=PACKAGE_INDEPENDENT_VERIFIER_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as exc:
            process.kill()
            _stdout, _stderr = process.communicate()
            reader.join()
            raise BootstrapError(
                "package-independent verifier exceeded its fixed timeout"
            ) from exc
        reader.join()
        if len(collected) != 1 or isinstance(collected[0], BaseException):
            detail = (
                repr(collected[0])
                if collected
                else "result reader produced no terminal value"
            )
            raise BootstrapError(
                f"package-independent verifier result transport failed: {detail}"
            )
        raw = collected[0]
        if not isinstance(raw, bytes) or not raw:
            raise BootstrapError("package-independent verifier emitted no result")
        value = authority.strict_loads(raw, "package-independent replay")
        if authority.canonical_json(value) != raw:
            raise BootstrapError("package-independent replay is not canonical JSON")
        if process.returncode != 0:
            if isinstance(value, Mapping):
                error_code = value.get("error_code", "UNKNOWN")
            else:
                error_code = "NON_OBJECT"
            raise BootstrapError(
                "package-independent verifier failed closed: "
                f"rc={process.returncode} code={error_code} stderr={stderr!r}"
            )
        if stdout != b"" or stderr != b"":
            raise BootstrapError(
                "package-independent verifier used an undeclared stdio channel"
            )
        _validate_package_independent_result(
            value,
            expected_pin=pin,
            package=package,
            repository_head=repository_head,
            run_nonce=run_nonce,
            manager_epoch=manager_epoch,
            expected_native_helper=native_helper_pin,
        )
        return raw
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if reader.is_alive():
            try:
                if write_fd >= 0:
                    os.close(write_fd)
                    write_fd = -1
            except OSError as exc:
                if primary is not None:
                    primary.add_note(f"result-pipe cleanup failed: {exc}")
            reader.join(timeout=5)
        _close_descriptors_with_primary(
            [
                descriptor
                for descriptor in (write_fd, package_fd, verifier_fd)
                if descriptor >= 0
            ],
            primary=primary,
        )


def _rename_noreplace_at(
    parent_fd: int,
    source_name: str,
    target_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise BootstrapError("renameat2(RENAME_NOREPLACE) is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if (
        renameat2(
            parent_fd,
            os.fsencode(source_name),
            parent_fd,
            os.fsencode(target_name),
            1,
        )
        != 0
    ):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target_name)


def _require_absent_at(parent_fd: int, name: str, label: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise BootstrapError(f"{label} absence cannot be established") from exc
    raise BootstrapError(f"{label} already exists; no-overwrite applies")


def _preallocate_keep_size(
    descriptor: int,
    size_bytes: int,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fallocate = getattr(libc, "fallocate", None)
    if fallocate is None:
        raise BootstrapError("fallocate(FALLOC_FL_KEEP_SIZE) is unavailable")
    fallocate.argtypes = (
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_longlong,
        ctypes.c_longlong,
    )
    fallocate.restype = ctypes.c_int
    if fallocate(descriptor, 1, 0, size_bytes) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    allocated = os.fstat(descriptor)
    if allocated.st_size != 0 or allocated.st_blocks * 512 < size_bytes:
        raise BootstrapError(
            "staging filesystem did not retain the full physical replay reserve"
        )


def _publish_package_independent_replay(
    *,
    raw: bytes,
    final_path: Path,
    staging_path: Path,
    budget_writer: _BootstrapBudgetAuthority | None = None,
) -> dict[str, object]:
    final = _absolute(final_path)
    staging = _absolute(staging_path)
    if (
        final.parent != staging.parent
        or final.name == staging.name
        or len(raw) == 0
        or len(raw) > PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES
    ):
        raise BootstrapError("package-independent replay publication paths or size drifted")
    if budget_writer is not None:
        if staging.exists() or staging.is_symlink():
            raise BootstrapError(
                "package-independent replay fixed staging path is occupied"
            )
        identity = budget_writer.write_exclusive(final, raw, mode=0o444)
        replay = authority.snapshot_regular(final)
        expected = {
            "path": str(final),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        if identity != expected or authority.detached_identity(replay) != expected:
            raise BootstrapError(
                "budgeted package-independent replay self-replay drifted"
            )
        return expected
    parent_path, parent_fd = _open_directory_fd(final.parent)
    staging_fd: int | None = None
    replay_fd: int | None = None
    joined_parent_fd: int | None = None
    renamed = False
    primary: BaseException | None = None
    try:
        if parent_path != final.parent:
            raise BootstrapError("package-independent replay parent path drifted")
        _require_absent_at(parent_fd, staging.name, "package replay staging member")
        _require_absent_at(parent_fd, final.name, "package replay final member")
        staging_fd = os.open(
            staging.name,
            os.O_RDWR
            | os.O_CLOEXEC
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        _preallocate_keep_size(
            staging_fd,
            PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )
        offset = 0
        while offset < len(raw):
            written = os.pwrite(staging_fd, raw[offset:], offset)
            if written <= 0:
                raise BootstrapError(
                    "package-independent replay staging write made no progress"
                )
            offset += written
        os.fsync(staging_fd)
        before_publish = os.fstat(staging_fd)
        if (
            not stat.S_ISREG(before_publish.st_mode)
            or before_publish.st_nlink != 1
            or before_publish.st_uid != os.getuid()
            or stat.S_IMODE(before_publish.st_mode) != 0o600
            or before_publish.st_size != len(raw)
            or _read_exact_fd(
                staging_fd,
                before_publish.st_size,
                label="package replay staging member",
            )
            != raw
        ):
            raise BootstrapError("package-independent replay staging verification failed")
        os.fchmod(staging_fd, 0o444)
        os.fsync(staging_fd)
        readonly = os.fstat(staging_fd)
        if (
            (readonly.st_dev, readonly.st_ino)
            != (before_publish.st_dev, before_publish.st_ino)
            or stat.S_IMODE(readonly.st_mode) != 0o444
        ):
            raise BootstrapError("package-independent replay mode promotion drifted")
        _rename_noreplace_at(parent_fd, staging.name, final.name)
        renamed = True
        os.fsync(parent_fd)
        replay_fd = os.open(
            final.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        replay_stat = os.fstat(replay_fd)
        named = os.stat(
            final.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            _stat_signature(replay_stat) != _stat_signature(named)
            or (replay_stat.st_dev, replay_stat.st_ino)
            != (readonly.st_dev, readonly.st_ino)
            or stat.S_IMODE(replay_stat.st_mode) != 0o444
            or replay_stat.st_nlink != 1
            or replay_stat.st_uid != os.getuid()
            or replay_stat.st_size != len(raw)
            or _read_exact_fd(
                replay_fd,
                replay_stat.st_size,
                label="package-independent replay final member",
            )
            != raw
        ):
            raise BootstrapError("package-independent replay final identity drifted")
        joined_parent_path, joined_parent_fd = _open_directory_fd(final.parent)
        joined_parent = os.fstat(joined_parent_fd)
        retained_parent = os.fstat(parent_fd)
        joined_leaf = os.stat(
            final.name,
            dir_fd=joined_parent_fd,
            follow_symlinks=False,
        )
        if (
            joined_parent_path != final.parent
            or (joined_parent.st_dev, joined_parent.st_ino)
            != (retained_parent.st_dev, retained_parent.st_ino)
            or _stat_signature(joined_leaf) != _stat_signature(replay_stat)
            or _stat_signature(os.fstat(replay_fd)) != _stat_signature(replay_stat)
        ):
            raise BootstrapError(
                "package-independent replay absolute-path self-replay failed"
            )
        return {
            "path": str(final),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
    except BaseException as exc:
        primary = exc
        if renamed:
            exc.add_note(
                "package-independent replay reached the no-replace commit point "
                "but did not return PASS"
            )
        raise
    finally:
        _close_descriptors_with_primary(
            [
                descriptor
                for descriptor in (
                    joined_parent_fd,
                    replay_fd,
                    staging_fd,
                    parent_fd,
                )
                if descriptor is not None
            ],
            primary=primary,
        )


class VerifiedPackageIndependentReplay:
    """Own the canonical verifier result and its retained published FD."""

    def __init__(
        self,
        *,
        result: Mapping[str, object],
        identity: Mapping[str, object],
        descriptor: int,
        signature: tuple[int, ...],
        raw: bytes,
    ) -> None:
        self.result = dict(result)
        self.identity = dict(identity)
        self._descriptor = descriptor
        self._signature = signature
        self._raw = raw
        self._closed = False

    def fileno(self) -> int:
        if self._closed:
            raise BootstrapError("package-independent replay authorization is closed")
        current = os.fstat(self._descriptor)
        if (
            _stat_signature(current) != self._signature
            or _read_exact_fd(
                self._descriptor,
                len(self._raw),
                label="retained package-independent replay",
            )
            != self._raw
            or _stat_signature(os.fstat(self._descriptor)) != self._signature
        ):
            raise BootstrapError(
                "retained package-independent replay identity drifted"
            )
        return self._descriptor

    def close(self) -> None:
        if self._closed:
            return
        primary: BaseException | None = None
        try:
            self.fileno()
        except BaseException as exc:
            primary = exc
        descriptor = self._descriptor
        self._descriptor = -1
        self._closed = True
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                raise
            primary.add_note(
                "package-independent replay FD cleanup also failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
        if primary is not None:
            raise primary


def _retain_published_package_independent_replay(
    *,
    raw: bytes,
    result: Mapping[str, object],
    identity: Mapping[str, object],
) -> VerifiedPackageIndependentReplay:
    replay_identity = authority.validate_detached_identity(
        identity,
        "published package-independent replay",
    )
    replay_path = Path(replay_identity["path"])
    parent_path, parent_fd = _open_directory_fd(replay_path.parent)
    descriptor: int | None = None
    primary: BaseException | None = None
    try:
        if parent_path != replay_path.parent:
            raise BootstrapError(
                "published package-independent replay parent identity drifted"
            )
        descriptor = os.open(
            replay_path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        metadata = os.fstat(descriptor)
        named = os.stat(
            replay_path.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o444
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
            or metadata.st_size != len(raw)
            or _stat_signature(metadata) != _stat_signature(named)
            or replay_identity["sha256"] != hashlib.sha256(raw).hexdigest()
            or replay_identity["size_bytes"] != len(raw)
            or _read_exact_fd(
                descriptor,
                len(raw),
                label="published package-independent replay",
            )
            != raw
            or _stat_signature(os.fstat(descriptor))
            != _stat_signature(metadata)
        ):
            raise BootstrapError(
                "published package-independent replay retained identity drifted"
            )
        retained = VerifiedPackageIndependentReplay(
            result=result,
            identity=replay_identity,
            descriptor=descriptor,
            signature=_stat_signature(metadata),
            raw=raw,
        )
        descriptor = None
        return retained
    except BaseException as exc:
        primary = exc
        raise
    finally:
        _close_descriptors_with_primary(
            [
                owned
                for owned in (descriptor, parent_fd)
                if owned is not None
            ],
            primary=primary,
        )


def _verify_and_publish_package_independent_replay(
    *,
    package_dir: Path,
    package: Mapping[str, object],
    verifier_source_identity: Mapping[str, object],
    python_path: Path,
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
    native_helper_source_identity: Mapping[str, object],
    final_path: Path,
    staging_path: Path,
    budget_writer: _BootstrapBudgetAuthority | None = None,
    retained_package_fd: int | None = None,
) -> VerifiedPackageIndependentReplay:
    """Cross the package execution boundary only after independent PASS."""

    raw = _run_package_independent_verifier(
        package_dir=package_dir,
        package=package,
        verifier_source_identity=verifier_source_identity,
        python_path=python_path,
        repository_head=repository_head,
        run_nonce=run_nonce,
        manager_epoch=manager_epoch,
        native_helper_source_identity=native_helper_source_identity,
        retained_package_fd=retained_package_fd,
    )
    parsed = authority.strict_loads(
        raw,
        "package-independent replay result",
    )
    if not isinstance(parsed, Mapping) or authority.canonical_json(parsed) != raw:
        raise BootstrapError(
            "package-independent replay result is not one canonical object"
        )
    identity = _publish_package_independent_replay(
        raw=raw,
        final_path=final_path,
        staging_path=staging_path,
        budget_writer=budget_writer,
    )
    return _retain_published_package_independent_replay(
        raw=raw,
        result=parsed,
        identity=identity,
    )


def _retained_package_member_bytes(
    descriptor: int,
    *,
    label: str,
    maximum_size: int,
) -> tuple[bytes, tuple[int, ...]]:
    try:
        before = os.fstat(descriptor)
    except OSError as exc:
        raise BootstrapError(f"{label} retained FD cannot be inspected") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 1
        or before.st_size > maximum_size
    ):
        raise BootstrapError(f"{label} retained FD identity is invalid")
    raw = _read_exact_fd(descriptor, before.st_size, label=label)
    try:
        if os.pread(descriptor, 1, before.st_size):
            raise BootstrapError(f"{label} retained FD grew while reading")
        after = os.fstat(descriptor)
    except OSError as exc:
        raise BootstrapError(f"{label} retained FD cannot be rechecked") from exc
    signature = _stat_signature(before)
    if _stat_signature(after) != signature:
        raise BootstrapError(f"{label} retained FD changed while reading")
    return raw, signature


def _package_source_identity_pin(
    value: object,
    *,
    label: str,
    system_tool: bool,
) -> Mapping[str, object]:
    keys = {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }
    if system_tool:
        keys.add("requested_path")
    record = _exact_keys(value, keys, label)
    if (
        type(record["device"]) is not int
        or type(record["inode"]) is not int
        or type(record["mode"]) is not int
        or record["mode_octal"] != f"{record['mode']:04o}"
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] <= 0
        or (
            system_tool
            and (
                type(record["requested_path"]) is not str
                or not Path(record["requested_path"]).is_absolute()
            )
        )
    ):
        raise BootstrapError(f"{label} is malformed")
    return record


def _package_native_manifest_join(
    manifest_raw: bytes,
    *,
    wrapper_source_identity: Mapping[str, object],
    native_helper_source_identity: Mapping[str, object],
    wrapper_raw: bytes,
    native_raw: bytes,
) -> None:
    manifest = authority.strict_loads(
        manifest_raw,
        "post-verifier package manifest",
    )
    record = _exact_keys(
        manifest,
        {
            "authorization_semantics",
            "external_sources",
            "manager_epoch",
            "package_members",
            "repository_head",
            "run_nonce",
            "schema",
            "seal_contract",
        },
        "post-verifier package manifest",
    )
    if record["schema"] != PACKAGE_MANIFEST_SCHEMA:
        raise BootstrapError("post-verifier package manifest schema drifted")
    external_sources = record["external_sources"]
    package_members = record["package_members"]
    if type(external_sources) is not list or type(package_members) is not list:
        raise BootstrapError("post-verifier package manifest lists are malformed")
    source_records: dict[str, Mapping[str, object]] = {}
    for index, raw_source in enumerate(external_sources):
        source = _exact_keys(
            raw_source,
            {
                "package_path",
                "parse_json",
                "role",
                "source_identity",
            },
            f"post-verifier package source {index}",
        )
        role = source["role"]
        if type(role) is not str or role in source_records:
            raise BootstrapError(
                "post-verifier package source role is invalid or duplicated"
            )
        if source["parse_json"] is not False:
            if role in {
                "tool.ab16_native_budget_helper_v1.py",
                "system.native_budget_helper.bin",
            }:
                raise BootstrapError(
                    "native package roles cannot be parsed as JSON"
                )
        if not isinstance(source["source_identity"], Mapping):
            raise BootstrapError(
                "post-verifier package source identity is malformed"
            )
        source_records[role] = source
    expected_sources = {
        "tool.ab16_native_budget_helper_v1.py": (
            NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH,
            wrapper_source_identity,
        ),
        "system.native_budget_helper.bin": (
            NATIVE_BUDGET_HELPER_PACKAGE_PATH,
            native_helper_source_identity,
        ),
    }
    for role, (package_path, source_identity) in expected_sources.items():
        selected_source = source_records.get(role)
        if (
            selected_source is None
            or selected_source["package_path"] != package_path
        ):
            raise BootstrapError(
                f"post-verifier package source join drifted: {role}"
            )
        selected_identity = selected_source["source_identity"]
        if (
            not isinstance(selected_identity, Mapping)
            or dict(selected_identity) != dict(source_identity)
        ):
            raise BootstrapError(
                f"post-verifier package source join drifted: {role}"
            )

    member_records: dict[str, Mapping[str, object]] = {}
    for index, raw_member in enumerate(package_members):
        member = _exact_keys(
            raw_member,
            {"path", "sha256", "size_bytes"},
            f"post-verifier package member {index}",
        )
        path = member["path"]
        if type(path) is not str or path in member_records:
            raise BootstrapError(
                "post-verifier package member path is invalid or duplicated"
            )
        member_records[path] = member
    for path, raw in (
        (NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH, wrapper_raw),
        (NATIVE_BUDGET_HELPER_PACKAGE_PATH, native_raw),
    ):
        selected_member = member_records.get(path)
        if (
            selected_member is None
            or selected_member["sha256"] != hashlib.sha256(raw).hexdigest()
            or selected_member["size_bytes"] != len(raw)
        ):
            raise BootstrapError(
                f"post-verifier package member identity drifted: {path}"
            )


class PackageNativeBudgetHelperHandle:
    """Own all retained package FDs supporting one native helper instance."""

    def __init__(
        self,
        *,
        helper: object,
        wrapper_module: types.ModuleType,
        descriptors: Sequence[int],
        signatures: Mapping[int, tuple[int, ...]],
    ) -> None:
        self._helper = helper
        self._wrapper_module = wrapper_module
        self._descriptors = tuple(descriptors)
        self._signatures = dict(signatures)
        self._closed = False

    @property
    def helper(self) -> object:
        if self._closed:
            raise BootstrapError("package native helper handle is closed")
        return self._helper

    @property
    def wrapper_module(self) -> types.ModuleType:
        if self._closed:
            raise BootstrapError("package native helper handle is closed")
        return self._wrapper_module

    def retained_descriptors(self) -> tuple[int, ...]:
        """Return the fixed inherited set while this handle owns it."""

        if self._closed:
            raise BootstrapError("package native helper handle is closed")
        return self._descriptors

    def close(self) -> None:
        if self._closed:
            return
        primary: BaseException | None = None
        try:
            for descriptor in self._descriptors:
                try:
                    current = os.fstat(descriptor)
                except OSError as exc:
                    raise BootstrapError(
                        "package native helper retained FD cannot be rechecked"
                    ) from exc
                expected = self._signatures.get(descriptor)
                if (
                    expected is not None
                    and _stat_signature(current) != expected
                ):
                    raise BootstrapError(
                        "package native helper retained FD identity drifted"
                    )
        except BaseException as exc:
            primary = exc
        self._closed = True
        _close_descriptors_with_primary(
            tuple(reversed(self._descriptors)),
            primary=primary,
        )
        if primary is not None:
            raise primary

    def __enter__(self) -> PackageNativeBudgetHelperHandle:
        return self

    def __exit__(
        self,
        _exc_type: object,
        exc: BaseException | None,
        _traceback: object,
    ) -> None:
        try:
            self.close()
        except BaseException as close_exc:
            if exc is None:
                raise
            exc.add_note(
                "package native helper handle cleanup failed: "
                f"{type(close_exc).__name__}: {close_exc}"
            )


class RetainedPackageBudgetRoleAuthorization:
    """One post-verifier, retained-FD authorization for the budget roles.

    The handle has no reopen-by-path operation.  It owns the package closure
    descriptors and the exact role source descriptors until ownership is
    committed to the persistent broker child.
    """

    def __init__(
        self,
        *,
        descriptors: Sequence[int],
        signatures: Mapping[int, tuple[int, ...]],
        role_descriptors: Mapping[str, int],
        role_bytes: Mapping[str, bytes],
        selected_descriptors: Mapping[str, int],
        selected_records: Mapping[str, Mapping[str, object]],
    ) -> None:
        self._descriptors = tuple(descriptors)
        self._signatures = dict(signatures)
        self._role_descriptors = dict(role_descriptors)
        self._role_bytes = dict(role_bytes)
        self._selected_descriptors = dict(selected_descriptors)
        self._selected_records = {
            role: dict(record)
            for role, record in selected_records.items()
        }
        self._loaded_modules: dict[str, types.ModuleType] = {}
        self._closed = False

    def _require_loaded_module_bindings(self) -> None:
        """Reject drift anywhere in the retained package module surface."""

        for loaded_role, loaded_module in self._loaded_modules.items():
            for alias in PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[loaded_role]:
                if sys.modules.get(alias) is not loaded_module:
                    raise BootstrapError(
                        "package budget role module binding drifted: "
                        f"{loaded_role}"
                    )
                parent_name, separator, attribute = alias.rpartition(".")
                parent = sys.modules.get(parent_name) if separator else None
                if (
                    parent is not None
                    and hasattr(parent, attribute)
                    and getattr(parent, attribute) is not loaded_module
                ):
                    raise BootstrapError(
                        "package budget role package binding drifted: "
                        f"{loaded_role}"
                    )

    def _require_open(self) -> None:
        if self._closed:
            raise BootstrapError(
                "retained package budget-role authorization is closed"
            )

    def require_verified_role(self, role: str) -> None:
        """Recheck one member by the fixed logical role vocabulary."""

        self._require_open()
        if role not in PACKAGE_BUDGET_RUNTIME_ROLE_PATHS:
            raise BootstrapError(
                f"package budget role is not authorized: {role!r}"
            )
        descriptor = self._role_descriptors[role]
        expected_signature = self._signatures[descriptor]
        raw = self._role_bytes[role]
        try:
            current = os.fstat(descriptor)
        except OSError as exc:
            raise BootstrapError(
                f"package budget role FD cannot be rechecked: {role}"
            ) from exc
        if (
            _stat_signature(current) != expected_signature
            or current.st_size != len(raw)
            or _read_exact_fd(
                descriptor,
                len(raw),
                label=f"package budget role {role}",
            )
            != raw
            or _stat_signature(os.fstat(descriptor)) != expected_signature
        ):
            raise BootstrapError(
                f"package budget role retained identity drifted: {role}"
            )

    def role_descriptors(self) -> dict[str, int]:
        """Expose the closed role-to-FD map for one broker-child transfer."""

        self._require_open()
        for role in PACKAGE_BUDGET_RUNTIME_ROLE_PATHS:
            self.require_verified_role(role)
        return dict(self._role_descriptors)

    def retained_descriptors(self) -> tuple[int, ...]:
        """Expose the complete inherited closure descriptor set."""

        self._require_open()
        return self._descriptors

    def selected_fd_transport(self) -> dict[str, object]:
        """Bind the five regular systemd OpenFile sources to this live owner.

        The caller may persist this record only while this exact process and
        authorization remain alive.  A forked persistent broker calls the same
        method after ``fork`` so the owner PID/starttime and ``/proc`` aliases
        name the broker, not the bootstrap parent.
        """

        self._require_open()
        if set(self._selected_descriptors) != set(
            PACKAGE_SELECTED_FD_TRANSPORT_PATHS
        ):
            raise BootstrapError(
                "retained selected-FD transport role set drifted"
            )
        pid = os.getpid()
        roles: dict[str, dict[str, object]] = {}
        for role in sorted(PACKAGE_SELECTED_FD_TRANSPORT_PATHS):
            descriptor = self._selected_descriptors[role]
            expected = self._selected_records[role]
            current = os.fstat(descriptor)
            raw = _read_exact_fd(
                descriptor,
                int(expected["size_bytes"]),
                label=f"selected-FD transport {role}",
            )
            if (
                _stat_signature(current) != self._signatures[descriptor]
                or stat.S_IMODE(current.st_mode) != expected["mode"]
                or len(raw) != expected["size_bytes"]
                or hashlib.sha256(raw).hexdigest() != expected["sha256"]
                or _stat_signature(os.fstat(descriptor))
                != self._signatures[descriptor]
            ):
                raise BootstrapError(
                    f"retained selected-FD transport identity drifted: {role}"
                )
            roles[role] = {
                "descriptor": descriptor,
                "mode": expected["mode"],
                "package_path": expected["package_path"],
                "proc_fd_path": f"/proc/{pid}/fd/{descriptor}",
                "sha256": expected["sha256"],
                "size_bytes": expected["size_bytes"],
            }
        return {
            "owner": {
                "pid": pid,
                "pid_starttime": _proc_starttime(pid),
                "uid": os.getuid(),
            },
            "roles": roles,
            "schema_version": PACKAGE_SELECTED_FD_TRANSPORT_SCHEMA,
        }

    def load_verified_role(self, role: str) -> types.ModuleType:
        """Execute one role only from its retained verified descriptor."""

        self.require_verified_role(role)
        self._require_loaded_module_bindings()
        module_name = PACKAGE_BUDGET_RUNTIME_MODULE_NAMES[role]
        aliases = PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[role]
        loaded = self._loaded_modules.get(role)
        if loaded is not None:
            return loaded
        if (
            set(PACKAGE_BUDGET_RUNTIME_ROLE_DEPENDENCIES)
            != set(PACKAGE_BUDGET_RUNTIME_ROLE_PATHS)
            or set(PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES)
            != set(PACKAGE_BUDGET_RUNTIME_ROLE_PATHS)
        ):
            raise BootstrapError(
                "package budget role dependency vocabulary drifted"
            )
        flattened_aliases = [
            alias
            for candidate in PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES.values()
            for alias in candidate
        ]
        if len(flattened_aliases) != len(set(flattened_aliases)):
            raise BootstrapError(
                "package budget role module aliases are not unique"
            )
        dependencies = PACKAGE_BUDGET_RUNTIME_ROLE_DEPENDENCIES[role]
        if any(dependency not in self._loaded_modules for dependency in dependencies):
            raise BootstrapError(
                f"package budget role dependencies were not loaded first: {role}"
            )
        for dependency in dependencies:
            dependency_module = self._loaded_modules[dependency]
            for dependency_alias in (
                PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[dependency]
            ):
                if sys.modules.get(dependency_alias) is not dependency_module:
                    raise BootstrapError(
                        "package budget role dependency module binding "
                        f"drifted: {dependency}"
                    )
                parent_name, separator, attribute = dependency_alias.rpartition(
                    "."
                )
                parent = sys.modules.get(parent_name) if separator else None
                if (
                    parent is not None
                    and hasattr(parent, attribute)
                    and getattr(parent, attribute) is not dependency_module
                ):
                    raise BootstrapError(
                        "package budget role dependency package binding "
                        f"drifted: {dependency}"
                    )
        for alias in aliases:
            if alias in sys.modules:
                raise BootstrapError(
                    f"ambient module blocks retained package role: {alias}"
                )
            parent_name, separator, attribute = alias.rpartition(".")
            parent = sys.modules.get(parent_name) if separator else None
            if parent is not None and hasattr(parent, attribute):
                raise BootstrapError(
                    "ambient package attribute blocks retained package role: "
                    f"{alias}"
                )
        descriptor = self._role_descriptors[role]
        module = types.ModuleType(module_name)
        module.__file__ = f"/proc/self/fd/{descriptor}"
        module.__package__ = None
        for alias in aliases:
            sys.modules[alias] = module
        try:
            exec(
                compile(
                    self._role_bytes[role],
                    module.__file__,
                    "exec",
                    dont_inherit=True,
                ),
                module.__dict__,
            )
        except BaseException:
            for alias in aliases:
                if sys.modules.get(alias) is module:
                    sys.modules.pop(alias, None)
            raise
        if any(sys.modules.get(alias) is not module for alias in aliases):
            for alias in aliases:
                if sys.modules.get(alias) is module:
                    sys.modules.pop(alias, None)
            raise BootstrapError(
                f"package budget role changed its module binding: {role}"
            )
        self._require_loaded_module_bindings()
        self._loaded_modules[role] = module
        return module

    def close(self) -> None:
        if self._closed:
            return
        primary: BaseException | None = None
        try:
            for descriptor in self._descriptors:
                if _stat_signature(os.fstat(descriptor)) != self._signatures[
                    descriptor
                ]:
                    raise BootstrapError(
                        "retained package budget-role closure identity drifted"
                    )
        except BaseException as exc:
            primary = exc
        for role, module in reversed(tuple(self._loaded_modules.items())):
            for alias in PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[role]:
                if sys.modules.get(alias) is module:
                    sys.modules.pop(alias, None)
                parent_name, separator, attribute = alias.rpartition(".")
                parent = sys.modules.get(parent_name) if separator else None
                if parent is not None and getattr(parent, attribute, None) is module:
                    try:
                        delattr(parent, attribute)
                    except BaseException as exc:
                        if primary is None:
                            primary = exc
                        else:
                            primary.add_note(
                                "retained package role parent-alias cleanup "
                                f"also failed for {alias}: "
                                f"{type(exc).__name__}: {exc}"
                            )
        self._loaded_modules.clear()
        self._closed = True
        _close_descriptors_with_primary(
            tuple(reversed(self._descriptors)),
            primary=primary,
        )
        if primary is not None:
            raise primary

    def __enter__(self) -> RetainedPackageBudgetRoleAuthorization:
        return self

    def __exit__(
        self,
        _exc_type: object,
        exc: BaseException | None,
        _traceback: object,
    ) -> None:
        try:
            self.close()
        except BaseException as close_exc:
            if exc is None:
                raise
            exc.add_note(
                "retained package budget-role cleanup failed: "
                f"{type(close_exc).__name__}: {close_exc}"
            )


def _open_retained_package_node(
    name: str,
    *,
    flags: int,
    parent_fd: int,
    label: str,
) -> int:
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise BootstrapError(f"{label} retained-FD open failed") from exc


def _strict_package_seal(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise BootstrapError("retained package seal is not ASCII") from exc
    if not lines or not raw.endswith(b"\n"):
        raise BootstrapError(
            "retained package seal is empty or not newline terminated"
        )
    result: dict[str, str] = {}
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            raise BootstrapError("retained package seal line is malformed")
        digest = line[:64]
        relative = line[66:]
        if (
            SHA256_RE.fullmatch(digest) is None
            or relative in result
            or _budget_relative_path(
                relative,
                "retained package seal path",
            )
            != relative
            or relative == "SHA256SUMS"
        ):
            raise BootstrapError(
                "retained package seal entry is invalid or duplicated"
            )
        result[relative] = digest
    return result


def open_verified_package_budget_roles(
    *,
    package_root_fd: int,
    independent_replay_fd: int,
    independent_replay_identity: Mapping[str, object],
    package: Mapping[str, object],
    independent_result: object,
    verifier_source_identity: Mapping[str, object],
    native_helper_source_identity: Mapping[str, object],
    role_source_identities: Mapping[str, Mapping[str, object]],
    selected_source_identities: Mapping[str, Mapping[str, object]],
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
) -> RetainedPackageBudgetRoleAuthorization:
    """Retain the closed budget role set after independent replay-v2 PASS."""

    verifier_pin = _package_verifier_pin(verifier_source_identity)
    native_source_pin = _package_source_identity_pin(
        native_helper_source_identity,
        label="retained budget-role native helper source identity",
        system_tool=True,
    )
    if (
        native_source_pin["mode"] != NATIVE_BUDGET_HELPER_MODE
        or native_source_pin["sha256"] != NATIVE_BUDGET_HELPER_SHA256
        or native_source_pin["size_bytes"] != NATIVE_BUDGET_HELPER_SIZE_BYTES
    ):
        raise BootstrapError(
            "retained budget-role native helper source identity drifted"
        )
    expected_native = _native_helper_expected_capability()
    validated = _validate_package_independent_result(
        independent_result,
        expected_pin=verifier_pin,
        package=package,
        repository_head=repository_head,
        run_nonce=run_nonce,
        manager_epoch=manager_epoch,
        expected_native_helper=expected_native,
    )
    if validated["status"] != "PASS":
        raise BootstrapError("package-independent replay did not authorize roles")
    if set(role_source_identities) != set(PACKAGE_BUDGET_RUNTIME_ROLE_PATHS):
        raise BootstrapError("package budget role source identity set drifted")
    if set(selected_source_identities) != set(
        PACKAGE_SELECTED_FD_TRANSPORT_PATHS
    ):
        raise BootstrapError(
            "package selected-FD source identity set drifted"
        )
    if (
        type(package_root_fd) is not int
        or package_root_fd < 3
        or type(independent_replay_fd) is not int
        or independent_replay_fd < 3
    ):
        raise BootstrapError("retained package/replay FD is invalid")

    owned: list[int] = []
    signatures: dict[int, tuple[int, ...]] = {}
    role_descriptors: dict[str, int] = {}
    role_bytes: dict[str, bytes] = {}
    selected_descriptors: dict[str, int] = {}
    selected_records: dict[str, dict[str, object]] = {}
    primary: BaseException | None = None
    transferred = False
    try:
        root_fd = os.dup(package_root_fd)
        owned.append(root_fd)
        root_metadata = os.fstat(root_fd)
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise BootstrapError("retained package-root FD is not a directory")
        signatures[root_fd] = _stat_signature(root_metadata)

        replay_fd = os.dup(independent_replay_fd)
        owned.append(replay_fd)
        replay_raw, signatures[replay_fd] = _retained_package_member_bytes(
            replay_fd,
            label="package-independent replay receipt",
            maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )
        replay_identity = authority.validate_detached_identity(
            independent_replay_identity,
            "package-independent replay identity",
        )
        if (
            replay_identity["sha256"]
            != hashlib.sha256(replay_raw).hexdigest()
            or replay_identity["size_bytes"] != len(replay_raw)
            or authority.strict_loads(
                replay_raw,
                "retained package-independent replay",
            )
            != independent_result
            or authority.canonical_json(independent_result) != replay_raw
        ):
            raise BootstrapError(
                "retained package-independent replay identity drifted"
            )

        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        payload_fd = _open_retained_package_node(
            "payload",
            flags=flags | os.O_DIRECTORY,
            parent_fd=root_fd,
            label="post-verifier package payload",
        )
        owned.append(payload_fd)
        payload_metadata = os.fstat(payload_fd)
        if not stat.S_ISDIR(payload_metadata.st_mode):
            raise BootstrapError(
                "post-verifier package payload is not a directory"
            )
        signatures[payload_fd] = _stat_signature(payload_metadata)
        manifest_fd = _open_retained_package_node(
            "package-manifest.json",
            flags=flags,
            parent_fd=root_fd,
            label="post-verifier package manifest",
        )
        owned.append(manifest_fd)
        seal_fd = _open_retained_package_node(
            "SHA256SUMS",
            flags=flags,
            parent_fd=root_fd,
            label="post-verifier package seal",
        )
        owned.append(seal_fd)
        manifest_raw, signatures[manifest_fd] = _retained_package_member_bytes(
            manifest_fd,
            label="post-verifier package manifest",
            maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )
        seal_raw, signatures[seal_fd] = _retained_package_member_bytes(
            seal_fd,
            label="post-verifier package seal",
            maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )

        package_record = _exact_keys(
            package,
            {
                "manifest_identity",
                "package_dir",
                "package_id",
                "schema",
                "seal_identity",
                "status",
            },
            "post-verifier package record",
        )
        expected_manifest = authority.validate_detached_identity(
            package_record["manifest_identity"],
            "post-verifier package manifest identity",
        )
        expected_seal = authority.validate_detached_identity(
            package_record["seal_identity"],
            "post-verifier package seal identity",
        )
        if (
            package_record["schema"] != PACKAGE_SCHEMA
            or package_record["status"] != "SEALED"
            or package_record["package_id"] != hashlib.sha256(seal_raw).hexdigest()
            or expected_manifest["sha256"]
            != hashlib.sha256(manifest_raw).hexdigest()
            or expected_manifest["size_bytes"] != len(manifest_raw)
            or expected_seal["sha256"] != hashlib.sha256(seal_raw).hexdigest()
            or expected_seal["size_bytes"] != len(seal_raw)
        ):
            raise BootstrapError(
                "retained package manifest/seal identity drifted"
            )
        manifest = authority.strict_loads(
            manifest_raw,
            "retained post-verifier package manifest",
        )
        manifest = _exact_keys(
            manifest,
            {
                "authorization_semantics",
                "external_sources",
                "manager_epoch",
                "package_members",
                "repository_head",
                "run_nonce",
                "schema",
                "seal_contract",
            },
            "retained post-verifier package manifest",
        )
        if (
            manifest["schema"] != PACKAGE_MANIFEST_SCHEMA
            or authority.canonical_json(manifest) != manifest_raw
        ):
            raise BootstrapError(
                "retained post-verifier package manifest drifted"
            )
        external_sources = manifest["external_sources"]
        members = manifest["package_members"]
        if type(external_sources) is not list or type(members) is not list:
            raise BootstrapError(
                "retained package manifest lists are malformed"
            )
        sources_by_role: dict[str, Mapping[str, object]] = {}
        for index, raw_source in enumerate(external_sources):
            source = _exact_keys(
                raw_source,
                {
                    "package_path",
                    "parse_json",
                    "role",
                    "source_identity",
                },
                f"retained package source {index}",
            )
            source_role = source["role"]
            if type(source_role) is not str or source_role in sources_by_role:
                raise BootstrapError(
                    "retained package source role is invalid or duplicated"
                )
            sources_by_role[source_role] = source
        members_by_path: dict[str, Mapping[str, object]] = {}
        for index, raw_member in enumerate(members):
            member = _exact_keys(
                raw_member,
                {"path", "sha256", "size_bytes"},
                f"retained package member {index}",
            )
            member_path = member["path"]
            if type(member_path) is not str or member_path in members_by_path:
                raise BootstrapError(
                    "retained package member path is invalid or duplicated"
                )
            members_by_path[member_path] = member
        seal = _strict_package_seal(seal_raw)
        replay_artifacts = validated["artifact_manifest"]
        replay_regular = {
            str(item["path"]): item
            for item in replay_artifacts
            if item["type"] == "regular"
        }

        for logical_role, package_path in PACKAGE_BUDGET_RUNTIME_ROLE_PATHS.items():
            source_role = package_path.removeprefix("payload/")
            source = sources_by_role.get(source_role)
            member = members_by_path.get(package_path)
            replay_member = replay_regular.get(package_path)
            planned = role_source_identities[logical_role]
            if (
                source is None
                or source["package_path"] != package_path
                or source["parse_json"] is not False
                or not isinstance(source["source_identity"], Mapping)
                or source["source_identity"].get("sha256")
                != planned.get("sha256")
                or source["source_identity"].get("size_bytes")
                != planned.get("size_bytes")
                or member is None
                or replay_member is None
                or seal.get(package_path) != member["sha256"]
            ):
                raise BootstrapError(
                    f"retained package role closure drifted: {logical_role}"
                )
            descriptor = _open_retained_package_node(
                Path(package_path).name,
                flags=flags,
                parent_fd=payload_fd,
                label=f"post-verifier package role {logical_role}",
            )
            owned.append(descriptor)
            raw, signatures[descriptor] = _retained_package_member_bytes(
                descriptor,
                label=f"post-verifier package role {logical_role}",
                maximum_size=16 << 20,
            )
            if (
                member["sha256"] != hashlib.sha256(raw).hexdigest()
                or member["size_bytes"] != len(raw)
                or replay_member["sha256"] != member["sha256"]
                or replay_member["size_bytes"] != member["size_bytes"]
            ):
                raise BootstrapError(
                    f"retained package role identity drifted: {logical_role}"
                )
            role_descriptors[logical_role] = descriptor
            role_bytes[logical_role] = raw

        for logical_role, package_path in (
            PACKAGE_SELECTED_FD_TRANSPORT_PATHS.items()
        ):
            source_role = package_path.removeprefix("payload/")
            source = sources_by_role.get(source_role)
            member = members_by_path.get(package_path)
            replay_member = replay_regular.get(package_path)
            planned = selected_source_identities[logical_role]
            if (
                source is None
                or source["package_path"] != package_path
                or source["parse_json"] is not False
                or not isinstance(source["source_identity"], Mapping)
                or source["source_identity"].get("sha256")
                != planned.get("sha256")
                or source["source_identity"].get("size_bytes")
                != planned.get("size_bytes")
                or member is None
                or replay_member is None
                or seal.get(package_path) != member["sha256"]
            ):
                raise BootstrapError(
                    "retained selected-FD transport closure drifted: "
                    f"{logical_role}"
                )
            existing_role = next(
                (
                    role
                    for role in role_descriptors
                    if PACKAGE_BUDGET_RUNTIME_ROLE_PATHS[role]
                    == package_path
                ),
                None,
            )
            if existing_role is None:
                descriptor = _open_retained_package_node(
                    Path(package_path).name,
                    flags=flags,
                    parent_fd=payload_fd,
                    label=(
                        "post-verifier selected-FD transport "
                        f"{logical_role}"
                    ),
                )
                owned.append(descriptor)
                raw, signatures[descriptor] = (
                    _retained_package_member_bytes(
                        descriptor,
                        label=(
                            "post-verifier selected-FD transport "
                            f"{logical_role}"
                        ),
                        maximum_size=256 << 20,
                    )
                )
            else:
                descriptor = role_descriptors[existing_role]
                raw = role_bytes[existing_role]
            if (
                member["sha256"] != hashlib.sha256(raw).hexdigest()
                or member["size_bytes"] != len(raw)
                or replay_member["sha256"] != member["sha256"]
                or replay_member["size_bytes"] != member["size_bytes"]
            ):
                raise BootstrapError(
                    "retained selected-FD transport identity drifted: "
                    f"{logical_role}"
                )
            selected_descriptors[logical_role] = descriptor
            selected_records[logical_role] = {
                "mode": stat.S_IMODE(os.fstat(descriptor).st_mode),
                "package_path": package_path,
                "sha256": member["sha256"],
                "size_bytes": member["size_bytes"],
            }

        result = RetainedPackageBudgetRoleAuthorization(
            descriptors=owned,
            signatures=signatures,
            role_descriptors=role_descriptors,
            role_bytes=role_bytes,
            selected_descriptors=selected_descriptors,
            selected_records=selected_records,
        )
        transferred = True
        return result
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if not transferred:
            _close_descriptors_with_primary(
                tuple(reversed(owned)),
                primary=primary,
            )


def open_verified_package_native_budget_helper(
    *,
    package_root_fd: int,
    package: Mapping[str, object],
    independent_result: object,
    verifier_source_identity: Mapping[str, object],
    wrapper_source_identity: Mapping[str, object],
    native_helper_source_identity: Mapping[str, object],
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
) -> PackageNativeBudgetHelperHandle:
    """Load the native capability only after a bound independent package PASS."""

    verifier_pin = _package_verifier_pin(verifier_source_identity)
    wrapper_pin = _package_source_identity_pin(
        wrapper_source_identity,
        label="native helper wrapper planned source identity",
        system_tool=False,
    )
    native_source_pin = _package_source_identity_pin(
        native_helper_source_identity,
        label="native helper planned source identity",
        system_tool=True,
    )
    expected_native = _native_helper_expected_capability()
    native_manifest_pin = {
        key: native_source_pin[key]
        for key in (
            "device",
            "inode",
            "mode",
            "mode_octal",
            "path",
            "sha256",
            "size_bytes",
        )
    }
    if (
        native_source_pin["mode"] != NATIVE_BUDGET_HELPER_MODE
        or native_source_pin["sha256"] != NATIVE_BUDGET_HELPER_SHA256
        or native_source_pin["size_bytes"] != NATIVE_BUDGET_HELPER_SIZE_BYTES
    ):
        raise BootstrapError(
            "native helper external planned-source identity drifted"
        )
    # This is the authorization edge.  No package role FD is opened or code
    # executed until the independently produced PASS is fully validated.
    validated = _validate_package_independent_result(
        independent_result,
        expected_pin=verifier_pin,
        package=package,
        repository_head=repository_head,
        run_nonce=run_nonce,
        manager_epoch=manager_epoch,
        expected_native_helper=expected_native,
    )
    if validated["status"] != "PASS":
        raise BootstrapError("package-independent replay did not authorize roles")
    if type(package_root_fd) is not int or package_root_fd < 3:
        raise BootstrapError("retained package-root FD is invalid")
    try:
        root_stat = os.fstat(package_root_fd)
    except OSError as exc:
        raise BootstrapError("retained package-root FD cannot be inspected") from exc
    if not stat.S_ISDIR(root_stat.st_mode):
        raise BootstrapError("retained package-root FD is not a directory")

    owned: list[int] = []
    signatures: dict[int, tuple[int, ...]] = {}
    primary: BaseException | None = None
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        manifest_fd = _open_retained_package_node(
            "package-manifest.json",
            flags=flags,
            parent_fd=package_root_fd,
            label="post-verifier package manifest",
        )
        owned.append(manifest_fd)
        seal_fd = _open_retained_package_node(
            "SHA256SUMS",
            flags=flags,
            parent_fd=package_root_fd,
            label="post-verifier package seal",
        )
        owned.append(seal_fd)
        manifest_raw, signatures[manifest_fd] = _retained_package_member_bytes(
            manifest_fd,
            label="post-verifier package manifest",
            maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )
        seal_raw, signatures[seal_fd] = _retained_package_member_bytes(
            seal_fd,
            label="post-verifier package seal",
            maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )
        package_record = _exact_keys(
            package,
            {
                "manifest_identity",
                "package_dir",
                "package_id",
                "schema",
                "seal_identity",
                "status",
            },
            "post-verifier package record",
        )
        manifest_identity = authority.validate_detached_identity(
            package_record["manifest_identity"],
            "post-verifier package manifest identity",
        )
        seal_identity = authority.validate_detached_identity(
            package_record["seal_identity"],
            "post-verifier package seal identity",
        )
        if (
            manifest_identity["sha256"]
            != hashlib.sha256(manifest_raw).hexdigest()
            or manifest_identity["size_bytes"] != len(manifest_raw)
            or seal_identity["sha256"] != hashlib.sha256(seal_raw).hexdigest()
            or seal_identity["size_bytes"] != len(seal_raw)
            or package_record["package_id"]
            != hashlib.sha256(seal_raw).hexdigest()
        ):
            raise BootstrapError(
                "post-verifier package manifest/seal identity drifted"
            )

        payload_fd = _open_retained_package_node(
            "payload",
            flags=flags | os.O_DIRECTORY,
            parent_fd=package_root_fd,
            label="post-verifier package payload",
        )
        owned.append(payload_fd)
        payload_stat = os.fstat(payload_fd)
        if not stat.S_ISDIR(payload_stat.st_mode):
            raise BootstrapError("post-verifier package payload is not a directory")
        signatures[payload_fd] = _stat_signature(payload_stat)
        wrapper_fd = _open_retained_package_node(
            NATIVE_BUDGET_HELPER_WRAPPER_PACKAGE_PATH.removeprefix("payload/"),
            flags=flags,
            parent_fd=payload_fd,
            label="post-verifier native helper wrapper",
        )
        owned.append(wrapper_fd)
        binary_fd = _open_retained_package_node(
            NATIVE_BUDGET_HELPER_PACKAGE_PATH.removeprefix("payload/"),
            flags=flags,
            parent_fd=payload_fd,
            label="post-verifier native helper binary",
        )
        owned.append(binary_fd)
        wrapper_raw, signatures[wrapper_fd] = _retained_package_member_bytes(
            wrapper_fd,
            label="post-verifier native helper wrapper",
            maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
        )
        native_raw, signatures[binary_fd] = _retained_package_member_bytes(
            binary_fd,
            label="post-verifier native helper binary",
            maximum_size=NATIVE_BUDGET_HELPER_SIZE_BYTES,
        )
        if (
            hashlib.sha256(wrapper_raw).hexdigest() != wrapper_pin["sha256"]
            or len(wrapper_raw) != wrapper_pin["size_bytes"]
        ):
            raise BootstrapError(
                "post-verifier native helper wrapper bytes drifted"
            )
        _native_helper_elf_capability(
            native_raw,
            source_identity=native_source_pin,
        )
        _package_native_manifest_join(
            manifest_raw,
            wrapper_source_identity=wrapper_pin,
            native_helper_source_identity=native_manifest_pin,
            wrapper_raw=wrapper_raw,
            native_raw=native_raw,
        )

        module = types.ModuleType("_ab16_package_native_budget_helper_v1")
        module.__file__ = f"/proc/self/fd/{wrapper_fd}"
        module.__package__ = ""
        exec(
            compile(
                wrapper_raw,
                module.__file__,
                "exec",
                dont_inherit=True,
            ),
            module.__dict__,
        )
        expected_function = getattr(module, "expected_package_identity", None)
        helper_type = getattr(module, "NativeBudgetHelper", None)
        if (
            not callable(expected_function)
            or not callable(helper_type)
            or expected_function() != expected_native
        ):
            raise BootstrapError(
                "post-verifier native helper wrapper API drifted"
            )
        # The tracked wrapper retains a developer-only reproducible build
        # utility, but the authority-loaded module never exposes that surface.
        module.__dict__.pop("build_shared_object", None)
        module.__dict__.pop("subprocess", None)
        helper = helper_type(
            binary_fd,
            expected_identity=expected_native,
        )
        for descriptor, expected_signature in signatures.items():
            if _stat_signature(os.fstat(descriptor)) != expected_signature:
                raise BootstrapError(
                    "package native helper retained FD changed during load"
                )
        return PackageNativeBudgetHelperHandle(
            helper=helper,
            wrapper_module=module,
            descriptors=tuple(owned),
            signatures=signatures,
        )
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if primary is not None:
            _close_descriptors_with_primary(
                tuple(reversed(owned)),
                primary=primary,
            )


def _package_budget_runtime_source_identities(
    planned: Mapping[str, Mapping[str, object]],
) -> tuple[
    dict[str, Mapping[str, object]],
    dict[str, Mapping[str, object]],
]:
    role_sources: dict[str, Mapping[str, object]] = {}
    if set(PACKAGE_BUDGET_RUNTIME_SOURCE_KEYS) != set(
        PACKAGE_BUDGET_RUNTIME_ROLE_PATHS
    ):
        raise BootstrapError(
            "package budget role source-key vocabulary drifted"
        )
    for role, source_key in PACKAGE_BUDGET_RUNTIME_SOURCE_KEYS.items():
        try:
            role_sources[role] = planned[source_key]
        except KeyError as exc:
            raise BootstrapError(
                f"package budget role lacks its planned source: {role}"
            ) from exc
    selected_keys = {
        "authority": "script.ab16_authority_v2",
        "loader": "script.ab16_formal_loader_v1",
        "native_helper": "system.native_budget_helper",
        "native_helper_wrapper": "script.ab16_native_budget_helper_v1",
        "python": "system.python3_13",
    }
    try:
        selected_sources = {
            role: planned[source_key]
            for role, source_key in selected_keys.items()
        }
    except KeyError as exc:
        raise BootstrapError(
            "package selected-FD transport lacks one planned source"
        ) from exc
    return role_sources, selected_sources


def _validate_packaged_resource_calibration_bundles(
    *,
    package_root_fd: int,
    package_authorization: RetainedPackageBudgetRoleAuthorization,
    expected_identities: Mapping[str, object],
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    budget_profile: Mapping[str, object],
    budget_profile_identity: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Use only package bytes and the package-pinned admission validator."""

    checked_identities = _validate_resource_calibration_bundle_identities(
        expected_identities,
        label="packaged resource calibration bundles",
    )
    admission = package_authorization.load_verified_role(
        "ab16-resource-admission-v1"
    )
    validate_bundle = getattr(
        admission,
        "validate_calibration_authorization_bundle",
        None,
    )
    stage_profile = getattr(
        admission,
        "_validated_prospective_profile",
        None,
    )
    if not callable(validate_bundle) or not callable(stage_profile):
        raise BootstrapError(
            "package resource-admission calibration API is incomplete"
        )
    detached_budget_profile_identity = {
        field: budget_profile_identity[field]
        for field in ("path", "sha256", "size_bytes")
    }
    payload_fd = -1
    owned: list[int] = []
    signatures: dict[int, tuple[int, ...]] = {}
    primary: BaseException | None = None
    validated: dict[str, dict[str, object]] = {}
    try:
        payload_fd = _open_retained_package_node(
            "payload",
            flags=(
                os.O_RDONLY
                | os.O_CLOEXEC
                | os.O_NOFOLLOW
                | os.O_DIRECTORY
            ),
            parent_fd=package_root_fd,
            label="resource calibration package payload",
        )
        owned.append(payload_fd)
        payload_stat = os.fstat(payload_fd)
        if not stat.S_ISDIR(payload_stat.st_mode):
            raise BootstrapError(
                "resource calibration package payload is not a directory"
            )
        signatures[payload_fd] = _stat_signature(payload_stat)
        for stage in RESOURCE_CALIBRATION_STAGES:
            role = RESOURCE_CALIBRATION_INPUT_ROLES[stage]
            descriptor = _open_retained_package_node(
                f"input.{role}.json",
                flags=os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                parent_fd=payload_fd,
                label=f"{stage} packaged resource calibration bundle",
            )
            owned.append(descriptor)
            raw, signatures[descriptor] = _retained_package_member_bytes(
                descriptor,
                label=f"{stage} packaged resource calibration bundle",
                maximum_size=PACKAGE_INDEPENDENT_REPLAY_MAX_BYTES,
            )
            identity = checked_identities[stage]
            if (
                identity["sha256"] != hashlib.sha256(raw).hexdigest()
                or identity["size_bytes"] != len(raw)
            ):
                raise BootstrapError(
                    f"{stage} packaged resource calibration bytes drifted"
                )
            record = authority.strict_loads(
                raw,
                f"{stage} packaged resource calibration bundle",
            )
            if authority.canonical_json(record) != raw:
                raise BootstrapError(
                    f"{stage} packaged resource calibration is not canonical"
                )
            if stage == "FORMAL_ORGANIC_ARM":
                expected_profile = stage_profile(
                    stage,
                    enforced_budget_profile=budget_profile,
                    enforced_budget_profile_identity=(
                        detached_budget_profile_identity
                    ),
                )
            else:
                expected_profile = stage_profile(
                    stage,
                    enforced_budget_profile=None,
                    enforced_budget_profile_identity=None,
                )
            try:
                checked_record = validate_bundle(
                    record,
                    bundle_identity=identity,
                    stage=stage,
                    expected_profile=expected_profile,
                    expected_calibration_tool_identities=(
                        expected_calibration_tool_identities
                    ),
                )
            except BaseException as exc:
                raise BootstrapError(
                    f"{stage} package calibration authorization failed closed"
                ) from exc
            if checked_record != record:
                raise BootstrapError(
                    f"{stage} package calibration validator result drifted"
                )
            validated[stage] = {
                "identity": dict(identity),
                "record": dict(checked_record),
            }
        for descriptor, signature in signatures.items():
            if _stat_signature(os.fstat(descriptor)) != signature:
                raise BootstrapError(
                    "packaged resource calibration retained FD drifted"
                )
        return validated
    except BaseException as exc:
        primary = exc
        raise
    finally:
        _close_descriptors_with_primary(
            tuple(reversed(owned)),
            primary=primary,
        )


class _TransferredFormalBudgetOwnership:
    """Own one exact, not-yet-consumed persistent-broker transfer cohort."""

    def __init__(
        self,
        *,
        account: Any,
        account_handoff: Mapping[str, object],
        reservations: Mapping[str, Any],
        reservation_handoffs: Mapping[str, Mapping[str, object]],
        control_parent: Any,
        control_parent_handoff: Mapping[str, object],
        final_release_parent: Any,
        final_release_parent_handoff: Mapping[str, object],
        broker_module: Any,
        owner_nonce: str,
    ) -> None:
        self.account = account
        self.account_handoff = dict(account_handoff)
        self.reservations = dict(reservations)
        self.reservation_handoffs = {
            purpose: dict(record)
            for purpose, record in reservation_handoffs.items()
        }
        self.control_parent = control_parent
        self.control_parent_handoff = dict(control_parent_handoff)
        self.final_release_parent = final_release_parent
        self.final_release_parent_handoff = dict(
            final_release_parent_handoff
        )
        self.broker_module = broker_module
        self.owner_nonce = owner_nonce
        self._consumed = False
        self._closed = False

    def mark_consumed(self) -> None:
        if self._closed or self._consumed:
            raise BootstrapError(
                "formal budget ownership transfer cannot be consumed twice"
            )
        self._consumed = True

    def close_incomplete(self, *, reason: str) -> None:
        if self._consumed:
            return
        if self._closed:
            raise BootstrapError(
                "formal budget ownership transfer cannot close twice"
            )
        self._closed = True
        primary: BaseException | None = None
        seal_abandoned = getattr(
            self.broker_module,
            "_seal_abandoned_reservation",
            None,
        )
        for purpose, reservation in tuple(self.reservations.items()):
            try:
                if not callable(seal_abandoned):
                    raise BootstrapError(
                        "package broker lacks abandoned-reservation closeout"
                    )
                seal_abandoned(purpose, reservation, reason=reason)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"{purpose} reservation closeout also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        for label, owned in (
            ("formal control parent", self.control_parent),
            ("outside final-release parent", self.final_release_parent),
            ("formal budget account", self.account),
        ):
            try:
                owned.close()
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"{label} cleanup also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary


class _PersistentBootstrapBudgetOwner:
    """Retain the sole bootstrap-admin connection and broker pidfd."""

    def __init__(
        self,
        *,
        process: Any,
        admin: Any,
    ) -> None:
        self.process = process
        self.admin = admin
        self._closed = False
        self._formal_launch_owner_handoff: dict[str, object] | None = None
        self._formal_launch_owner_pidfd = -1
        self._formal_launch_owner_confirmed = False

    def authorize_formal_launch_owner(
        self,
        *,
        expected_peer: Mapping[str, object],
        pidfd: int,
        formal_budget_runtime: Mapping[str, object],
    ) -> dict[str, object]:
        """Register the package-pinned delayed owner exactly once."""

        if (
            self._closed
            or self._formal_launch_owner_handoff is not None
            or self.process is None
            or self.admin is None
        ):
            raise BootstrapError(
                "formal-launch owner handoff is duplicate or owner is closed"
            )
        peer = _exact_keys(
            expected_peer,
            {"pid", "pid_starttime", "uid"},
            "formal-launch owner peer",
        )
        if any(
            isinstance(peer[field], bool)
            or not isinstance(peer[field], int)
            for field in ("pid", "pid_starttime", "uid")
        ) or (
            peer["pid"] <= 0
            or peer["pid_starttime"] <= 0
            or peer["uid"] != os.getuid()
        ):
            raise BootstrapError(
                "formal-launch owner peer identity is invalid"
            )
        runtime = _exact_keys(
            formal_budget_runtime,
            {
                "broker_actor_identity",
                "broker_endpoint_identity",
                "broker_nonce",
                "formal_budget_handoff_identity",
                "formal_root_contract_identity",
                "package_independent_replay_identity",
                "recovery_actor_identity",
                "recovery_extent_identity",
            },
            "formal-launch owner budget runtime",
        )
        actor = {
            "schema_version": "noncert-cuts-ab16-budget-broker-actor-v1",
            **dict(self.process.actor),
        }
        if (
            runtime["broker_actor_identity"]
            != dict(self.process.actor)
            or runtime["broker_endpoint_identity"]
            != dict(self.process.endpoint_identity)
            or runtime["broker_nonce"] != self.process.nonce
        ):
            raise BootstrapError(
                "formal-launch owner budget runtime differs from broker"
            )
        credential = secrets.token_hex(32)
        owned_pidfd = os.dup(pidfd)
        try:
            response = self.admin.register_bound_nonarm_grant(
                {
                    "credential": credential,
                    "expected_peer": dict(peer),
                    "role": "formal-launch-owner",
                },
                pidfd=pidfd,
            )
            grant = response.record.get("result")
            if (
                type(grant) is not dict
                or grant.get("role") != "formal-launch-owner"
                or grant.get("expected_peer") != peer
                or grant.get("credential_sha256")
                != hashlib.sha256(
                    credential.encode("ascii")
                ).hexdigest()
            ):
                raise BootstrapError(
                    "formal-launch owner broker grant drifted"
                )
            handoff = {
                "broker_actor": actor,
                "broker_endpoint_identity": dict(
                    self.process.endpoint_identity
                ),
                "broker_nonce": self.process.nonce,
                "credential": credential,
                "formal_budget_runtime": dict(runtime),
                "grant": dict(grant),
                "schema_version": (
                    "noncert-cuts-ab16-formal-launch-owner-"
                    "broker-handoff-v1"
                ),
                "state": "PREREGISTERED_LIVE_OWNER",
                "transport_only": True,
            }
            self._formal_launch_owner_handoff = handoff
            self._formal_launch_owner_pidfd = owned_pidfd
            owned_pidfd = -1
            return dict(handoff)
        finally:
            if owned_pidfd >= 0:
                os.close(owned_pidfd)

    def confirm_formal_launch_owner_session(self) -> dict[str, object]:
        """Require the exact peer to consume and retain the registered grant."""

        handoff = self._formal_launch_owner_handoff
        if (
            self._closed
            or handoff is None
            or self._formal_launch_owner_confirmed
            or self._formal_launch_owner_pidfd < 0
        ):
            raise BootstrapError(
                "formal-launch owner confirmation state drifted"
            )
        poller = select.poll()
        poller.register(self._formal_launch_owner_pidfd, select.POLLIN)
        if poller.poll(0):
            raise BootstrapError(
                "formal-launch owner exited before broker confirmation"
            )
        grant = cast(Mapping[str, object], handoff["grant"])
        response = self.admin.request(
            "CONFIRM_BOUND_NONARM_SESSION",
            {
                "credential_sha256": grant["credential_sha256"],
                "expected_peer": grant["expected_peer"],
                "role": "formal-launch-owner",
            },
        )
        result = response.record.get("result")
        if (
            type(result) is not dict
            or result
            != {
                "credential_sha256": grant["credential_sha256"],
                "expected_peer": grant["expected_peer"],
                "role": "formal-launch-owner",
                "state": "EXACT_OWNER_SESSION_LIVE",
            }
        ):
            raise BootstrapError(
                "formal-launch owner broker confirmation drifted"
            )
        self._formal_launch_owner_confirmed = True
        return dict(result)

    def confirm_broker_hosted_formal_launch_owner(
        self,
        handoff: Mapping[str, object],
    ) -> dict[str, object]:
        """Adopt the broker-spawned package actor without persisting its token."""

        if (
            self._closed
            or self._formal_launch_owner_handoff is not None
            or self._formal_launch_owner_confirmed
        ):
            raise BootstrapError(
                "broker-hosted formal-launch owner adoption is duplicate"
            )
        record = _exact_keys(
            handoff,
            {
                "broker_actor",
                "broker_endpoint_identity",
                "broker_nonce",
                "context_state",
                "credential",
                "grant",
                "owner_actor",
                "owner_pidfd_method",
                "owner_role_source_identity",
                "ready",
                "registration_confirmation",
                "schema_version",
                "state",
                "transport_only",
            },
            "broker-hosted formal-launch owner handoff",
        )
        grant = cast(Mapping[str, object], record["grant"])
        owner_actor = cast(
            Mapping[str, object],
            record["owner_actor"],
        )
        if (
            record["schema_version"]
            != (
                "noncert-cuts-ab16-formal-launch-owner-"
                "broker-handoff-v1"
            )
            or record["state"] != "PREREGISTERED_LIVE_OWNER"
            or record["context_state"] != "AWAITING_DELAYED_CONTEXT"
            or record["transport_only"] is not True
            or record["broker_actor"]
            != {
                "schema_version": (
                    "noncert-cuts-ab16-budget-broker-actor-v1"
                ),
                **dict(self.process.actor),
            }
            or record["broker_endpoint_identity"]
            != dict(self.process.endpoint_identity)
            or record["broker_nonce"] != self.process.nonce
            or type(record["credential"]) is not str
            or grant.get("credential_sha256")
            != hashlib.sha256(
                record["credential"].encode("ascii")
            ).hexdigest()
            or grant.get("role") != "formal-launch-owner"
            or grant.get("expected_peer")
            != {
                "pid": owner_actor.get("pid"),
                "pid_starttime": owner_actor.get("starttime"),
                "uid": os.getuid(),
            }
            or record["registration_confirmation"]
            != {
                "credential_sha256": grant.get(
                    "credential_sha256"
                ),
                "expected_peer": grant.get("expected_peer"),
                "role": "formal-launch-owner",
                "state": "EXACT_OWNER_SESSION_LIVE",
            }
            or owner_actor.get("starttime")
            != _proc_starttime(cast(int, owner_actor.get("pid")))
        ):
            raise BootstrapError(
                "broker-hosted formal-launch owner handoff drifted"
            )
        self._formal_launch_owner_handoff = dict(record)
        self._formal_launch_owner_confirmed = True
        return {
            "context_state": record["context_state"],
            "credential_sha256": grant["credential_sha256"],
            "grant": dict(grant),
            "owner_actor": dict(owner_actor),
            "owner_pidfd_method": record["owner_pidfd_method"],
            "owner_role_source_identity": record[
                "owner_role_source_identity"
            ],
            "ready": record["ready"],
            "registration_confirmation": record[
                "registration_confirmation"
            ],
            "schema_version": record["schema_version"],
            "state": "BROKER_HOSTED_OWNER_RETAINED",
        }

    def _close_formal_launch_owner_pidfd_preserving(
        self,
        primary: BaseException | None,
    ) -> None:
        descriptor = self._formal_launch_owner_pidfd
        self._formal_launch_owner_pidfd = -1
        if descriptor < 0:
            return
        try:
            os.close(descriptor)
        except BaseException as cleanup_error:
            if primary is None:
                raise
            primary.add_note(
                "formal-launch owner pidfd cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )

    def _close_pidfd_preserving(
        self,
        primary: BaseException | None,
    ) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            process.close()
        except BaseException as cleanup_error:
            if primary is None:
                raise
            primary.add_note(
                "persistent broker pidfd cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )

    def close_success(self) -> None:
        if self._closed:
            raise BootstrapError(
                "bootstrap persistent budget owner cannot close twice"
            )
        self._closed = True
        if not self._formal_launch_owner_confirmed:
            self._closed = False
            raise BootstrapError(
                "bootstrap cannot close before formal-launch owner handoff"
            )
        primary: BaseException | None = None
        admin = self.admin
        self.admin = None
        try:
            admin.close_session()
        except BaseException as exc:
            primary = exc
        try:
            self._close_pidfd_preserving(primary)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "persistent broker pidfd cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        try:
            self._close_formal_launch_owner_pidfd_preserving(primary)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "formal-launch owner pidfd cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        if primary is not None:
            raise primary

    def abort_markerless(
        self,
        *,
        failure_identity: Mapping[str, object],
        reason_sha256: str,
    ) -> dict[str, object]:
        if self._closed:
            raise BootstrapError(
                "bootstrap persistent budget owner cannot abort twice"
            )
        self._closed = True
        primary: BaseException | None = None
        result: dict[str, object] | None = None
        admin = self.admin
        self.admin = None
        process = self.process
        try:
            response = admin.request(
                "ABORT_BOOTSTRAP_INCOMPLETE",
                {
                    "bootstrap_failure_identity": dict(failure_identity),
                    "reason_sha256": reason_sha256,
                    "state": "markerless-incomplete",
                },
                expected_fd_counts=frozenset({0}),
            )
            raw_result = response.record.get("result")
            expected_fields = {
                "abandoned_fixed_reservations",
                "bootstrap_failure_identity",
                "prior_handoff_state",
                "recovery_handoff_identity",
                "recovery_lock_release",
                "recovery_terminal",
                "state",
            }
            if (
                type(raw_result) is not dict
                or set(raw_result) != expected_fields
                or raw_result["state"] != "MARKERLESS_BOOTSTRAP_ABORTED"
                or raw_result["bootstrap_failure_identity"]
                != dict(failure_identity)
                or raw_result["prior_handoff_state"]
                not in {"PENDING", "PUBLISHED"}
                or type(raw_result["abandoned_fixed_reservations"])
                is not dict
                or set(raw_result["abandoned_fixed_reservations"])
                != set(_FORMAL_FIXED_RESERVATION_CONTRACT)
                or any(
                    record
                    != {
                        "state": (
                            "STAGING_SEALED_WITHOUT_REFUND_OR_REUSE"
                        )
                    }
                    for record in raw_result[
                        "abandoned_fixed_reservations"
                    ].values()
                )
            ):
                raise BootstrapError(
                    "persistent broker bootstrap-abort result drifted"
                )
            result = dict(raw_result)
        except BaseException as exc:
            primary = exc
        finally:
            try:
                admin.close()
            except BaseException as cleanup_error:
                if primary is None:
                    primary = cleanup_error
                else:
                    primary.add_note(
                        "bootstrap admin abort cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
        if primary is None:
            try:
                exit_code = process.wait()
                if exit_code != 0:
                    raise BootstrapError(
                        "persistent broker bootstrap abort exited nonzero"
                    )
            except BaseException as exc:
                primary = exc
        else:
            try:
                signal.pidfd_send_signal(
                    process.pidfd,
                    signal.SIGTERM,
                )
                process.wait()
            except BaseException as cleanup_error:
                primary.add_note(
                    "persistent broker forced abort also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        try:
            self._close_pidfd_preserving(primary)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "persistent broker pidfd cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        if primary is not None:
            raise primary
        assert result is not None
        return result

    def terminate_unpublished_incomplete(self) -> None:
        """Stop the exact child when no failure identity can authorize abort."""

        if self._closed:
            raise BootstrapError(
                "bootstrap persistent budget owner cannot terminate twice"
            )
        self._closed = True
        primary: BaseException | None = None
        admin = self.admin
        self.admin = None
        process = self.process
        try:
            admin.close()
        except BaseException as exc:
            primary = exc
        try:
            signal.pidfd_send_signal(process.pidfd, signal.SIGTERM)
            process.wait()
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "persistent broker exact-child termination also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        try:
            self._close_pidfd_preserving(primary)
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "persistent broker pidfd cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
        if primary is not None:
            raise primary


def _attach_persistent_bootstrap_budget_owner(
    owner: _PersistentBootstrapBudgetOwner,
) -> None:
    active = _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME
    if active is None or "persistent_owner" in active:
        raise BootstrapError(
            "bootstrap persistent budget owner attachment drifted"
        )
    active["persistent_owner"] = owner


def _transfer_formal_budget_runtime(
    *,
    budget_runtime: Mapping[str, object],
    broker_module: Any,
    owner_nonce: str,
) -> _TransferredFormalBudgetOwnership:
    if (
        not isinstance(owner_nonce, str)
        or len(owner_nonce) != 64
        or any(character not in "0123456789abcdef" for character in owner_nonce)
    ):
        raise BootstrapError("persistent broker owner nonce is malformed")
    formal_broker = cast(Any, budget_runtime["formal_broker"])
    raw_reservations = budget_runtime["formal_reservations"]
    control_parent = cast(
        Any,
        budget_runtime["control_parent_capability"],
    )
    final_release_parent = cast(
        Any,
        budget_runtime["final_release_parent_capability"],
    )
    if (
        not isinstance(raw_reservations, Mapping)
        or set(raw_reservations) != set(_FORMAL_FIXED_RESERVATION_CONTRACT)
    ):
        raise BootstrapError("formal fixed-purpose reservation set drifted")
    typed_reservations = cast(Mapping[str, Any], raw_reservations)

    account: Any | None = None
    account_handoff: Mapping[str, object] | None = None
    reservations: dict[str, Any] = {}
    reservation_handoffs: dict[str, Mapping[str, object]] = {}
    transferred_control: Any | None = None
    control_handoff: Mapping[str, object] | None = None
    transferred_final_release: Any | None = None
    final_release_handoff: Mapping[str, object] | None = None
    primary: BaseException | None = None
    try:
        account, account_handoff = formal_broker.transfer_ownership(
            to_owner_nonce=owner_nonce,
        )
        for purpose, reservation in sorted(typed_reservations.items()):
            successor, handoff = reservation.transfer_ownership(
                to_owner_nonce=owner_nonce,
            )
            reservations[purpose] = successor
            reservation_handoffs[purpose] = handoff
        transferred_control, control_handoff = control_parent.transfer_ownership(
            to_owner_nonce=owner_nonce,
        )
        transferred_final_release, final_release_handoff = (
            final_release_parent.transfer_ownership(
                to_owner_nonce=owner_nonce,
            )
        )
        return _TransferredFormalBudgetOwnership(
            account=account,
            account_handoff=account_handoff,
            reservations=reservations,
            reservation_handoffs=reservation_handoffs,
            control_parent=transferred_control,
            control_parent_handoff=control_handoff,
            final_release_parent=transferred_final_release,
            final_release_parent_handoff=final_release_handoff,
            broker_module=broker_module,
            owner_nonce=owner_nonce,
        )
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if primary is not None:
            for purpose, reservation in tuple(reservations.items()):
                try:
                    seal = getattr(
                        broker_module,
                        "_seal_abandoned_reservation",
                    )
                    seal(
                        purpose,
                        reservation,
                        reason="bootstrap formal ownership transfer failed",
                    )
                except BaseException as cleanup_error:
                    primary.add_note(
                        f"{purpose} transferred reservation cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            for purpose, reservation in sorted(typed_reservations.items()):
                if purpose in reservations:
                    continue
                try:
                    seal = getattr(
                        broker_module,
                        "_seal_abandoned_reservation",
                    )
                    seal(
                        purpose,
                        reservation,
                        reason="bootstrap formal ownership transfer failed",
                    )
                except BaseException as cleanup_error:
                    primary.add_note(
                        f"{purpose} source reservation cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            for label, owned in (
                (
                    "formal control parent",
                    (
                        transferred_control
                        if transferred_control is not None
                        else control_parent
                    ),
                ),
                (
                    "outside final-release parent",
                    (
                        transferred_final_release
                        if transferred_final_release is not None
                        else final_release_parent
                    ),
                ),
                ("transferred formal budget account", account),
            ):
                if owned is None:
                    continue
                try:
                    cast(Any, owned).close()
                except BaseException as cleanup_error:
                    primary.add_note(
                        f"{label} cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )


def _load_package_budget_broker_role(
    package_authorization: RetainedPackageBudgetRoleAuthorization,
) -> object:
    global authority
    loaded = {
        role: package_authorization.load_verified_role(role)
        for role in PACKAGE_BUDGET_RUNTIME_LOAD_ORDER
    }
    if set(loaded) != set(PACKAGE_BUDGET_RUNTIME_ROLE_PATHS):
        raise BootstrapError(
            "retained package role load order did not cover the full cohort"
        )
    # This is the sole authority transition: the source was externally pinned,
    # copied into the package, independently replayed, then executed from its
    # retained package FD.  No repository/worktree module is accepted here.
    authority = loaded["campaign-authority-v4"]
    return loaded["ab16-budget-broker-v1"]


def _bootstrap_persistent_budget_runtime(
    *,
    budget_runtime: Mapping[str, object],
    budget_profile: Mapping[str, object],
    budget_profile_identity: Mapping[str, object],
    resource_calibration_bundle_identities: Mapping[str, object],
    calibration_tool_content_identities: Mapping[
        str, Mapping[str, object]
    ],
    package_root_fd: int,
    replay_authorization: VerifiedPackageIndependentReplay,
    package: Mapping[str, object],
    verifier_source_identity: Mapping[str, object],
    native_helper_source_identity: Mapping[str, object],
    planned: Mapping[str, Mapping[str, object]],
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
    endpoint_path: Path,
    bootstrap_handoff_spec: Mapping[str, object],
    formal_root_budget_contract_identity: Mapping[str, object],
    bootstrap_failure_closeout_path: Path,
) -> dict[str, object]:
    """Cross package PASS into one persistent broker and armed recovery actor."""

    role_sources, selected_sources = _package_budget_runtime_source_identities(
        planned
    )
    package_authorization: RetainedPackageBudgetRoleAuthorization | None = None
    native_authorization: PackageNativeBudgetHelperHandle | None = None
    transferred: _TransferredFormalBudgetOwnership | None = None
    adopted_unwrapped: Mapping[str, object] | None = None
    structural_fds: tuple[int, ...] = ()
    process: Any | None = None
    admin: Any | None = None
    owner: _PersistentBootstrapBudgetOwner | None = None
    primary: BaseException | None = None
    owner_nonce = secrets.token_hex(32)
    spawn_succeeded = False
    try:
        package_authorization = open_verified_package_budget_roles(
            package_root_fd=package_root_fd,
            independent_replay_fd=replay_authorization.fileno(),
            independent_replay_identity=replay_authorization.identity,
            package=package,
            independent_result=replay_authorization.result,
            verifier_source_identity=verifier_source_identity,
            native_helper_source_identity=native_helper_source_identity,
            role_source_identities=role_sources,
            selected_source_identities=selected_sources,
            repository_head=repository_head,
            run_nonce=run_nonce,
            manager_epoch=manager_epoch,
        )
        native_authorization = open_verified_package_native_budget_helper(
            package_root_fd=package_root_fd,
            package=package,
            independent_result=replay_authorization.result,
            verifier_source_identity=verifier_source_identity,
            wrapper_source_identity=planned[
                "script.ab16_native_budget_helper_v1"
            ],
            native_helper_source_identity=native_helper_source_identity,
            repository_head=repository_head,
            run_nonce=run_nonce,
            manager_epoch=manager_epoch,
        )
        resource_calibration_authorization_bundles = (
            _validate_packaged_resource_calibration_bundles(
                package_root_fd=package_root_fd,
                package_authorization=package_authorization,
                expected_identities=(
                    resource_calibration_bundle_identities
                ),
                expected_calibration_tool_identities=(
                    calibration_tool_content_identities
                ),
                budget_profile=budget_profile,
                budget_profile_identity=budget_profile_identity,
            )
        )
        broker_module = _load_package_budget_broker_role(
            package_authorization
        )
        structural_handoff, structural_fds = (
            _export_bootstrap_structural_handoff(
                budget_runtime=budget_runtime,
                replay_authorization=replay_authorization,
                to_owner_nonce=owner_nonce,
            )
        )
        adopt_structural = cast(
            Any,
            getattr(
                broker_module,
                "adopt_bootstrap_structural_handoff",
                None,
            ),
        )
        if not callable(adopt_structural):
            raise BootstrapError(
                "package budget broker structural adoption API is incomplete"
            )
        adopted = adopt_structural(
            structural_handoff,
            structural_fds,
            expected_owner_nonce=owner_nonce,
        )
        adopted_record = _exact_keys(
            adopted,
            {
                "account",
                "account_handoff",
                "control_parent",
                "control_parent_handoff",
                "final_release_parent",
                "final_release_parent_handoff",
                "reservations",
                "reservation_handoffs",
            },
            "package broker structural adoption result",
        )
        adopted_unwrapped = adopted_record
        broker_reservation_purposes = (
            set(_FORMAL_FIXED_RESERVATION_CONTRACT)
            - set(OUTSIDE_FINAL_RELEASE_RESERVATIONS)
        )
        if (
            not isinstance(adopted_record["account_handoff"], Mapping)
            or not isinstance(adopted_record["control_parent_handoff"], Mapping)
            or not isinstance(
                adopted_record["final_release_parent_handoff"],
                Mapping,
            )
            or not isinstance(adopted_record["reservations"], Mapping)
            or not isinstance(
                adopted_record["reservation_handoffs"],
                Mapping,
            )
            or set(adopted_record["reservations"])
            != broker_reservation_purposes
            or set(adopted_record["reservation_handoffs"])
            != broker_reservation_purposes
        ):
            raise BootstrapError(
                "package broker structural adoption cohort drifted"
            )
        transferred = _TransferredFormalBudgetOwnership(
            account=adopted_record["account"],
            account_handoff=cast(
                Mapping[str, object],
                adopted_record["account_handoff"],
            ),
            reservations=cast(
                Mapping[str, Any],
                adopted_record["reservations"],
            ),
            reservation_handoffs=cast(
                Mapping[str, Mapping[str, object]],
                adopted_record["reservation_handoffs"],
            ),
            control_parent=adopted_record["control_parent"],
            control_parent_handoff=cast(
                Mapping[str, object],
                adopted_record["control_parent_handoff"],
            ),
            final_release_parent=adopted_record[
                "final_release_parent"
            ],
            final_release_parent_handoff=cast(
                Mapping[str, object],
                adopted_record["final_release_parent_handoff"],
            ),
            broker_module=broker_module,
            owner_nonce=owner_nonce,
        )
        adopted_unwrapped = None
        owned_structural_fds = structural_fds
        structural_fds = ()
        _close_descriptors_with_primary(
            owned_structural_fds,
            primary=None,
        )
        validate_account = cast(
            Any,
            getattr(
            broker_module,
            "validate_transferred_account",
            None,
            ),
        )
        validate_reservations = cast(
            Any,
            getattr(
            broker_module,
            "validate_transferred_reservations",
            None,
            ),
        )
        validate_control = cast(
            Any,
            getattr(
            broker_module,
            "validate_transferred_control_parent",
            None,
            ),
        )
        validate_final_release = cast(
            Any,
            getattr(
                broker_module,
                "validate_transferred_final_release_parent",
                None,
            ),
        )
        spawn = cast(
            Any,
            getattr(
            broker_module,
            "spawn_persistent_broker_from_transfer",
            None,
            ),
        )
        if not all(
            callable(entrypoint)
            for entrypoint in (
                validate_account,
                validate_reservations,
                validate_control,
                validate_final_release,
                spawn,
            )
        ):
            raise BootstrapError(
                "package budget broker ownership API is incomplete"
            )
        validate_account(
            transferred.account,
            transferred.account_handoff,
            expected_owner_nonce=owner_nonce,
        )
        validate_reservations(
            transferred.account,
            transferred.reservations,
            transferred.reservation_handoffs,
            expected_owner_nonce=owner_nonce,
        )
        validate_control(
            transferred.account,
            transferred.control_parent,
            transferred.control_parent_handoff,
            expected_owner_nonce=owner_nonce,
            endpoint_path=endpoint_path,
        )
        validate_final_release(
            transferred.account,
            transferred.final_release_parent,
            transferred.final_release_parent_handoff,
            expected_owner_nonce=owner_nonce,
            expected_parent_path=transferred.final_release_parent.path,
        )
        formal_root_profile = cast(
            Mapping[str, Any],
            budget_profile["formal_root"],
        )
        formal_directories = tuple(
            dict(item)
            for item in formal_root_profile["fixed_directories"]
            if item["path"] != "."
        )
        process = spawn(
            account=transferred.account,
            ownership_handoff=transferred.account_handoff,
            fixed_purpose_reservations=transferred.reservations,
            fixed_purpose_handoffs=transferred.reservation_handoffs,
            control_parent_capability=transferred.control_parent,
            control_parent_handoff=transferred.control_parent_handoff,
            final_release_parent_capability=(
                transferred.final_release_parent
            ),
            final_release_parent_handoff=(
                transferred.final_release_parent_handoff
            ),
            endpoint_path=endpoint_path,
            owner_nonce=owner_nonce,
            package_authorization=package_authorization,
            native_helper_authorization=native_authorization,
            bootstrap_handoff_spec=bootstrap_handoff_spec,
            formal_root_budget_contract_identity=(
                formal_root_budget_contract_identity
            ),
            package_id=package["package_id"],
            campaign_run_nonce=run_nonce,
            formal_resource_calibration_bundle_identity=(
                resource_calibration_authorization_bundles[
                    "FORMAL_ORGANIC_ARM"
                ]["identity"]
            ),
            resource_budget_profile_identity=budget_profile_identity,
            resource_calibration_authorization_bundles=(
                resource_calibration_authorization_bundles
            ),
            calibration_tool_content_identities=(
                calibration_tool_content_identities
            ),
            bootstrap_failure_closeout_path=(
                bootstrap_failure_closeout_path
            ),
            formal_directories=formal_directories,
            arm_directories={},
            formal_artifact_contracts=tuple(
                cast(
                    Sequence[Mapping[str, object]],
                    formal_root_profile["artifact_maxima"],
                )
            ),
            formal_append_contracts=tuple(
                cast(
                    Sequence[Mapping[str, object]],
                    formal_root_profile["append_channels"],
                )
            ),
            arm_artifact_contracts=cast(
                Mapping[
                    str, Mapping[str, Mapping[str, object]]
                ],
                formal_root_profile["arm_artifact_caps"],
            ),
            arm_append_contracts=cast(
                Mapping[
                    str, Sequence[Mapping[str, object]]
                ],
                formal_root_profile["arm_append_channels"],
            ),
        )
        spawn_succeeded = True
        transferred.mark_consumed()
        package_authorization = None
        native_authorization = None
        admin = process.connect_bootstrap_admin()
        owner = _PersistentBootstrapBudgetOwner(
            process=process,
            admin=admin,
        )
        _attach_persistent_bootstrap_budget_owner(owner)
        process = None
        admin = None
        recovery = owner.admin.request(
            "PREPARE_RECOVERY",
            {},
            expected_fd_counts=frozenset({0}),
        )
        recovery_result = recovery.record.get("result")
        expected_recovery_fields = {
            "actor",
            "broker_actor",
            "control_owner",
            "pidfd_method",
            "prepared_recovery_identity",
            "role",
            "role_source_identity",
            "schema_version",
            "state",
        }
        if (
            type(recovery_result) is not dict
            or set(recovery_result) != expected_recovery_fields
            or recovery_result["schema_version"]
            != "noncert-cuts-ab16-recovery-owner-observation-v2"
            or recovery_result["state"] != "BROKER_RETAINED_CONTROL"
            or recovery_result["control_owner"] != "persistent-budget-broker"
            or recovery_result["broker_actor"] != owner.process.actor
            or recovery_result["role"] != "ab16-recovery-closeout-v1"
        ):
            raise BootstrapError(
                "package-pinned recovery owner observation drifted"
            )
        formal_calibration_envelope = cast(
            Mapping[str, object],
            resource_calibration_authorization_bundles[
                "FORMAL_ORGANIC_ARM"
            ],
        )
        formal_calibration_identity = cast(
            Mapping[str, object],
            formal_calibration_envelope["identity"],
        )
        handoff = {
            "authority": dict(_BUDGET_FALSE_AUTHORITY),
            "formal_account_handoff": dict(
                transferred.account_handoff
            ),
            "formal_control_parent_handoff": dict(
                transferred.control_parent_handoff
            ),
            "formal_final_release_parent_handoff": dict(
                transferred.final_release_parent_handoff
            ),
            "formal_reservation_handoffs": {
                purpose: dict(record)
                for purpose, record in sorted(
                    transferred.reservation_handoffs.items()
                )
            },
            "formal_root_budget_contract_identity": dict(
                formal_root_budget_contract_identity
            ),
            "formal_resource_calibration_bundle_identity": dict(
                formal_calibration_identity
            ),
            "resource_budget_profile_identity": dict(
                budget_profile_identity
            ),
            "calibration_tool_content_identities": {
                role: dict(identity)
                for role, identity in sorted(
                    calibration_tool_content_identities.items()
                )
            },
            "package_id": package["package_id"],
            "recovery_owner_observation": dict(recovery_result),
            "resource_calibration_authorization_bundles": {
                stage: {
                    "identity": dict(
                        cast(Mapping[str, object], envelope["identity"])
                    ),
                    "record": dict(
                        cast(Mapping[str, object], envelope["record"])
                    ),
                }
                for stage, envelope in sorted(
                    resource_calibration_authorization_bundles.items()
                )
            },
            "run_nonce": run_nonce,
            "schema_version": FORMAL_ROOT_BUDGET_HANDOFF_SCHEMA,
            "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
            "status": "PASS",
        }
        handoff_response = owner.admin.request(
            "PUBLISH_BOOTSTRAP_HANDOFF",
            handoff,
            expected_fd_counts=frozenset({0}),
        )
        handoff_result = handoff_response.record.get("result")
        expected_handoff_path = (
            Path(str(formal_root_budget_contract_identity["path"])).parent
            / str(bootstrap_handoff_spec["relative_path"])
        )
        expected_handoff_message_identity = {
            "sha256": hashlib.sha256(
                _budget_canonical_json(handoff)
            ).hexdigest(),
            "size_bytes": len(_budget_canonical_json(handoff)),
        }
        if (
            type(handoff_result) is not dict
            or set(handoff_result)
            != {"handoff_identity", "handoff_message_identity"}
            or handoff_result["handoff_message_identity"]
            != expected_handoff_message_identity
            or type(handoff_result["handoff_identity"]) is not dict
            or set(handoff_result["handoff_identity"])
            != {"path", "sha256", "size_bytes"}
            or Path(handoff_result["handoff_identity"]["path"])
            != expected_handoff_path
            or handoff_result["handoff_identity"]["sha256"]
            != expected_handoff_message_identity["sha256"]
            or handoff_result["handoff_identity"]["size_bytes"]
            != expected_handoff_message_identity["size_bytes"]
        ):
            raise BootstrapError(
                "persistent broker bootstrap handoff result drifted"
            )
        status = owner.admin.request("STATUS", {}).record.get("result")
        if (
            type(status) is not dict
            or set(status) != {"contract", "root_closure"}
            or type(status["contract"]) is not dict
            or type(status["root_closure"]) is not dict
        ):
            raise BootstrapError("persistent budget broker status drifted")
        runtime = {
            "authority": dict(_BUDGET_FALSE_AUTHORITY),
            "broker_actor": dict(owner.process.actor),
            "broker_endpoint_identity": dict(
                owner.process.endpoint_identity
            ),
            "broker_nonce": owner.process.nonce,
            "broker_pidfd_method": owner.process.pidfd_method,
            "formal_account_handoff": dict(
                transferred.account_handoff
            ),
            "formal_reservation_handoffs": {
                purpose: dict(record)
                for purpose, record in sorted(
                    transferred.reservation_handoffs.items()
                )
            },
            "formal_control_parent_handoff": dict(
                transferred.control_parent_handoff
            ),
            "formal_final_release_parent_handoff": dict(
                transferred.final_release_parent_handoff
            ),
            "formal_root_budget_handoff_identity": dict(
                handoff_result["handoff_identity"]
            ),
            "recovery_owner_observation": dict(recovery_result),
            "schema_version": BOOTSTRAP_BROKER_RUNTIME_SCHEMA,
            "selected_fd_transport": dict(
                owner.process.selected_fd_transport
            ),
            "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        }
        owner_response = owner.admin.request(
            "START_FORMAL_LAUNCH_OWNER",
            {"session_id": "formal-owner-session-a001"},
            expected_fd_counts=frozenset({0}),
        )
        owner_handoff = owner_response.record.get("result")
        if type(owner_handoff) is not dict:
            raise BootstrapError(
                "package-pinned formal-launch owner handoff is absent"
            )
        runtime["formal_launch_owner_observation"] = (
            owner.confirm_broker_hosted_formal_launch_owner(
                owner_handoff
            )
        )
        return runtime
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if admin is not None:
            try:
                admin.close()
            except BaseException as cleanup_error:
                if primary is not None:
                    primary.add_note(
                        "bootstrap admin cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
        if process is not None:
            try:
                if spawn_succeeded:
                    terminate_unattached = getattr(
                        process,
                        "terminate_unattached",
                        None,
                    )
                    if not callable(terminate_unattached):
                        raise BootstrapError(
                            "spawned persistent broker lacks exact "
                            "unattached-child termination"
                        )
                    terminate_unattached()
                else:
                    process.close()
            except BaseException as cleanup_error:
                if primary is None:
                    raise
                primary.add_note(
                    "persistent broker unattached-child cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        if adopted_unwrapped is not None:
            adopted_objects: list[object] = []
            raw_reservations = adopted_unwrapped.get("reservations")
            if isinstance(raw_reservations, Mapping):
                adopted_objects.extend(raw_reservations.values())
            adopted_objects.extend(
                adopted_unwrapped.get(field)
                for field in (
                    "final_release_parent",
                    "control_parent",
                    "account",
                )
            )
            closed_identities: set[int] = set()
            for owned in adopted_objects:
                if owned is None or id(owned) in closed_identities:
                    continue
                closed_identities.add(id(owned))
                close = getattr(owned, "close", None)
                if not callable(close):
                    continue
                try:
                    close()
                except BaseException as cleanup_error:
                    if primary is None:
                        primary = cleanup_error
                    else:
                        primary.add_note(
                            "unwrapped structural adoption cleanup also "
                            f"failed: {type(cleanup_error).__name__}: "
                            f"{cleanup_error}"
                        )
        if structural_fds:
            _close_descriptors_with_primary(
                structural_fds,
                primary=primary,
            )
        if transferred is not None and not spawn_succeeded:
            try:
                transferred.close_incomplete(
                    reason="bootstrap persistent broker startup failed",
                )
            except BaseException as cleanup_error:
                if primary is not None:
                    primary.add_note(
                        "formal budget transfer cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
        for label, authorization in (
            ("package budget-role authorization", package_authorization),
            ("native-helper authorization", native_authorization),
        ):
            if authorization is None:
                continue
            try:
                authorization.close()
            except BaseException as cleanup_error:
                if primary is not None:
                    primary.add_note(
                        f"{label} cleanup also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )


def _arm_bootstrap_budget_runtime_closeout(
    *,
    budget_runtime: Mapping[str, object],
    budget_profile: Mapping[str, object],
    campaign_dir: Path,
    terminal_path: Path,
) -> None:
    global _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME
    if _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME is not None:
        raise BootstrapError("another bootstrap budget runtime is already active")
    _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME = {
        "budget_profile": budget_profile,
        "budget_runtime": budget_runtime,
        "campaign_dir": campaign_dir,
        "terminal_path": terminal_path,
    }


def _publish_bootstrap_budget_success(
    *,
    persistent_runtime: Mapping[str, object],
    package_id: object,
) -> dict[str, object]:
    global _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME
    active = _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME
    if active is None:
        raise BootstrapError("bootstrap budget runtime closeout is not armed")
    budget_runtime = cast(Mapping[str, Any], active["budget_runtime"])
    profile = cast(Mapping[str, Any], active["budget_profile"])
    writer = budget_runtime["adapter"]
    bootstrap_broker = budget_runtime["bootstrap_broker"]
    failure_reservation = budget_runtime["bootstrap_failure_reservation"]
    persistent_owner = active.get("persistent_owner")
    if not isinstance(
        persistent_owner,
        _PersistentBootstrapBudgetOwner,
    ):
        raise BootstrapError(
            "bootstrap persistent budget owner is not retained"
        )
    reserve = profile["bootstrap"]["failure_closeout_reserve"]
    actor = persistent_runtime["broker_actor"]
    actor_pid = actor.get("pid") if type(actor) is dict else None
    if (
        type(actor) is not dict
        or type(actor_pid) is not int
        or actor.get("pid_starttime") != _proc_starttime(actor_pid)
    ):
        raise BootstrapError(
            "persistent budget broker liveness drifted before bootstrap terminal"
        )
    unused_failure_identity = failure_reservation.publish_bytes(
        str(reserve["target_name"]),
        _budget_canonical_json(
            {
                "authority": dict(_BUDGET_FALSE_AUTHORITY),
                "package_id": package_id,
                "schema_version": BOOTSTRAP_PACKAGE_FAILURE_CLOSEOUT_SCHEMA,
                "state": "UNUSED_SUCCESS_RESERVE_SEALED",
                "status": "PASS",
            }
        ),
    )
    terminal = {
        "authority": dict(_BUDGET_FALSE_AUTHORITY),
        "bootstrap_writer_release_contract": (
            "terminal-fsync-then-exact-close-before-return-v1"
        ),
        "campaign_dir": str(active["campaign_dir"]),
        "package_id": package_id,
        "persistent_budget_runtime": dict(persistent_runtime),
        "schema_version": BOOTSTRAP_BUDGET_TERMINAL_SCHEMA,
        "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        "status": "PASS",
        "unused_failure_closeout_identity": dict(unused_failure_identity),
    }
    terminal_identity = writer.write_exclusive(
        active["terminal_path"],
        _budget_canonical_json(terminal),
        mode=0o444,
    )
    writer.assert_success_writes_complete()
    writer.seal_directories()
    bootstrap_broker.close()
    if actor["pid_starttime"] != _proc_starttime(actor["pid"]):
        raise BootstrapError(
            "persistent budget broker liveness drifted after bootstrap writer close"
        )
    context_response = persistent_owner.admin.request(
        "BUILD_AND_DELIVER_FORMAL_LAUNCH_CONTEXT",
        {"campaign_dir": str(active["campaign_dir"])},
        expected_fd_counts=frozenset({0}),
    )
    context_result = context_response.record.get("result")
    if (
        type(context_result) is not dict
        or set(context_result)
        != {
            "context_identity",
            "owner_acknowledgement",
            "state",
        }
        or context_result["state"]
        != "PACKAGE_CONTEXT_REPLAYED_AND_RETAINED"
        or type(context_result["context_identity"]) is not dict
        or set(context_result["context_identity"])
        != {"sha256", "size_bytes"}
        or type(context_result["owner_acknowledgement"]) is not dict
        or context_result["owner_acknowledgement"].get("status")
        != "CONTEXT_RETAINED"
    ):
        raise BootstrapError(
            "package-pinned formal-launch owner context handoff drifted"
        )
    persistent_owner.close_success()
    _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME = None
    return {
        "identity": terminal_identity,
        "record": terminal,
        "formal_launch_owner_context_handoff": dict(context_result),
        "writer_closed": True,
    }


def _fail_active_bootstrap_budget_runtime(primary: BaseException) -> None:
    global _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME
    active = _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME
    if active is None:
        return
    budget_runtime = cast(Mapping[str, Any], active["budget_runtime"])
    profile = cast(Mapping[str, Any], active["budget_profile"])
    reserve = profile["bootstrap"]["failure_closeout_reserve"]
    failure_reservation = budget_runtime["bootstrap_failure_reservation"]
    failure_identity: dict[str, object] | None = None
    try:
        published_failure = failure_reservation.publish_bytes(
            str(reserve["target_name"]),
            _budget_canonical_json(
                {
                    "authority": dict(_BUDGET_FALSE_AUTHORITY),
                    "error_type": type(primary).__name__,
                    "formal_campaign_creation_authorized": False,
                    "root_path": str(active["campaign_dir"]),
                    "schema_version": (
                        BOOTSTRAP_PACKAGE_FAILURE_CLOSEOUT_SCHEMA
                    ),
                    "state": "markerless-incomplete",
                    "status": "FAIL_CLOSED",
                }
            ),
        )
        failure_identity = {
            "path": str(
                Path(active["campaign_dir"])
                / str(published_failure["path"])
            ),
            "sha256": published_failure["sha256"],
            "size_bytes": published_failure["size_bytes"],
        }
    except BaseException as closeout_error:
        primary.add_note(
            "bootstrap retained failure closeout also failed: "
            f"{type(closeout_error).__name__}: {closeout_error}"
        )
    persistent_owner = active.get("persistent_owner")
    if isinstance(
        persistent_owner,
        _PersistentBootstrapBudgetOwner,
    ):
        if failure_identity is None:
            try:
                persistent_owner.terminate_unpublished_incomplete()
            except BaseException as cleanup_error:
                primary.add_note(
                    "persistent broker termination without a published "
                    "failure identity also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        else:
            try:
                persistent_owner.abort_markerless(
                    failure_identity=failure_identity,
                    reason_sha256=hashlib.sha256(
                        (
                            f"{type(primary).__name__}: {primary}"
                        ).encode("utf-8")
                    ).hexdigest(),
                )
            except BaseException as cleanup_error:
                primary.add_note(
                    "persistent broker markerless abort also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        try:
            budget_runtime["bootstrap_broker"].close()
        except BaseException as cleanup_error:
            primary.add_note(
                "bootstrap budget broker cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME = None
        return
    for label, owned in (
        (
            "outside final-release parent capability",
            budget_runtime["final_release_parent_capability"],
        ),
        (
            "formal control-parent capability",
            budget_runtime["control_parent_capability"],
        ),
        *(
            (
                f"formal {purpose} reservation",
                reservation,
            )
            for purpose, reservation in reversed(
                tuple(budget_runtime["formal_reservations"].items())
            )
        ),
        ("formal budget broker", budget_runtime["formal_broker"]),
        ("bootstrap budget broker", budget_runtime["bootstrap_broker"]),
    ):
        try:
            owned.close()
        except BaseException as cleanup_error:
            primary.add_note(
                f"{label} cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
    _ACTIVE_BOOTSTRAP_BUDGET_RUNTIME = None


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
    resource_budget_profile: Path | str,
    resource_calibration_bundle_paths: Mapping[str, Path | str],
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
    budget_profile, budget_profile_identity = _resource_budget_profile(
        resource_budget_profile,
        require_launch_ready=True,
    )
    (
        resource_calibration_paths,
        resource_calibration_bundle_identities,
    ) = _resource_calibration_bundle_sources(
        resource_calibration_bundle_paths
    )
    resource_calibration_authorization_bundles: dict[
        str,
        Mapping[str, Any],
    ] = {}
    for stage, path in resource_calibration_paths.items():
        bundle, observed_identity = _canonical_record(
            path,
            f"{stage} resource calibration authorization bundle",
        )
        if (
            observed_identity
            != resource_calibration_bundle_identities[stage]
        ):
            raise BootstrapError(
                f"{stage} resource calibration authorization identity drifted"
            )
        resource_calibration_authorization_bundles[stage] = bundle
    budget_contracts = _planned_budget_contracts(
        campaign_dir=output,
        profile=budget_profile,
        profile_identity=budget_profile_identity,
    )
    budget_binding = {
        "bootstrap_budget_contract_identity": budget_contracts[
            "bootstrap_identity"
        ],
        "formal_root_budget_contract_identity": budget_contracts[
            "formal_identity"
        ],
        "resource_calibration_bundle_identities": (
            resource_calibration_bundle_identities
        ),
        "resource_budget_profile_identity": budget_profile_identity,
    }
    if any(candidate[field] != expected for field, expected in budget_binding.items()):
        raise BootstrapError(
            "candidate resource-budget profile/contract binding drifted"
        )
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
        budget_binding=budget_binding,
    )
    _bootstrap_handoff_spec = _bootstrap_runtime_budget_bindings(
        campaign_dir=output,
        profile=budget_profile,
        path_preregistration=path_preregistration,
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
        or any(gate_b[field] != expected for field, expected in budget_binding.items())
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
    calibration_tool_content_identities = (
        _calibration_tool_content_identities(planned)
    )
    if candidate["planned_source_identities"] != planned or candidate[
        "planned_source_set_digest"
    ] != _source_set_digest(planned):
        raise BootstrapError("planned package source bytes drifted after Gate A")
    _require_package_verifier_source_binding(
        planned=planned,
        candidate=candidate,
        gate_b=gate_b,
    )
    _require_native_helper_source_binding(
        planned=planned,
        candidate=candidate,
        gate_b=gate_b,
    )
    gate_b_session = gate_b["publisher"]["qualification_session"]
    gate_b_lock_identities = gate_b_session["lock_identities"]
    resource_gate_dir = gate_b_path.parent / "resource-gates"
    pre_full_resource_gate_path = (
        resource_gate_dir / "before-final-full-preflight.json"
    )
    pre_publication_resource_gate_path = (
        resource_gate_dir / "after-final-full-preflight.json"
    )
    _pre_full_resource_gate, pre_full_resource_gate_identity = (
        _read_gate_b_resource_gate(
            gate_b["pre_full_resource_gate_identity"],
            planned=planned,
            calibration_authorization_bundle=(
                resource_calibration_authorization_bundles[
                    "FULL_PREFLIGHT"
                ]
            ),
            calibration_authorization_bundle_identity=(
                resource_calibration_bundle_identities["FULL_PREFLIGHT"]
            ),
            expected_actor=gate_b["publisher"]["actor"],
            expected_session_id=gate_b_session["session_id"],
            expected_lock_identities=gate_b_lock_identities,
            expected_path=pre_full_resource_gate_path,
            expected_profile_stage="FULL_PREFLIGHT",
            expected_stage="BEFORE_FINAL_FULL_PREFLIGHT",
            expected_disk_path=gate_b_path.parent.parent,
            expected_kind="GATE_B_FINAL_FULL_PREFLIGHT",
            expected_sequence=1,
        )
    )
    _pre_publication_resource_gate, pre_publication_resource_gate_identity = (
        _read_gate_b_resource_gate(
            gate_b["pre_publication_resource_gate_identity"],
            planned=planned,
            calibration_authorization_bundle=(
                resource_calibration_authorization_bundles[
                    "GATE_B_QUALIFICATION"
                ]
            ),
            calibration_authorization_bundle_identity=(
                resource_calibration_bundle_identities[
                    "GATE_B_QUALIFICATION"
                ]
            ),
            expected_actor=gate_b["publisher"]["actor"],
            expected_session_id=gate_b_session["session_id"],
            expected_lock_identities=gate_b_lock_identities,
            expected_path=pre_publication_resource_gate_path,
            expected_profile_stage="GATE_B_QUALIFICATION",
            expected_stage="AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
            expected_disk_path=gate_b_path.parent,
            expected_kind="GATE_B_QUALIFICATION_PUBLICATION",
            expected_sequence=2,
        )
    )
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
    _validate_final_full_preflight(
        final_full_preflight,
        gate_a=gate_a,
        planned=planned,
        receipt_identity=final_full_preflight_identity,
    )
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
        pre_full_resource_gate_identity=pre_full_resource_gate_identity,
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
    captured = _capture_epoch(
        approved_observation=gate_b_epoch,
        system_paths=system_paths,
    )
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

    _base_authority, bootstrap_binding = _prepackage_state()
    budget_runtime = _create_bootstrap_budget_runtime(
        campaign_dir=output,
        budget_source_bytes=bootstrap_binding["budget_authority_bytes"],
        budget_source_identity=planned[
            "script.ab16_budget_authority_v1"
        ],
        profile=budget_profile,
        contracts=budget_contracts,
    )
    budget_writer = budget_runtime["adapter"]
    _arm_bootstrap_budget_runtime_closeout(
        budget_runtime=budget_runtime,
        budget_profile=budget_profile,
        campaign_dir=output,
        terminal_path=Path(
            path_preregistration["bootstrap_budget_terminal_path"]
        ),
    )
    budget_writer.mkdir_exclusive(output)
    bootstrap_dir = budget_writer.mkdir_exclusive(
        output / "bootstrap-authority"
    )
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
    capture_source_identity = budget_writer.write_exclusive(
        capture_path,
        authority.canonical_json(capture_record),
    )
    campaign_authority_dir = budget_writer.mkdir_exclusive(
        output / "campaign-authority"
    )
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
        writer=budget_writer,
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
        pre_full_resource_gate_path=pre_full_resource_gate_path,
        pre_publication_resource_gate_path=pre_publication_resource_gate_path,
        capture_path=capture_path,
        path_preregistration_path=path_preregistration_path,
        snapshot_archive_path=snapshot_build["archive_path"],
        snapshot_manifest_path=snapshot_build["manifest_path"],
        external_platform_path=snapshot_build["platform_path"],
        resource_budget_profile_path=_absolute(resource_budget_profile),
        resource_calibration_bundle_paths=resource_calibration_paths,
    )
    expected_package_sources = {
        spec.role: authority.full_identity(authority.snapshot_regular(spec.path)) for spec in source_specs
    }
    with _activate_bootstrap_budget_authority(budget_writer):
        package = budget_writer.build_package(
            package_dir,
            source_specs,
            repository_head=repository_head,
            run_nonce=output.name,
            manager_epoch=captured["manager_epoch"],
        )
    package_absolute, retained_package_fd = _open_directory_fd(
        package_dir
    )
    if package_absolute != package_dir:
        os.close(retained_package_fd)
        raise BootstrapError(
            "retained package root absolute identity drifted"
        )
    replay_authorization: VerifiedPackageIndependentReplay | None = None
    replay_primary: BaseException | None = None
    try:
        _package_source_join(
            package_dir,
            expected_sources=expected_package_sources,
        )
        replay_authorization = (
            _verify_and_publish_package_independent_replay(
                package_dir=package_dir,
                package=package,
                verifier_source_identity=gate_b[
                    "package_verifier_source_identity"
                ],
                python_path=system_paths["python3_13"],
                repository_head=repository_head,
                run_nonce=output.name,
                manager_epoch=captured["manager_epoch"],
                native_helper_source_identity=gate_b[
                    "native_budget_helper_source_identity"
                ],
                final_path=Path(
                    path_preregistration[
                        "package_independent_replay_path"
                    ]
                ),
                staging_path=Path(
                    path_preregistration[
                        "package_independent_replay_staging_path"
                    ]
                ),
                budget_writer=budget_writer,
                retained_package_fd=retained_package_fd,
            )
        )
        package_independent_replay_identity = dict(
            replay_authorization.identity
        )
        persistent_budget_runtime = _bootstrap_persistent_budget_runtime(
            budget_runtime=budget_runtime,
            budget_profile=budget_profile,
            budget_profile_identity=budget_profile_identity,
            resource_calibration_bundle_identities=(
                resource_calibration_bundle_identities
            ),
            calibration_tool_content_identities=(
                calibration_tool_content_identities
            ),
            package_root_fd=retained_package_fd,
            replay_authorization=replay_authorization,
            package=package,
            verifier_source_identity=gate_b[
                "package_verifier_source_identity"
            ],
            native_helper_source_identity=gate_b[
                "native_budget_helper_source_identity"
            ],
            planned=planned,
            repository_head=repository_head,
            run_nonce=output.name,
            manager_epoch=captured["manager_epoch"],
            endpoint_path=Path(
                path_preregistration["budget_broker_control_socket_path"]
            ),
            bootstrap_handoff_spec=_bootstrap_handoff_spec,
            formal_root_budget_contract_identity=budget_contracts[
                "formal_identity"
            ],
            bootstrap_failure_closeout_path=Path(
                path_preregistration[
                    "bootstrap_package_failure_closeout_path"
                ]
            ),
        )
    except BaseException as exc:
        replay_primary = exc
        raise
    finally:
        if replay_authorization is not None:
            try:
                replay_authorization.close()
            except BaseException as cleanup_error:
                if replay_primary is None:
                    raise
                replay_primary.add_note(
                    "package-independent replay authorization cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        try:
            os.close(retained_package_fd)
        except BaseException as cleanup_error:
            if replay_primary is None:
                raise
            replay_primary.add_note(
                "retained package-root cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
    materialization, snapshot_identities = _materialize_repository_snapshot(
        campaign_dir=output,
        package_dir=package_dir,
        package_id=package["package_id"],
        created_at_utc=timestamp,
        writer=budget_writer,
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
    inputs[PACKAGE_INDEPENDENT_REPLAY_INPUT_ROLE] = dict(
        package_independent_replay_identity
    )
    inputs[RESOURCE_BUDGET_PROFILE_INPUT_ROLE] = _payload_identity(
        package_dir,
        RESOURCE_BUDGET_PROFILE_PACKAGE_ROLE,
    )

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
        budget_binding=budget_binding,
    )
    with _activate_bootstrap_budget_authority(budget_writer):
        root_identity = budget_writer.write_campaign_root(output, root)
    selection = authority.make_gate1_selection(
        root,
        campaign_root_identity=root_identity,
        tools=tools,
        inputs=inputs,
        created_at_utc=timestamp,
    )
    with _activate_bootstrap_budget_authority(budget_writer):
        selection_identity = budget_writer.write_gate1_selection(
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
    formal_parent = output / "formal-ab16"
    try:
        formal_parent_metadata = os.stat(formal_parent, follow_symlinks=False)
    except OSError as exc:
        raise BootstrapError(
            "formal launch parent created by the budget broker is absent"
        ) from exc
    if (
        not stat.S_ISDIR(formal_parent_metadata.st_mode)
        or formal_parent_metadata.st_uid != os.getuid()
        or stat.S_IMODE(formal_parent_metadata.st_mode) != 0o700
    ):
        raise BootstrapError(
            "formal launch parent created by the budget broker drifted"
        )
    if qualification_fd is None or qualification_lock_fds is None:
        raise BootstrapError("Gate-B qualification handoff capability is absent")
    # The qualification actor's three retained locks still cover this write
    # and the persistent-owner liveness check.  Only the explicit handoff
    # below may let that actor close them.
    bootstrap_budget_terminal = _publish_bootstrap_budget_success(
        persistent_runtime=persistent_budget_runtime,
        package_id=package["package_id"],
    )
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
        "bootstrap_budget_terminal_identity": bootstrap_budget_terminal[
            "identity"
        ],
        "bootstrap_budget_writer_closed": bootstrap_budget_terminal[
            "writer_closed"
        ],
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
        "gate_b_pre_full_resource_gate_identity": pre_full_resource_gate_identity,
        "gate_b_pre_publication_resource_gate_identity": (
            pre_publication_resource_gate_identity
        ),
        "gate_b_qualification_handoff": qualification_handoff,
        "organic_ab16_authorized": False,
        "package_id": package["package_id"],
        "persistent_budget_runtime": persistent_budget_runtime,
        "native_budget_helper_source_identity": dict(
            gate_b["native_budget_helper_source_identity"]
        ),
        "package_independent_replay_identity": (
            package_independent_replay_identity
        ),
        "package_verifier_source_identity": dict(
            gate_b["package_verifier_source_identity"]
        ),
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


_bootstrap_campaign_unwrapped = bootstrap_campaign
_BOOTSTRAP_CAMPAIGN_API_LOCK = threading.Lock()
_BOOTSTRAP_CAMPAIGN_API_STATE = "READY"


def bootstrap_campaign(  # type: ignore[no-redef]
    *,
    campaign_dir: Path | str,
    repository_root: Path | str,
    gate_a_receipt: Path | str,
    offline_candidate: Path | str,
    gate_b_approval: Path | str,
    resource_budget_profile: Path | str,
    resource_calibration_bundle_paths: Mapping[str, Path | str],
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    qualification_fd: int | None = None,
    qualification_lock_fds: Mapping[str, int] | None = None,
    created_at_utc: str | None = None,
) -> dict[str, object]:
    """Run the one-shot bootstrap with exact failure-terminal ownership."""

    global _BOOTSTRAP_CAMPAIGN_API_STATE
    with _BOOTSTRAP_CAMPAIGN_API_LOCK:
        if _BOOTSTRAP_CAMPAIGN_API_STATE != "READY":
            raise BootstrapError(
                "bootstrap campaign API attempt was already consumed"
            )
        _BOOTSTRAP_CAMPAIGN_API_STATE = "CONSUMED"
    primary: BaseException | None = None
    try:
        _replay_prepackage_closure()
        return _bootstrap_campaign_unwrapped(
            campaign_dir=campaign_dir,
            repository_root=repository_root,
            gate_a_receipt=gate_a_receipt,
            offline_candidate=offline_candidate,
            gate_b_approval=gate_b_approval,
            resource_budget_profile=resource_budget_profile,
            resource_calibration_bundle_paths=(
                resource_calibration_bundle_paths
            ),
            strict_input_paths=strict_input_paths,
            system_tool_paths=system_tool_paths,
            qualification_fd=qualification_fd,
            qualification_lock_fds=qualification_lock_fds,
            created_at_utc=created_at_utc,
        )
    except BaseException as exc:
        primary = exc
        _fail_active_bootstrap_budget_runtime(exc)
        raise
    finally:
        try:
            _replay_prepackage_closure()
        except BaseException as replay_error:
            if primary is None:
                raise
            primary.add_note(
                "post-bootstrap pre-package closure replay also failed: "
                f"{type(replay_error).__name__}: {replay_error}"
            )


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
    parser.add_argument("--native-budget-helper", type=Path, required=True)
    parser.add_argument(
        "--resource-budget-profile",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--resource-calibration-full-preflight",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--resource-calibration-gate-b-qualification",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--resource-calibration-formal-organic-arm",
        type=Path,
        required=True,
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


def _cli_resource_calibration_bundle_paths(
    args: argparse.Namespace,
) -> dict[str, Path]:
    return {
        "FULL_PREFLIGHT": args.resource_calibration_full_preflight,
        "GATE_B_QUALIFICATION": (
            args.resource_calibration_gate_b_qualification
        ),
        "FORMAL_ORGANIC_ARM": (
            args.resource_calibration_formal_organic_arm
        ),
    }


def _cli_system_tools(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "attestor_python": args.attestor_python,
        "busctl": args.busctl,
        "git": args.git,
        "libsystemd": args.libsystemd,
        "native_budget_helper": args.native_budget_helper,
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
        if repository != Path(str(_BOOTSTRAP_BINDING["repository_root"])):
            raise BootstrapError("CLI repository root differs from the fixed Git top level")
        if args.command == "candidate":
            _replay_prepackage_closure()
            result = build_gate_a_candidate(
                output_path=args.candidate_output,
                gate_a_receipt=args.gate_a_receipt,
                repository_root=repository,
                target_campaign_dir=args.campaign_dir,
                resource_budget_profile=args.resource_budget_profile,
                resource_calibration_bundle_paths=(
                    _cli_resource_calibration_bundle_paths(args)
                ),
                strict_input_paths=_production_strict_inputs(repository, args),
                system_tool_paths=_cli_system_tools(args),
                created_at_utc=args.created_at_utc,
            )
            _replay_prepackage_closure()
        elif args.command == "bootstrap":
            result = bootstrap_campaign(
                campaign_dir=args.campaign_dir,
                repository_root=repository,
                gate_a_receipt=args.gate_a_receipt,
                offline_candidate=args.offline_candidate,
                gate_b_approval=args.gate_b_approval,
                resource_budget_profile=args.resource_budget_profile,
                resource_calibration_bundle_paths=(
                    _cli_resource_calibration_bundle_paths(args)
                ),
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
