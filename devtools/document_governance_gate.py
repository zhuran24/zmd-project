#!/usr/bin/env python3
"""Run the repository's non-mutating document-governance acceptance gate.

The gate is intentionally separate from the production preflight.  It validates
only the document/knowledge/governance framework declared by
``.docsystem/manifest.json``.  Every lane runs without a shell, receives an
isolated temporary directory, and is wrapped by a Git-visible-state fingerprint.
A green result therefore describes the exact repository state supplied to the
gate rather than a tree silently rewritten by one of its checkers.
"""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping, Sequence

import jsonschema  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_RELPATH = ".docsystem/manifest.json"
MANIFEST_SCHEMA_RELPATH = "data/repository_governance/document_system/manifest.schema.json"
_ALLOWED_PLACEHOLDERS = frozenset({"{python}", "{repo}", "{temp}"})
_WRITE_CAPABLE_TOKENS = frozenset({"--write", "write", "--fix", "--apply", "--update"})
_RESERVED_LANE_ENVIRONMENT = frozenset(
    {
        "PATH",
        "HOME",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPYCACHEPREFIX",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "MYPY_CACHE_DIR",
        "RUFF_CACHE_DIR",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_OPTIONAL_LOCKS",
        "ZMD_DOCUMENT_GOVERNANCE_GATE",
        "ZMD_DOCUMENT_GOVERNANCE_LANE",
        "ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT",
    }
)


class GovernanceGateError(RuntimeError):
    """Fail-closed configuration, Git or lane-execution error."""


@dataclass(frozen=True)
class GitVisibleState:
    """Compact receipt for index, worktree and non-ignored untracked state."""

    version: str
    digest: str
    head: str
    index_digest: str
    visible_paths_digest: str
    status_digest: str
    path_records: Mapping[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "digest": self.digest,
            "head": self.head,
            "index_digest": self.index_digest,
            "visible_paths_digest": self.visible_paths_digest,
            "status_digest": self.status_digest,
            "path_records": dict(self.path_records),
        }


@dataclass(frozen=True)
class LaneResult:
    lane_id: str
    description: str
    command: tuple[str, ...]
    returncode: int
    duration_seconds: float
    timed_out: bool
    output: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.lane_id,
            "description": self.description,
            "command": list(self.command),
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 6),
            "timed_out": self.timed_out,
            "passed": self.passed,
            "output": self.output,
        }


