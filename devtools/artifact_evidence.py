#!/usr/bin/env python3
"""Build and validate the repository evidence boundary.

Evidence can be present in three materially different ways:

* ``git_tracked``: durable paths whose bytes are in the current Git index;
* ``workspace_untracked``: local evidence that may exist in the shared worktree
  but is intentionally not durable in Git;
* ``external_root``: hash-bound material restored through a separate manifest.

The frozen production boundary still consumes the schema-v1
``data/artifact_boundaries.json`` projection.  That compatibility file is
therefore generated from *only* the ``git_tracked`` declarations.  Code-asset
inventory, in contrast, uses this module's semantic boundary and can recognise
both tracked and workspace evidence without pretending that the latter is
tracked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import jsonschema  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = "data/artifact_boundaries.json"
DEFAULT_SCHEMA = "data/repository_governance/artifact_boundaries.schema.json"
DEFAULT_INPUTS = "data/repository_governance/artifact_evidence_inputs.json"
DEFAULT_INPUTS_SCHEMA = (
    "data/repository_governance/artifact_evidence_inputs.schema.json"
)
TRACKED_REASON = "Explicit git-tracked historical evidence declaration."
TRACKED_ROOT_FILE_REASON = (
    "Explicit git-tracked root-level artifact evidence/control file retained in place."
)
GIT_QUOTED_REASON = (
    "Generated compatibility prefix for the frozen line-oriented git ls-files checker."
)


class ArtifactEvidenceError(RuntimeError):
    """A fail-closed artifact-evidence boundary error."""


@dataclass(frozen=True)
class ArtifactEvidenceBoundary:
    root_prefix: str
    dossier_registry: str
    # ``registered_roots`` remains the compatibility name used by code-asset
    # consumers.  In v2 these are local workspace evidence roots, not an
    # assertion that every file below them is tracked.
    registered_roots: tuple[str, ...]
    tracked_root_files: tuple[str, ...]
    ignored_runtime_prefixes: tuple[str, ...]
    tracked_prefixes: tuple[str, ...] = ()
    tracked_files: tuple[str, ...] = ()
    workspace_root_files: tuple[str, ...] = ()
    external_registry: str | None = None
    expected_tracked_path_count: int | None = None

    def covers_tracked(self, path: str) -> bool:
        return (
            path in self.tracked_root_files
            or path in self.tracked_files
            or any(path.startswith(prefix) for prefix in self.tracked_prefixes)
        )

    def covers_workspace(self, path: str) -> bool:
        return path in self.workspace_root_files or any(
            path.startswith(root) for root in self.registered_roots
        )

    def covers(self, path: str) -> bool:
        """Return whether ``path`` belongs to any declared in-worktree evidence state."""

        return self.covers_tracked(path) or self.covers_workspace(path)

    def storage_class_for(self, path: str) -> str | None:
        if self.covers_tracked(path):
            return "git_tracked"
        if self.covers_workspace(path):
            return "workspace_untracked"
        return None

    def is_artifact_path(self, path: str) -> bool:
        return path.startswith(self.root_prefix)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactEvidenceError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ArtifactEvidenceError(f"non-finite JSON constant: {value}")


def _read_json_object(path: Path, root: Path) -> dict[str, Any]:
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
        raise ArtifactEvidenceError(f"cannot read strict JSON {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactEvidenceError(f"{path}: JSON root must be an object")
    return value


def _validate_schema_pair(
    root: Path,
    payload_relpath: str,
    schema_relpath: str,
    *,
    label: str,
) -> dict[str, Any]:
    payload = _read_json_object(root / payload_relpath, root)
    schema = _read_json_object(root / schema_relpath, root)
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(payload),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except jsonschema.SchemaError as exc:
        raise ArtifactEvidenceError(f"{label} schema is invalid: {exc.message}") from exc
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ArtifactEvidenceError(
            f"{label} schema validation failed at {location}: {error.message}"
        )
    return payload


def _validate_relpath(
    value: str,
    label: str,
    *,
    trailing_slash: bool | None = None,
) -> str:
    pure = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or ".." in pure.parts
        or "\\" in value
        or "\0" in value
    ):
        raise ArtifactEvidenceError(
            f"{label} is not a safe repository-relative path: {value!r}"
        )
    if trailing_slash is True and not value.endswith("/"):
        raise ArtifactEvidenceError(f"{label} must end in '/': {value!r}")
    if trailing_slash is False and value.endswith("/"):
        raise ArtifactEvidenceError(f"{label} must name a file: {value!r}")
    return value


def _validate_sorted_unique(values: Sequence[str], label: str) -> tuple[str, ...]:
    if list(values) != sorted(values):
        raise ArtifactEvidenceError(f"{label} must be sorted")
    if len(values) != len(set(values)):
        raise ArtifactEvidenceError(f"{label} contains duplicates")
    return tuple(values)


def _parse_nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(os.fsdecode(item) for item in raw.split(b"\0") if item)


def git_tracked_paths(root: Path = ROOT, prefix: str | None = None) -> tuple[str, ...]:
    args = ["git", "ls-files", "--cached", "-z"]
    if prefix is not None:
        args.extend(["--", prefix])
    completed = subprocess.run(
        args,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise ArtifactEvidenceError(f"git ls-files failed: {stderr}")
    return tuple(sorted(_parse_nul_paths(completed.stdout)))


def git_untracked_paths(root: Path = ROOT, prefix: str | None = None) -> tuple[str, ...]:
    """Return non-ignored workspace paths without changing their Git state."""

    args = ["git", "ls-files", "--others", "--exclude-standard", "-z"]
    if prefix is not None:
        args.extend(["--", prefix])
    completed = subprocess.run(
        args,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise ArtifactEvidenceError(f"git ls-files --others failed: {stderr}")
    return tuple(sorted(_parse_nul_paths(completed.stdout)))


def _registered_dossier_roots(
    root: Path,
    dossier_registry: str,
    root_prefix: str,
    required_tracked_state: str,
) -> tuple[str, ...]:
    dossiers = _read_json_object(root / dossier_registry, root)
    records = dossiers.get("records")
    if not isinstance(records, list):
        raise ArtifactEvidenceError("dossier registry must contain records[]")

    roots: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ArtifactEvidenceError(f"dossier records[{index}] must be an object")
        path = record.get("path")
        if not isinstance(path, str) or not path.startswith(root_prefix):
            continue
        tracked_state = record.get("tracked_state")
        if tracked_state != required_tracked_state:
            raise ArtifactEvidenceError(
                f"artifact dossier {path!r} must declare tracked_state="
                f"{required_tracked_state!r}, got {tracked_state!r}"
            )
        parts = PurePosixPath(path).parts
        if len(parts) != 2 or path != f".artifacts/{parts[1]}":
            raise ArtifactEvidenceError(
                f"artifact dossier must be a direct child of .artifacts/: {path!r}"
            )
        roots.append(f"{path}/")
    return _validate_sorted_unique(sorted(roots), "registered artifact dossier roots")


def _projection_records(
    tracked_prefixes: Sequence[str],
    tracked_files: Sequence[str],
    tracked_root_files: Sequence[str],
) -> list[dict[str, str]]:
    reasons = {path: TRACKED_REASON for path in tracked_prefixes}
    reasons.update({path: TRACKED_REASON for path in tracked_files})
    reasons.update({path: TRACKED_ROOT_FILE_REASON for path in tracked_root_files})

    # The certified v1 checker consumes line-oriented ``git ls-files`` output.
    # Git may wrap non-ASCII paths in a leading quote before C-escaping bytes.
    # Quoted counterparts are compatibility-only records; semantic matching
    # uses the unquoted declarations above.
    reasons.update({f'"{path}': GIT_QUOTED_REASON for path in tuple(reasons)})
    return [
        {"path_prefix": path, "reason": reasons[path]}
        for path in sorted(reasons)
    ]


def _parse_direct_files(
    values: Sequence[Any],
    *,
    label: str,
    root_prefix: str,
    require_root: bool,
) -> tuple[str, ...]:
    parsed = tuple(str(value) for value in values)
    for index, value in enumerate(parsed):
        _validate_relpath(value, f"{label}[{index}]", trailing_slash=False)
        if not value.startswith(root_prefix):
            raise ArtifactEvidenceError(f"{label}[{index}] leaves {root_prefix!r}: {value!r}")
        if require_root and PurePosixPath(value).parent.as_posix() != root_prefix.rstrip("/"):
            raise ArtifactEvidenceError(
                f"{label} entries must be direct files below {root_prefix}: {value!r}"
            )
    return _validate_sorted_unique(parsed, label)


def _parse_prefixes(
    values: Sequence[Any],
    *,
    label: str,
    root_prefix: str,
) -> tuple[str, ...]:
    parsed = tuple(str(value) for value in values)
    for index, value in enumerate(parsed):
        _validate_relpath(value, f"{label}[{index}]", trailing_slash=True)
        if not value.startswith(root_prefix):
            raise ArtifactEvidenceError(f"{label}[{index}] leaves {root_prefix!r}: {value!r}")
    return _validate_sorted_unique(parsed, label)


def _parse_inputs(
    root: Path,
    inputs: Mapping[str, Any],
    *,
    require_external_registry: bool = True,
) -> ArtifactEvidenceBoundary:
    root_prefix = _validate_relpath(
        str(inputs["root_prefix"]),
        "root_prefix",
        trailing_slash=True,
    )
    if root_prefix != ".artifacts/":
        raise ArtifactEvidenceError("artifact evidence root_prefix must remain '.artifacts/'")

    git_tracked = inputs["git_tracked"]
    workspace = inputs["workspace_untracked"]
    external = inputs["external_root"]
    if not isinstance(git_tracked, Mapping):
        raise ArtifactEvidenceError("git_tracked must be an object")
    if not isinstance(workspace, Mapping):
        raise ArtifactEvidenceError("workspace_untracked must be an object")
    if not isinstance(external, Mapping):
        raise ArtifactEvidenceError("external_root must be an object")

    tracked_root_files = _parse_direct_files(
        git_tracked["root_files"],
        label="git_tracked.root_files",
        root_prefix=root_prefix,
        require_root=True,
    )
    tracked_files = _parse_direct_files(
        git_tracked["files"],
        label="git_tracked.files",
        root_prefix=root_prefix,
        require_root=False,
    )
    tracked_prefixes = _parse_prefixes(
        git_tracked["path_prefixes"],
        label="git_tracked.path_prefixes",
        root_prefix=root_prefix,
    )
    expected_tracked_path_count = int(git_tracked["expected_path_count"])

    dossier_registry = _validate_relpath(
        str(workspace["dossier_registry"]),
        "workspace_untracked.dossier_registry",
        trailing_slash=False,
    )
    required_tracked_state = str(workspace["required_dossier_tracked_state"])
    workspace_roots = _registered_dossier_roots(
        root,
        dossier_registry,
        root_prefix,
        required_tracked_state,
    )
    workspace_root_files = _parse_direct_files(
        workspace["root_files"],
        label="workspace_untracked.root_files",
        root_prefix=root_prefix,
        require_root=True,
    )

    external_registry = _validate_relpath(
        str(external["registry"]),
        "external_root.registry",
        trailing_slash=False,
    )
    if require_external_registry and not (root / external_registry).is_file():
        raise ArtifactEvidenceError(
            f"external evidence registry is missing: {external_registry}"
        )

    ignored = _parse_prefixes(
        inputs["ignored_runtime_artifact_prefixes"],
        label="ignored_runtime_artifact_prefixes",
        root_prefix="",
    )

    tracked_paths = set(tracked_root_files) | set(tracked_files)
    if tracked_paths & set(workspace_root_files):
        overlap = sorted(tracked_paths & set(workspace_root_files))
        raise ArtifactEvidenceError(
            "artifact evidence file appears in both git_tracked and workspace_untracked: "
            + ", ".join(overlap)
        )
    for tracked_prefix in tracked_prefixes:
        if any(
            tracked_prefix.startswith(workspace_root) or workspace_root.startswith(tracked_prefix)
            for workspace_root in workspace_roots
        ):
            # A tracked historical slice may intentionally live inside a broader
            # local dossier.  Longest/specific matching therefore chooses
            # git_tracked for those files; this overlap is allowed.
            continue

    all_evidence_roots = tuple(sorted(set(workspace_roots) | set(tracked_prefixes)))
    all_evidence_files = tracked_paths | set(workspace_root_files)
    for ignored_prefix in ignored:
        for evidence_root in all_evidence_roots:
            if ignored_prefix.startswith(evidence_root) or evidence_root.startswith(ignored_prefix):
                raise ArtifactEvidenceError(
                    "ignored runtime prefix overlaps registered evidence root: "
                    f"{ignored_prefix!r}, {evidence_root!r}"
                )
        if any(path.startswith(ignored_prefix) for path in all_evidence_files):
            raise ArtifactEvidenceError(
                "ignored runtime prefix overlaps registered evidence file: "
                f"{ignored_prefix!r}"
            )

    return ArtifactEvidenceBoundary(
        root_prefix=root_prefix,
        dossier_registry=dossier_registry,
        registered_roots=workspace_roots,
        tracked_root_files=tracked_root_files,
        ignored_runtime_prefixes=ignored,
        tracked_prefixes=tracked_prefixes,
        tracked_files=tracked_files,
        workspace_root_files=workspace_root_files,
        external_registry=external_registry,
        expected_tracked_path_count=expected_tracked_path_count,
    )


def _boundary_from_inputs(
    root: Path,
    inputs: Mapping[str, Any],
    *,
    require_external_registry: bool = True,
) -> ArtifactEvidenceBoundary:
    """Parse the semantic evidence model without consulting its projection."""

    return _parse_inputs(
        root,
        inputs,
        require_external_registry=require_external_registry,
    )


def _parse_boundary(
    root: Path,
    manifest: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> ArtifactEvidenceBoundary:
    boundary = _boundary_from_inputs(root, inputs)

    if str(manifest["root_prefix"]) != boundary.root_prefix:
        raise ArtifactEvidenceError("artifact boundary root_prefix is stale")
    if str(manifest["projection_source"]) != DEFAULT_INPUTS:
        raise ArtifactEvidenceError("artifact boundary projection_source is stale")
    if tuple(str(value) for value in manifest["tracked_root_files"]) != boundary.tracked_root_files:
        raise ArtifactEvidenceError(
            "artifact boundary tracked_root_files is stale; rebuild the compatibility projection"
        )
    if (
        tuple(str(value) for value in manifest["ignored_runtime_artifact_prefixes"])
        != boundary.ignored_runtime_prefixes
    ):
        raise ArtifactEvidenceError(
            "artifact boundary ignored runtime prefixes are stale; rebuild the compatibility projection"
        )

    records = manifest["tracked_historical_evidence"]
    actual_prefixes = tuple(str(record["path_prefix"]) for record in records)
    _validate_sorted_unique(
        actual_prefixes,
        "tracked_historical_evidence path_prefix values",
    )
    expected_records = _projection_records(
        boundary.tracked_prefixes,
        boundary.tracked_files,
        boundary.tracked_root_files,
    )
    if list(records) != expected_records:
        raise ArtifactEvidenceError(
            "tracked_historical_evidence is stale; rebuild it from the explicit "
            "git_tracked evidence inputs"
        )
    return boundary


def load_semantic_boundary(
    root: Path = ROOT,
    *,
    inputs_relpath: str = DEFAULT_INPUTS,
    inputs_schema_relpath: str = DEFAULT_INPUTS_SCHEMA,
) -> ArtifactEvidenceBoundary:
    """Load storage classes without requiring the generated projection to be fresh."""

    root = root.resolve()
    inputs_relpath = _validate_relpath(
        inputs_relpath,
        "artifact inputs",
        trailing_slash=False,
    )
    inputs_schema_relpath = _validate_relpath(
        inputs_schema_relpath,
        "artifact inputs schema",
        trailing_slash=False,
    )
    inputs = _validate_schema_pair(
        root,
        inputs_relpath,
        inputs_schema_relpath,
        label="artifact evidence inputs",
    )
    return _boundary_from_inputs(
        root,
        inputs,
        require_external_registry=False,
    )

def load_boundary(
    root: Path = ROOT,
    *,
    manifest_relpath: str = DEFAULT_MANIFEST,
    schema_relpath: str = DEFAULT_SCHEMA,
    inputs_relpath: str = DEFAULT_INPUTS,
    inputs_schema_relpath: str = DEFAULT_INPUTS_SCHEMA,
) -> ArtifactEvidenceBoundary:
    root = root.resolve()
    paths = {
        "artifact manifest": (manifest_relpath, False),
        "artifact schema": (schema_relpath, False),
        "artifact inputs": (inputs_relpath, False),
        "artifact inputs schema": (inputs_schema_relpath, False),
    }
    validated: dict[str, str] = {}
    for label, (value, trailing_slash) in paths.items():
        validated[label] = _validate_relpath(value, label, trailing_slash=trailing_slash)
    manifest = _validate_schema_pair(
        root,
        validated["artifact manifest"],
        validated["artifact schema"],
        label="artifact boundary",
    )
    inputs = _validate_schema_pair(
        root,
        validated["artifact inputs"],
        validated["artifact inputs schema"],
        label="artifact evidence inputs",
    )
    return _parse_boundary(root, manifest, inputs)


def render_projection(
    root: Path = ROOT,
    *,
    inputs_relpath: str = DEFAULT_INPUTS,
    inputs_schema_relpath: str = DEFAULT_INPUTS_SCHEMA,
) -> str:
    """Render the frozen schema-v1 projection from git-tracked inputs only."""

    root = root.resolve()
    inputs_relpath = _validate_relpath(inputs_relpath, "artifact inputs", trailing_slash=False)
    inputs_schema_relpath = _validate_relpath(
        inputs_schema_relpath,
        "artifact inputs schema",
        trailing_slash=False,
    )
    inputs = _validate_schema_pair(
        root,
        inputs_relpath,
        inputs_schema_relpath,
        label="artifact evidence inputs",
    )
    boundary = _parse_inputs(root, inputs)
    payload = {
        "schema_version": 1,
        "description": (
            "Generated compatibility projection for the frozen artifact-boundary checker; "
            "only git_tracked evidence is projected. Workspace and external evidence states "
            "remain in data/repository_governance/artifact_evidence_inputs.json."
        ),
        "root_prefix": boundary.root_prefix,
        "projection_source": DEFAULT_INPUTS,
        "tracked_root_files": list(boundary.tracked_root_files),
        "tracked_historical_evidence": _projection_records(
            boundary.tracked_prefixes,
            boundary.tracked_files,
            boundary.tracked_root_files,
        ),
        "ignored_runtime_artifact_prefixes": list(boundary.ignored_runtime_prefixes),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_projection(
    root: Path = ROOT,
    *,
    manifest_relpath: str = DEFAULT_MANIFEST,
    inputs_relpath: str = DEFAULT_INPUTS,
    inputs_schema_relpath: str = DEFAULT_INPUTS_SCHEMA,
) -> None:
    output = root / manifest_relpath
    content = render_projection(
        root,
        inputs_relpath=inputs_relpath,
        inputs_schema_relpath=inputs_schema_relpath,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output.parent,
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, output)


def validate_tracked_paths(
    boundary: ArtifactEvidenceBoundary,
    tracked_paths: Iterable[str],
) -> tuple[str, ...]:
    """Validate that every tracked artifact is explicitly ``git_tracked``.

    A path being covered by a workspace dossier is intentionally insufficient:
    that would recreate the sandbox topology error this model is designed to
    prevent.
    """

    tracked = tuple(sorted(set(tracked_paths)))
    artifact_paths = tuple(path for path in tracked if boundary.is_artifact_path(path))
    undeclared = tuple(path for path in artifact_paths if not boundary.covers_tracked(path))
    if undeclared:
        preview = ", ".join(undeclared[:10])
        suffix = f" (+{len(undeclared) - 10} more)" if len(undeclared) > 10 else ""
        raise ArtifactEvidenceError(
            "tracked .artifacts path lacks git_tracked declaration: "
            f"{preview}{suffix}"
        )

    tracked_root_files = tuple(
        path
        for path in artifact_paths
        if PurePosixPath(path).parent.as_posix() == ".artifacts"
    )
    missing_root_declarations = tuple(
        path for path in tracked_root_files if path not in boundary.tracked_root_files
    )
    if missing_root_declarations:
        raise ArtifactEvidenceError(
            "tracked .artifacts root file lacks explicit git_tracked declaration: "
            + ", ".join(missing_root_declarations)
        )
    stale_root_files = tuple(
        path for path in boundary.tracked_root_files if path not in artifact_paths
    )
    if stale_root_files:
        raise ArtifactEvidenceError(
            "declared .artifacts root file is not tracked: " + ", ".join(stale_root_files)
        )
    tracked_ignored = tuple(
        path
        for path in tracked
        if any(path.startswith(prefix) for prefix in boundary.ignored_runtime_prefixes)
    )
    if tracked_ignored:
        raise ArtifactEvidenceError(
            "ignored runtime artifact prefix contains tracked path: "
            + ", ".join(tracked_ignored[:10])
        )
    if (
        boundary.expected_tracked_path_count is not None
        and len(artifact_paths) != boundary.expected_tracked_path_count
    ):
        raise ArtifactEvidenceError(
            "tracked .artifacts count does not match the real-repository census: "
            f"expected {boundary.expected_tracked_path_count}, got {len(artifact_paths)}"
        )
    return artifact_paths


def validate_workspace_paths(
    boundary: ArtifactEvidenceBoundary,
    workspace_paths: Iterable[str],
) -> tuple[str, ...]:
    """Validate explicitly observed untracked artifact paths without requiring them."""

    workspace = tuple(
        sorted(
            path
            for path in set(workspace_paths)
            if boundary.is_artifact_path(path)
            and not any(path.startswith(prefix) for prefix in boundary.ignored_runtime_prefixes)
        )
    )
    undeclared = tuple(path for path in workspace if not boundary.covers_workspace(path))
    if undeclared:
        preview = ", ".join(undeclared[:10])
        suffix = f" (+{len(undeclared) - 10} more)" if len(undeclared) > 10 else ""
        raise ArtifactEvidenceError(
            f"workspace-untracked .artifacts path lacks local evidence declaration: {preview}{suffix}"
        )
    return workspace


def load_and_validate_tracked_boundary(
    root: Path = ROOT,
    *,
    manifest_relpath: str = DEFAULT_MANIFEST,
    schema_relpath: str = DEFAULT_SCHEMA,
    inputs_relpath: str = DEFAULT_INPUTS,
    inputs_schema_relpath: str = DEFAULT_INPUTS_SCHEMA,
) -> ArtifactEvidenceBoundary:
    boundary = load_boundary(
        root,
        manifest_relpath=manifest_relpath,
        schema_relpath=schema_relpath,
        inputs_relpath=inputs_relpath,
        inputs_schema_relpath=inputs_schema_relpath,
    )
    validate_tracked_paths(
        boundary,
        git_tracked_paths(root, boundary.root_prefix.rstrip("/")),
    )
    return boundary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "render"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "render":
            if args.write:
                write_projection(ROOT)
                print(f"wrote {DEFAULT_MANIFEST}")
            else:
                print(render_projection(ROOT), end="")
            return 0
        load_and_validate_tracked_boundary(ROOT)
    except ArtifactEvidenceError as exc:
        print(f"artifact evidence check failed: {exc}")
        return 1
    print("artifact evidence check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