@dataclass(frozen=True)
class GateReport:
    profile: str
    base: str | None
    before: GitVisibleState
    after: GitVisibleState
    state_changes: tuple[str, ...]
    lane_results: tuple[LaneResult, ...]
    duration_seconds: float

    @property
    def passed(self) -> bool:
        return not self.state_changes and all(result.passed for result in self.lane_results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.passed else "BLOCK",
            "profile": self.profile,
            "base": self.base,
            "duration_seconds": round(self.duration_seconds, 6),
            "before": self.before.as_dict(),
            "after": self.after.as_dict(),
            "state_changes": list(self.state_changes),
            "lanes": [result.as_dict() for result in self.lane_results],
        }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GovernanceGateError(f"duplicate JSON key: {key!r}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise GovernanceGateError(f"non-finite JSON constant: {value}")


def _load_json_object(path: Path, root: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        try:
            label = path.relative_to(root).as_posix()
        except ValueError:
            label = str(path)
        raise GovernanceGateError(f"cannot read strict JSON {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceGateError(f"{path}: JSON root must be an object")
    return value


def _validate_json(schema: Mapping[str, Any], value: Mapping[str, Any], label: str) -> None:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except jsonschema.SchemaError as exc:
        raise GovernanceGateError(f"schema for {label} is invalid: {exc.message}") from exc
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise GovernanceGateError(f"{label} schema error at {location}: {error.message}")


def _normalise_relpath(value: str) -> str:
    path = PurePosixPath(value)
    if not value or value.startswith("/") or ".." in path.parts or "\\" in value or "\0" in value:
        raise GovernanceGateError(f"unsafe repository-relative path: {value!r}")
    return path.as_posix()


def load_gate_configuration(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and semantically validate the bootstrap manifest and gate registry."""

    root = root.resolve()
    manifest_path = root / BOOTSTRAP_RELPATH
    manifest = _load_json_object(manifest_path, root)
    manifest_schema_value = manifest.get("manifest_schema")
    if manifest_schema_value != MANIFEST_SCHEMA_RELPATH:
        raise GovernanceGateError(
            "bootstrap manifest_schema is not the code-pinned schema path: "
            f"{manifest_schema_value!r} != {MANIFEST_SCHEMA_RELPATH!r}"
        )
    manifest_schema = _load_json_object(root / MANIFEST_SCHEMA_RELPATH, root)
    _validate_json(manifest_schema, manifest, BOOTSTRAP_RELPATH)

    descriptor = manifest.get("governance_gate")
    if not isinstance(descriptor, dict):
        raise GovernanceGateError("bootstrap manifest does not declare governance_gate")
    source = root / _normalise_relpath(str(descriptor.get("source", "")))
    schema_path = root / _normalise_relpath(str(descriptor.get("schema", "")))
    config = _load_json_object(source, root)
    schema = _load_json_object(schema_path, root)
    _validate_json(schema, config, source.relative_to(root).as_posix())
    _validate_gate_semantics(root, manifest, config)
    return manifest, config


def _validate_gate_semantics(
    root: Path,
    manifest: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    if config["system_version"] != manifest["system_version"]:
        raise GovernanceGateError("governance gate and bootstrap manifest system_version differ")

    descriptor = manifest["governance_gate"]
    required_descriptor_paths = {
        "source": descriptor["source"],
        "schema": descriptor["schema"],
        "runner": descriptor["runner"],
        "ci_workflow": descriptor["ci_workflow"],
    }
    for field, relpath_value in required_descriptor_paths.items():
        relpath = _normalise_relpath(str(relpath_value))
        if not (root / relpath).is_file():
            raise GovernanceGateError(f"manifest.governance_gate.{field} is missing: {relpath}")

    lanes = config["lanes"]
    lane_by_id: dict[str, Mapping[str, Any]] = {}
    for lane in lanes:
        lane_id = str(lane["id"])
        if lane_id in lane_by_id:
            raise GovernanceGateError(f"duplicate governance lane id: {lane_id}")
        lane_by_id[lane_id] = lane
        for required_path_value in lane["required_paths"]:
            relpath = _normalise_relpath(str(required_path_value))
            if not (root / relpath).exists():
                raise GovernanceGateError(f"lane {lane_id} requires missing path: {relpath}")
        command = [str(token) for token in lane["command"]]
        if command[0] != "{python}":
            raise GovernanceGateError(
                f"lane {lane_id} must execute through the registered Python interpreter"
            )
        for token in command:
            present = {placeholder for placeholder in _ALLOWED_PLACEHOLDERS if placeholder in token}
            # Braces other than the three stable placeholders are rejected.  The
            # command is argv, not a shell template.
            residue = token
            for placeholder in present:
                residue = residue.replace(placeholder, "")
            if "{" in residue or "}" in residue:
                raise GovernanceGateError(
                    f"lane {lane_id} command contains unsupported placeholder: {token!r}"
                )
            if token in _WRITE_CAPABLE_TOKENS or any(
                token.startswith(f"{prefix}=")
                for prefix in _WRITE_CAPABLE_TOKENS
                if prefix.startswith("--")
            ):
                raise GovernanceGateError(
                    f"lane {lane_id} contains a write-capable token forbidden by the read-only gate: {token}"
                )
        if "-c" in command:
            raise GovernanceGateError(
                f"lane {lane_id} embeds Python source with -c; register a reviewed repository tool instead"
            )
        environment_keys = {str(key) for key in lane["environment"]}
        reserved_environment = sorted(environment_keys & _RESERVED_LANE_ENVIRONMENT)
        if reserved_environment:
            raise GovernanceGateError(
                f"lane {lane_id} overrides runner-owned environment: "
                + ", ".join(reserved_environment)
            )
        base_argument = lane["base_argument"]
        if base_argument is not None and str(base_argument) in lane["command"]:
            raise GovernanceGateError(
                f"lane {lane_id} must not hard-code its configured base_argument"
            )

    used: set[str] = set()
    profiles = config["profiles"]
    for profile_id, profile in profiles.items():
        lane_ids = [str(value) for value in profile["lane_ids"]]
        if len(lane_ids) != len(set(lane_ids)):
            raise GovernanceGateError(f"profile {profile_id} repeats a lane")
        unknown = sorted(set(lane_ids) - set(lane_by_id))
        if unknown:
            raise GovernanceGateError(
                f"profile {profile_id} references unknown lanes: {', '.join(unknown)}"
            )
        used.update(lane_ids)
    unused = sorted(set(lane_by_id) - used)
    if unused:
        raise GovernanceGateError(f"governance lanes are unused by every profile: {', '.join(unused)}")

    required_profiles = {"changed", "full", "weekly", "framework", "historical_replay"}
    missing_profiles = sorted(required_profiles - set(profiles))
    if missing_profiles:
        raise GovernanceGateError(
            "governance gate omits required profiles: " + ", ".join(missing_profiles)
        )
    changed_lanes = set(profiles["changed"]["lane_ids"])
    full_lanes = set(profiles["full"]["lane_ids"])
    weekly_lanes = set(profiles["weekly"]["lane_ids"])
    historical_lanes = set(profiles["historical_replay"]["lane_ids"])
    for profile_id, selected in (("changed", changed_lanes), ("full", full_lanes), ("weekly", weekly_lanes)):
        if "code_assets_current" not in selected:
            raise GovernanceGateError(f"{profile_id} profile must include code_assets_current")
        if "code_assets_history" in selected:
            raise GovernanceGateError(
                f"{profile_id} profile must not depend on historical Git objects"
            )
    if historical_lanes != {"code_assets_history"}:
        raise GovernanceGateError(
            "historical_replay must be the manual-only code_assets_history lane"
        )
    if "docsystem_changed" not in changed_lanes:
        raise GovernanceGateError("changed profile must include diff-aware document checking")
    if "docsystem_changed" in weekly_lanes:
        raise GovernanceGateError("weekly profile must be clean-tree oriented, not diff-scoped")

    for profile_id, selected in (
        ("changed", changed_lanes),
        ("full", full_lanes),
        ("weekly", weekly_lanes),
    ):
        if "maintenance_audit" not in selected:
            raise GovernanceGateError(
                f"{profile_id} profile must include the read-only maintenance audit"
            )
    framework_lanes = set(profiles.get("framework", {}).get("lane_ids", []))
    for profile_id, selected in (
        ("changed", changed_lanes),
        ("full", full_lanes),
        ("weekly", weekly_lanes),
        ("framework", framework_lanes),
    ):
        if "maintenance_audit_regressions" not in selected:
            raise GovernanceGateError(
                f"{profile_id} profile must include maintenance-audit regressions"
            )
    if "maintenance_audit" in framework_lanes:
        raise GovernanceGateError(
            "framework profile should run maintenance regressions, not the repository audit lane"
        )

    default_profile = str(config["runner"]["default_profile"])
    if default_profile not in profiles:
        raise GovernanceGateError(f"runner.default_profile is unknown: {default_profile}")


def _run_git(root: Path, args: Sequence[str], *, allow_failure: bool = False) -> bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GovernanceGateError("git is unavailable") from exc
    if completed.returncode != 0 and not allow_failure:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise GovernanceGateError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout


def _nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(os.fsdecode(value) for value in raw.split(b"\0") if value)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_record(root: Path, relpath: str) -> str:
    path = root / relpath
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return "missing"
    mode = stat.S_IMODE(metadata.st_mode)
    if stat.S_ISLNK(metadata.st_mode):
        target = os.fsencode(os.readlink(path))
        return f"symlink:{mode:o}:{len(target)}:{_sha256_bytes(target)}"
    if stat.S_ISREG(metadata.st_mode):
        return f"file:{mode:o}:{metadata.st_size}:{_sha256_file(path)}"
    if stat.S_ISDIR(metadata.st_mode):
        return f"directory:{mode:o}"
    return f"other:{mode:o}:{metadata.st_mode}"


def _declared_workspace_inputs(root: Path) -> tuple[str, ...]:
    manifest_path = root / BOOTSTRAP_RELPATH
    if not manifest_path.is_file():
        # Direct fingerprint consumers may operate on a minimal Git fixture.
        # A real gate run loads and validates the manifest before fingerprinting.
        return ()
    manifest = _load_json_object(manifest_path, root)
    records = manifest.get("workspace_overlays", {}).get("records", [])
    if not isinstance(records, list):
        raise GovernanceGateError("manifest workspace_overlays.records must be a list")
    paths: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise GovernanceGateError(f"workspace_overlays.records[{index}] must be an object")
        paths.append(_normalise_relpath(str(record.get("path", ""))))
    if len(paths) != len(set(paths)):
        raise GovernanceGateError("workspace overlay paths contain duplicates")
    return tuple(sorted(paths))


def capture_git_visible_state(root: Path = ROOT) -> GitVisibleState:
    """Fingerprint tracked state plus manifest-declared workspace inputs.

    Arbitrary untracked files are intentionally excluded.  A concurrent agent
    writing an unrelated local artifact must not be misattributed to a checker.
    Optional overlays are included explicitly because they are declared inputs.
    """

    root = root.resolve()
    top = Path(os.fsdecode(_run_git(root, ["rev-parse", "--show-toplevel"])).strip()).resolve()
    if top != root:
        raise GovernanceGateError(f"repository root mismatch: expected {root}, Git reports {top}")

    head_raw = _run_git(root, ["rev-parse", "--verify", "HEAD"], allow_failure=True).strip()
    head = head_raw.decode("ascii", "strict") if head_raw else "UNBORN"
    index_raw = _run_git(root, ["ls-files", "--stage", "-z"])
    tracked_raw = _run_git(root, ["ls-files", "--cached", "-z"])
    status_raw = _run_git(
        root,
        ["status", "--porcelain=v2", "-z", "--untracked-files=no", "--ignore-submodules=none"],
    )

    dynamic_paths: set[str] = set()
    for args in (
        ["diff", "--no-renames", "--name-only", "-z"],
        ["diff", "--cached", "--no-renames", "--name-only", "-z"],
    ):
        dynamic_paths.update(_nul_paths(_run_git(root, args)))
    dynamic_paths.update(_declared_workspace_inputs(root))
    records = {path: _path_record(root, path) for path in sorted(dynamic_paths)}

    digest = hashlib.sha256()
    fields = (
        ("version", b"git_declared_state_v2"),
        ("head", head.encode("ascii")),
        ("index", index_raw),
        ("tracked", tracked_raw),
        ("status", status_raw),
    )
    for label, value in fields:
        digest.update(label.encode("ascii") + b"\0" + len(value).to_bytes(8, "big") + value)
    for path, record in records.items():
        encoded_path = os.fsencode(path)
        encoded_record = record.encode("ascii")
        digest.update(
            b"path\0"
            + len(encoded_path).to_bytes(8, "big")
            + encoded_path
            + len(encoded_record).to_bytes(8, "big")
            + encoded_record
        )

    return GitVisibleState(
        version="git_declared_state_v2",
        digest=digest.hexdigest(),
        head=head,
        index_digest=_sha256_bytes(index_raw),
        visible_paths_digest=_sha256_bytes(tracked_raw),
        status_digest=_sha256_bytes(status_raw),
        path_records=records,
    )


def compare_git_visible_states(before: GitVisibleState, after: GitVisibleState) -> tuple[str, ...]:
    changes: list[str] = []
    if before.version != after.version:
        changes.append(f"fingerprint version changed: {before.version} -> {after.version}")
    if before.head != after.head:
        changes.append(f"HEAD changed: {before.head} -> {after.head}")
    if before.index_digest != after.index_digest:
        changes.append("Git index entries changed")
    if before.visible_paths_digest != after.visible_paths_digest:
        changes.append("Git-visible path set changed")
    if before.status_digest != after.status_digest:
        changes.append("Git status changed")
    for path in sorted(set(before.path_records) | set(after.path_records)):
        previous = before.path_records.get(path)
        current = after.path_records.get(path)
        if previous != current:
            if previous is None:
                changes.append(f"path became worktree-visible: {path}")
            elif current is None:
                changes.append(f"path left the changed/untracked set: {path}")
            else:
                changes.append(f"path bytes or mode changed: {path}")
    if before.digest != after.digest and not changes:
        changes.append("Git-visible fingerprint changed for an unclassified reason")
    return tuple(changes)


def _expand_token(token: str, *, root: Path, temp: Path) -> str:
    value = token.replace("{python}", sys.executable)
    value = value.replace("{repo}", str(root))
    value = value.replace("{temp}", str(temp))
    return value


def _external_temp_parent(root: Path) -> Path:
    """Return a configurable system scratch root outside the repository."""

    configured = os.environ.get("ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT")
    parent = Path(configured).expanduser().resolve() if configured else Path(tempfile.gettempdir()).resolve()
    repository = root.resolve()
    # A scratch root may be an ancestor of the repository (for example /tmp
    # containing /tmp/pytest-*/repo): TemporaryDirectory creates a sibling,
    # not a descendant of the repository.  Only the repository itself or a
    # directory inside it is unsafe.
    if parent == repository or repository in parent.parents:
        raise GovernanceGateError(
            f"document-governance scratch root must be outside the repository: {parent}"
        )
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise GovernanceGateError(f"document-governance scratch root is not writable: {parent}")
    return parent


def _run_lane(
    root: Path,
    lane: Mapping[str, Any],
    *,
    base: str | None,
) -> LaneResult:
    lane_id = str(lane["id"])
    started = time.monotonic()
    with tempfile.TemporaryDirectory(
        prefix=f"zmd-docgate-{lane_id}-",
        dir=_external_temp_parent(root),
    ) as temporary:
        temp = Path(temporary)
        command = tuple(
            _expand_token(str(token), root=root, temp=temp)
            for token in lane["command"]
        )
        base_argument = lane["base_argument"]
        if base is not None and base_argument is not None:
            command = (*command, str(base_argument), base)

        env = os.environ.copy()
        env.update(
            {
                "GIT_OPTIONAL_LOCKS": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": str(temp / "pycache"),
                "TMPDIR": str(temp / "tmp"),
                "TMP": str(temp / "tmp"),
                "TEMP": str(temp / "tmp"),
                "XDG_CACHE_HOME": str(temp / "xdg-cache"),
                "MYPY_CACHE_DIR": str(temp / "mypy-cache"),
                "RUFF_CACHE_DIR": str(temp / "ruff-cache"),
                "ZMD_DOCUMENT_GOVERNANCE_GATE": "1",
                "ZMD_DOCUMENT_GOVERNANCE_LANE": lane_id,
            }
        )
        (temp / "tmp").mkdir(parents=True, exist_ok=True)
        for key, raw_value in lane["environment"].items():
            env[str(key)] = _expand_token(str(raw_value), root=root, temp=temp)

        timed_out = False
        output = ""
        returncode = 1
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                stdout, _ = process.communicate(timeout=int(lane["timeout_seconds"]))
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                stdout, _ = process.communicate()
                returncode = 124
            output = stdout.decode("utf-8", "replace")
        except OSError as exc:
            output = f"cannot execute lane {lane_id}: {exc}\n"
            returncode = 127
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()

    return LaneResult(
        lane_id=lane_id,
        description=str(lane["description"]),
        command=command,
        returncode=returncode,
        duration_seconds=time.monotonic() - started,
        timed_out=timed_out,
        output=output,
    )


def _verify_base(root: Path, base: str) -> str:
    value = _run_git(root, ["rev-parse", "--verify", f"{base}^{{commit}}"])
    return value.decode("ascii", "strict").strip()


def run_gate(
    *,
    root: Path = ROOT,
    profile: str | None = None,
    base: str | None = None,
    lane_filter: Iterable[str] = (),
) -> GateReport:
    root = root.resolve()
    _manifest, config = load_gate_configuration(root)
    profile_id = profile or str(config["runner"]["default_profile"])
    profiles = config["profiles"]
    if profile_id not in profiles:
        raise GovernanceGateError(f"unknown governance profile: {profile_id}")
    profile_record = profiles[profile_id]
    if profile_record["requires_base"] and base is None:
        raise GovernanceGateError(f"profile {profile_id} requires --base")
    resolved_base = _verify_base(root, base) if base is not None else None

    lane_by_id = {str(lane["id"]): lane for lane in config["lanes"]}
    lane_ids = [str(value) for value in profile_record["lane_ids"]]
    requested = tuple(lane_filter)
    if requested:
        unknown = sorted(set(requested) - set(lane_ids))
        if unknown:
            raise GovernanceGateError(
                f"requested lanes are not in profile {profile_id}: {', '.join(unknown)}"
            )
        requested_set = set(requested)
        lane_ids = [lane_id for lane_id in lane_ids if lane_id in requested_set]
    if not lane_ids:
        raise GovernanceGateError("governance gate selected no lanes")

    before = capture_git_visible_state(root)
    started = time.monotonic()
    results_by_id: dict[str, LaneResult] = {}
    workers = min(int(config["runner"]["max_parallel_lanes"]), len(lane_ids))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="document-governance") as executor:
        futures: dict[str, Future[LaneResult]] = {
            lane_id: executor.submit(_run_lane, root, lane_by_id[lane_id], base=resolved_base)
            for lane_id in lane_ids
        }
        for lane_id in lane_ids:
            results_by_id[lane_id] = futures[lane_id].result()
    after = capture_git_visible_state(root)
    changes = compare_git_visible_states(before, after)
    return GateReport(
        profile=profile_id,
        base=resolved_base,
        before=before,
        after=after,
        state_changes=changes,
        lane_results=tuple(results_by_id[lane_id] for lane_id in lane_ids),
        duration_seconds=time.monotonic() - started,
    )


def _render_report(report: GateReport) -> str:
    lines = [
        "=" * 72,
        f"Document governance gate: profile={report.profile}",
        f"input fingerprint:  {report.before.digest}",
        f"output fingerprint: {report.after.digest}",
        "=" * 72,
    ]
    for result in report.lane_results:
        verdict = "PASS" if result.passed else "BLOCK"
        lines.append(
            f"[{verdict}] {result.lane_id} ({result.duration_seconds:.2f}s): {result.description}"
        )
        output = result.output.rstrip()
        if output:
            lines.extend(f"  {line}" for line in output.splitlines())
        if result.timed_out:
            lines.append("  lane exceeded its configured timeout")
    if report.state_changes:
        lines.append("[BLOCK] governance checks mutated Git-visible repository state:")
        lines.extend(f"  {change}" for change in report.state_changes)
    lines.append("=" * 72)
    lines.append("PASS: document governance gate" if report.passed else "BLOCK: document governance gate")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run one registered governance profile")
    run.add_argument("--repo-root", type=Path, default=ROOT)
    run.add_argument("--profile")
    run.add_argument("--base", help="Git base revision for diff-aware lanes")
    run.add_argument("--lane", action="append", default=[], help="restrict to a lane in the selected profile")
    run.add_argument("--json", action="store_true")

    list_parser = subparsers.add_parser("list", help="list registered profiles and lanes")
    list_parser.add_argument("--repo-root", type=Path, default=ROOT)
    list_parser.add_argument("--json", action="store_true")

    fingerprint = subparsers.add_parser("fingerprint", help="print the current Git-visible-state receipt")
    fingerprint.add_argument("--repo-root", type=Path, default=ROOT)
    fingerprint.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "run":
            report = run_gate(
                root=args.repo_root,
                profile=args.profile,
                base=args.base,
                lane_filter=args.lane,
            )
            if args.json:
                print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(_render_report(report), end="")
            return 0 if report.passed else 1

        if args.command == "list":
            _manifest, config = load_gate_configuration(args.repo_root.resolve())
            payload = {
                "default_profile": config["runner"]["default_profile"],
                "profiles": config["profiles"],
                "lanes": config["lanes"],
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"default profile: {payload['default_profile']}")
                for profile_id, record in payload["profiles"].items():
                    print(f"{profile_id}: {', '.join(record['lane_ids'])}")
            return 0

        if args.command == "fingerprint":
            state = capture_git_visible_state(args.repo_root)
            if args.json:
                print(json.dumps(state.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(state.digest)
            return 0
    except GovernanceGateError as exc:
        print(f"document governance gate failed: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
