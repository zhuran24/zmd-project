#!/usr/bin/env python3
"""Recompute and validate the repository code-asset governance projection.

This module is developer tooling.  It intentionally lives outside root-level
Python, ``src`` and ``scripts`` so adding it cannot expand the certified exact
source tree.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Mapping, Sequence

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "repository_governance" / "code_assets.json"
SCHEMA_PATH = ROOT / "data" / "repository_governance" / "code_assets.schema.json"

PRIMARY_CLASSES = (
    "active_implementation",
    "test",
    "common_infrastructure",
    "authoritative_input",
    "enforcement_control",
    "historical_evidence",
    "retirement_candidate",
)
PYTEST_LANES = frozenset({"developer", "evidence", "replay"})
READ_ONLY_HISTORICAL_EVIDENCE_NATURES = frozenset(
    {"research_evidence", "failed_campaign_history"}
)
READ_ONLY_HISTORICAL_EVIDENCE_FIELDS = frozenset(
    {
        "path",
        "nature",
        "content_treatment",
        "mutation_expectation",
        "rationale",
    }
)
AUTHORITY_ASSET_ROLES = frozenset(
    {
        "certified_source_of_truth",
        "current_enforcement_control",
        "current_governing_specification",
        "external_authority_manifest",
    }
)
SOURCE_DISCOVERY_MODULES = (
    "src.search.exact_campaign",
    "src.search.pr2_l0_artifact_core",
)


class GovernanceError(RuntimeError):
    """A fail-closed governance validation error."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GovernanceError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise GovernanceError(f"non-finite JSON constant: {value}")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"cannot read strict JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceError(f"{path.relative_to(ROOT)} root must be an object")
    return value


def load_manifest() -> dict[str, Any]:
    return _load_json_object(MANIFEST_PATH)


def _validate_against_schema(schema: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
    except jsonschema.SchemaError as exc:
        raise GovernanceError(f"repository code asset schema is invalid: {exc.message}") from exc
    errors = sorted(
        validator.iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise GovernanceError(f"manifest schema validation failed at {location}: {error.message}")


def _run_git(args: Sequence[str], *, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise GovernanceError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout


def git_visible_paths() -> tuple[str, ...]:
    raw = _run_git(["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    paths = tuple(sorted(_parse_nul_paths(raw)))
    _validate_path_set(paths)
    return paths


def _parse_nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(os.fsdecode(item) for item in raw.split(b"\0") if item)


def _parse_ls_tree_records(raw: bytes) -> tuple[tuple[str, str], ...]:
    entries: list[tuple[str, str]] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            object_id_raw, path_raw = item.split(b"\t", 1)
        except ValueError as exc:
            raise GovernanceError("git ls-tree emitted a malformed NUL record") from exc
        try:
            object_id = object_id_raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise GovernanceError("git ls-tree emitted a non-ASCII object id") from exc
        entries.append((object_id, os.fsdecode(path_raw)))
    return tuple(entries)


def _validate_path_set(paths: Sequence[str]) -> None:
    if len(paths) != len(set(paths)):
        raise GovernanceError("repository path enumeration contains duplicates")
    for path in paths:
        pure = PurePosixPath(path)
        if path.startswith("/") or ".." in pure.parts or "\\" in path or "\0" in path:
            raise GovernanceError(f"unsafe repository path: {path!r}")


def _read_only_historical_evidence_roots(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    records = manifest.get("read_only_historical_evidence_roots")
    if not isinstance(records, list) or not records:
        raise GovernanceError("read_only_historical_evidence_roots must be a non-empty list")

    roots: list[str] = []
    for index, record in enumerate(records):
        label = f"read_only_historical_evidence_roots[{index}]"
        if not isinstance(record, dict) or set(record) != READ_ONLY_HISTORICAL_EVIDENCE_FIELDS:
            raise GovernanceError(f"{label} has invalid fields")
        path = record["path"]
        if not isinstance(path, str):
            raise GovernanceError(f"{label}.path must be a string")
        _validate_repository_pattern(path, f"{label}.path")
        parts = PurePosixPath(path).parts
        if (
            len(parts) != 2
            or parts[0] != ".artifacts"
            or path != f".artifacts/{parts[1]}/"
            or any(character in parts[1] for character in "*?[")
        ):
            raise GovernanceError(
                f"{label}.path must be an exact top-level .artifacts root with a trailing slash"
            )
        if record["nature"] not in READ_ONLY_HISTORICAL_EVIDENCE_NATURES:
            raise GovernanceError(f"{label}.nature is invalid")
        if record["content_treatment"] != "non_code_asset":
            raise GovernanceError(f"{label}.content_treatment must remain non_code_asset")
        if record["mutation_expectation"] != "read_only_preserve_in_place":
            raise GovernanceError(
                f"{label}.mutation_expectation must remain read_only_preserve_in_place"
            )
        if not isinstance(record["rationale"], str) or not record["rationale"].strip():
            raise GovernanceError(f"{label}.rationale must be a non-empty string")
        roots.append(path)

    if roots != sorted(roots):
        raise GovernanceError("read-only historical evidence roots must be sorted by path")
    if len(roots) != len(set(roots)):
        raise GovernanceError("read-only historical evidence roots contain duplicate paths")
    for index, root in enumerate(roots):
        for other in roots[index + 1 :]:
            if root.startswith(other) or other.startswith(root):
                raise GovernanceError(
                    "read-only historical evidence roots must not overlap: "
                    f"{root!r} and {other!r}"
                )
    return tuple(roots)


def _is_read_only_historical_evidence_path(
    path: str,
    roots: Sequence[str],
) -> bool:
    return any(path.startswith(root) for root in roots)


def _validate_read_only_historical_evidence_roots(manifest: Mapping[str, Any]) -> None:
    roots = _read_only_historical_evidence_roots(manifest)
    tracked = _parse_nul_paths(_run_git(["ls-files", "--cached", "-z"]))
    covered_tracked = sorted(
        path for path in tracked if _is_read_only_historical_evidence_path(path, roots)
    )
    if covered_tracked:
        raise GovernanceError(
            "read-only historical evidence roots must not cover tracked paths: "
            f"{covered_tracked!r}"
        )


def _current_bytes(path: str) -> bytes:
    absolute = ROOT / path
    if absolute.is_symlink():
        return os.fsencode(os.readlink(absolute))
    try:
        return absolute.read_bytes()
    except OSError as exc:
        raise GovernanceError(f"cannot read repository asset {path}: {exc}") from exc


def _commit_blobs(commit: str) -> dict[str, bytes]:
    tree = _run_git(
        [
            "-c",
            "core.quotePath=false",
            "ls-tree",
            "-rz",
            "--full-tree",
            "--format=%(objectname)%x09%(path)",
            commit,
        ]
    )
    entries = list(_parse_ls_tree_records(tree))
    paths = [path for _object_id, path in entries]
    _validate_path_set(paths)

    completed = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        input=b"".join(object_id.encode("ascii") + b"\n" for object_id, _ in entries),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise GovernanceError(f"git cat-file --batch failed: {stderr}")
    stream = io.BytesIO(completed.stdout)
    blobs: dict[str, bytes] = {}
    for expected_object_id, path in entries:
        header = stream.readline()
        parts = header.rstrip(b"\n").split()
        if (
            len(parts) != 3
            or parts[0].decode("ascii") != expected_object_id
            or parts[1] != b"blob"
        ):
            raise GovernanceError(f"git cat-file emitted an invalid header for {path}")
        size = int(parts[2])
        payload = stream.read(size)
        terminator = stream.read(1)
        if len(payload) != size or terminator != b"\n":
            raise GovernanceError(f"git cat-file emitted a truncated blob for {path}")
        blobs[path] = payload
    if stream.read(1):
        raise GovernanceError("git cat-file emitted trailing batch data")
    return blobs


def _matches_glob(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def _matches(path: str, matcher: Mapping[str, Any]) -> bool:
    if len(matcher) != 1:
        raise GovernanceError(f"match object must contain exactly one selector: {matcher!r}")
    if "path" in matcher:
        return path == matcher["path"]
    if "prefix" in matcher:
        prefix = matcher["prefix"]
        return isinstance(prefix, str) and path.startswith(prefix)
    if "glob" in matcher:
        pattern = matcher["glob"]
        return isinstance(pattern, str) and _matches_glob(path, pattern)
    if "paths" in matcher:
        values = matcher["paths"]
        if not isinstance(values, list):
            raise GovernanceError("match.paths must be a list")
        return any(
            path.startswith(value) if isinstance(value, str) and value.endswith("/") else path == value
            for value in values
        )
    raise GovernanceError(f"unsupported match selector: {matcher!r}")


def _is_code_asset(path: str, raw: bytes, selector: Mapping[str, Any]) -> bool:
    extensions = selector["extensions"]
    if PurePosixPath(path).suffix in extensions:
        return True
    if selector["include_shebang"] and raw.startswith(b"#!"):
        return True
    if path in selector["explicit_paths"]:
        return True
    return any(_matches_glob(path, pattern) for pattern in selector["explicit_globs"])


def _classification_for(path: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    classification = manifest["classification"]
    for rule in classification["rules"]:
        if _matches(path, rule["match"]):
            result = dict(rule)
            result.pop("match")
            return result
    result = dict(classification["fallback"])
    result["id"] = "fallback"
    return result


def _asset_role_for(path: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    role_rules = manifest["asset_role_rules"]
    for rule in role_rules["rules"]:
        if _matches(path, rule["match"]):
            result = dict(rule)
            result.pop("match")
            return result
    result = dict(role_rules["fallback"])
    result["id"] = "fallback"
    return result


def _measurement(
    paths_and_bytes: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    *,
    include_assets: bool,
    git_visible_count: int | None = None,
    exclude_read_only_historical_evidence: bool = True,
) -> dict[str, Any]:
    selector = manifest["code_selector"]
    read_only_roots = (
        _read_only_historical_evidence_roots(manifest)
        if exclude_read_only_historical_evidence
        else ()
    )
    class_counts = {name: 0 for name in PRIMARY_CLASSES}
    raw_bytes = 0
    lf_count = 0
    assets: list[dict[str, Any]] = []
    for path in sorted(paths_and_bytes):
        if _is_read_only_historical_evidence_path(path, read_only_roots):
            continue
        raw = paths_and_bytes[path]
        if not _is_code_asset(path, raw, selector):
            continue
        classification = _classification_for(path, manifest)
        primary_class = classification["primary_class"]
        if primary_class not in class_counts:
            raise GovernanceError(f"{path}: unsupported primary class {primary_class!r}")
        class_counts[primary_class] += 1
        raw_bytes += len(raw)
        lf_count += raw.count(b"\n")
        if include_assets:
            assets.append(
                {
                    "path": path,
                    "primary_class": primary_class,
                    "rule_id": classification["id"],
                    "lifecycle": classification["lifecycle"],
                    "authority_role": classification["authority_role"],
                    "certified_admission": classification["certified_admission"],
                    "workflow_membership": classification["workflow_membership"],
                    "mutation_policy": classification["mutation_policy"],
                    "raw_bytes": len(raw),
                    "lf_count": raw.count(b"\n"),
                }
            )
    result: dict[str, Any] = {
        "git_visible_count": len(paths_and_bytes) if git_visible_count is None else git_visible_count,
        "code_asset_count": sum(class_counts.values()),
        "raw_bytes": raw_bytes,
        "lf_count": lf_count,
        "class_counts": class_counts,
    }
    if include_assets:
        result["assets"] = assets
    return result


def inventory(*, commit: str | None = None, include_assets: bool = True) -> dict[str, Any]:
    manifest = load_manifest()
    read_only_roots = _read_only_historical_evidence_roots(manifest)
    if commit is None:
        paths = git_visible_paths()
        blobs = {
            path: _current_bytes(path)
            for path in paths
            if not _is_read_only_historical_evidence_path(path, read_only_roots)
        }
        git_visible_count = len(paths)
        revision = "WORKTREE"
    else:
        blobs = _commit_blobs(commit)
        git_visible_count = len(blobs)
        revision = _run_git(["rev-parse", "--verify", f"{commit}^{{commit}}"]).decode().strip()
    result = _measurement(
        blobs,
        manifest,
        include_assets=include_assets,
        git_visible_count=git_visible_count,
        exclude_read_only_historical_evidence=commit is None,
    )
    result["revision"] = revision
    return result


def _require_string_list(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise GovernanceError(f"{label} must be {'a non-empty' if nonempty else 'a'} list")
    if any(not isinstance(item, str) or not item for item in value):
        raise GovernanceError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise GovernanceError(f"{label} contains duplicates")
    return value


def _validate_repository_pattern(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise GovernanceError(f"{label} must be a non-empty string")
    pure = PurePosixPath(value)
    if value.startswith("/") or ".." in pure.parts or "\\" in value or "\0" in value:
        raise GovernanceError(f"{label} is not a safe repository-relative pattern")
    return value


def _validate_match(matcher: Any, label: str) -> None:
    if not isinstance(matcher, dict) or len(matcher) != 1:
        raise GovernanceError(f"{label} must contain exactly one selector")
    key, value = next(iter(matcher.items()))
    if key in {"path", "prefix", "glob"}:
        _validate_repository_pattern(value, f"{label}.{key}")
        return
    if key == "paths":
        values = _require_string_list(value, f"{label}.paths", nonempty=True)
        for index, item in enumerate(values):
            _validate_repository_pattern(item, f"{label}.paths[{index}]")
        return
    raise GovernanceError(f"{label} has unsupported selector {key!r}")


def _validate_manifest_shape(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != "repository_code_assets_v1":
        raise GovernanceError("unsupported manifest schema_version")
    if manifest.get("authority", {}).get("role") != "descriptive_governance_projection":
        raise GovernanceError("manifest must remain a descriptive governance projection")

    selector = manifest.get("code_selector")
    if not isinstance(selector, dict):
        raise GovernanceError("code_selector must be an object")
    extensions = _require_string_list(selector.get("extensions"), "code_selector.extensions", nonempty=True)
    if any(not extension.startswith(".") for extension in extensions):
        raise GovernanceError("code_selector.extensions entries must start with '.'")
    if selector.get("include_shebang") is not True:
        raise GovernanceError("code_selector.include_shebang must remain true")
    for field in ("explicit_paths", "explicit_globs"):
        for index, value in enumerate(
            _require_string_list(selector.get(field), f"code_selector.{field}")
        ):
            _validate_repository_pattern(value, f"code_selector.{field}[{index}]")

    _read_only_historical_evidence_roots(manifest)

    classification = manifest.get("classification")
    if not isinstance(classification, dict):
        raise GovernanceError("classification must be an object")
    if tuple(classification.get("primary_classes", ())) != PRIMARY_CLASSES:
        raise GovernanceError("classification.primary_classes order or membership drifted")
    rules = classification.get("rules")
    if not isinstance(rules, list) or not rules:
        raise GovernanceError("classification.rules must be a non-empty list")
    rule_ids: set[str] = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise GovernanceError(f"classification.rules[{index}] must be an object")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in rule_ids:
            raise GovernanceError(f"classification rule id is missing or duplicated: {rule_id!r}")
        rule_ids.add(rule_id)
        _validate_match(rule.get("match"), f"classification.rules[{index}].match")
        if rule.get("primary_class") not in PRIMARY_CLASSES:
            raise GovernanceError(f"{rule_id}: invalid primary_class")
        _require_string_list(
            rule.get("workflow_membership"),
            f"{rule_id}.workflow_membership",
            nonempty=True,
        )
        for field in (
            "lifecycle",
            "authority_role",
            "certified_admission",
            "mutation_policy",
            "rationale",
        ):
            if not isinstance(rule.get(field), str) or not rule[field]:
                raise GovernanceError(f"{rule_id}: {field} must be a non-empty string")
    fallback = classification.get("fallback")
    if not isinstance(fallback, dict) or fallback.get("primary_class") not in PRIMARY_CLASSES:
        raise GovernanceError("classification.fallback is invalid")

    role_rules = manifest.get("asset_role_rules")
    if not isinstance(role_rules, dict) or not isinstance(role_rules.get("rules"), list):
        raise GovernanceError("asset_role_rules must contain rules")
    role_ids: set[str] = set()
    for index, rule in enumerate(role_rules["rules"]):
        if not isinstance(rule, dict):
            raise GovernanceError(f"asset_role_rules.rules[{index}] must be an object")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in role_ids:
            raise GovernanceError(f"asset role rule id is missing or duplicated: {rule_id!r}")
        role_ids.add(rule_id)
        _validate_match(rule.get("match"), f"asset_role_rules.rules[{index}].match")

    isolation = manifest.get("logical_isolation")
    if not isinstance(isolation, dict):
        raise GovernanceError("logical_isolation must be an object")
    for projection_name in ("search", "lint"):
        projection = isolation.get(projection_name)
        if not isinstance(projection, dict) or not isinstance(projection.get("enabled"), bool):
            raise GovernanceError(f"logical_isolation.{projection_name} is invalid")
        for index, value in enumerate(
            _require_string_list(
                projection.get("excluded_rules"),
                f"logical_isolation.{projection_name}.excluded_rules",
            )
        ):
            _validate_repository_pattern(
                value,
                f"logical_isolation.{projection_name}.excluded_rules[{index}]",
            )
    pytest_projection = isolation.get("pytest")
    if not isinstance(pytest_projection, dict) or not isinstance(
        pytest_projection.get("enabled"), bool
    ):
        raise GovernanceError("logical_isolation.pytest is invalid")
    lane_rules = pytest_projection.get("lane_rules")
    if not isinstance(lane_rules, list) or not lane_rules:
        raise GovernanceError("logical_isolation.pytest.lane_rules must be non-empty")
    for index, lane_rule in enumerate(lane_rules):
        if not isinstance(lane_rule, dict) or set(lane_rule) != {"glob", "lane"}:
            raise GovernanceError(f"pytest lane rule {index} is invalid")
        _validate_repository_pattern(lane_rule["glob"], f"pytest lane rule {index}.glob")
        if lane_rule["lane"] not in PYTEST_LANES:
            raise GovernanceError(f"pytest lane rule {index} has invalid lane")

    capabilities = manifest.get("capability_index")
    if not isinstance(capabilities, list):
        raise GovernanceError("capability_index must be a list")
    capability_names = [entry.get("capability") for entry in capabilities if isinstance(entry, dict)]
    expected_capabilities = {
        "canonical_config_receipt",
        "independent_replay",
        "strict_json",
        "stable_snapshot_read",
        "retained_same_fd",
        "exclusive_no_overwrite",
        "resource_receipt",
        "terminal_receipt",
    }
    if set(capability_names) != expected_capabilities or len(capability_names) != len(expected_capabilities):
        raise GovernanceError("capability_index must cover each required capability exactly once")

    entrypoints = manifest.get("pytest_entrypoints")
    if not isinstance(entrypoints, list):
        raise GovernanceError("pytest_entrypoints must be a list")
    entrypoint_ids: set[str] = set()
    for entry in entrypoints:
        if not isinstance(entry, dict):
            raise GovernanceError("pytest entrypoint must be an object")
        entrypoint_id = entry.get("id")
        digest = entry.get("expected_sha256")
        baseline_digest = entry.get("baseline_sha256")
        if (
            not isinstance(entrypoint_id, str)
            or not entrypoint_id
            or entrypoint_id in entrypoint_ids
            or not isinstance(entry.get("baseline_count"), int)
            or entry["baseline_count"] < 0
            or not isinstance(entry.get("expected_count"), int)
            or entry["expected_count"] < 0
            or not isinstance(baseline_digest, str)
            or len(baseline_digest) != 64
            or any(character not in "0123456789abcdef" for character in baseline_digest)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise GovernanceError(f"invalid pytest entrypoint record: {entrypoint_id!r}")
        entrypoint_ids.add(entrypoint_id)
    pending_recipes = manifest.get("pytest_pending_recipes")
    if not isinstance(pending_recipes, list):
        raise GovernanceError("pytest_pending_recipes must be a list")
    for recipe in pending_recipes:
        if (
            not isinstance(recipe, dict)
            or recipe.get("status") != "pending_missing_target"
            or recipe.get("behavior") != "do_not_start_pytest"
            or not isinstance(recipe.get("target"), str)
        ):
            raise GovernanceError("invalid pending pytest recipe")
        if (ROOT / recipe["target"]).exists() or (ROOT / recipe["target"]).is_symlink():
            raise GovernanceError(
                f"pending pytest target now exists and needs a measured receipt: {recipe['target']}"
            )


def _validate_baseline(manifest: Mapping[str, Any]) -> dict[str, Any]:
    expected = manifest["measurement"]["baseline"]
    measured = inventory(commit=expected["commit"], include_assets=False)
    comparable = {
        key: measured[key]
        for key in (
            "git_visible_count",
            "code_asset_count",
            "raw_bytes",
            "lf_count",
            "class_counts",
        )
    }
    expected_comparable = {
        key: expected[key]
        for key in (
            "git_visible_count",
            "code_asset_count",
            "raw_bytes",
            "lf_count",
            "class_counts",
        )
    }
    if comparable != expected_comparable:
        raise GovernanceError(
            "baseline measurement drifted: "
            f"expected={expected_comparable!r} actual={comparable!r}"
        )
    return measured


def _validate_current(manifest: Mapping[str, Any]) -> dict[str, Any]:
    measured = inventory(include_assets=True)
    expected_counts = dict(manifest["measurement"]["expected_current_class_counts"])
    visible = set(git_visible_paths())
    for conditional in manifest["measurement"]["conditional_current_assets"]:
        if conditional["path"] in visible:
            expected_counts[conditional["primary_class"]] += 1
    if measured["class_counts"] != expected_counts:
        raise GovernanceError(
            "current class counts drifted: "
            f"expected={expected_counts!r} actual={measured['class_counts']!r}"
        )

    assets_by_path = {asset["path"]: asset for asset in measured["assets"]}
    pose = assets_by_path.get("src/models/pose_bool_exact_master.py")
    if pose is None or (
        pose["primary_class"],
        pose["lifecycle"],
        pose["certified_admission"],
    ) != (
        "active_implementation",
        "active_env_gated",
        "blocked_pose_bool_master_not_certified",
    ):
        raise GovernanceError("PoseBoolExactMasterDelegate backend classification drifted")

    retirement_paths = {
        asset["path"]
        for asset in measured["assets"]
        if asset["primary_class"] == "retirement_candidate"
    }
    expected_retirement_paths = (
        {f"scripts/build_phase1_1_gpt_pro_review_v{version}.py" for version in range(2, 9)}
        | {f"scripts/build_phase1_2_entry_review_v{version}.py" for version in range(9, 12)}
        | {f"scripts/build_phase1_2_spike_review_v{version}.py" for version in range(14, 23)}
    )
    if retirement_paths != expected_retirement_paths:
        raise GovernanceError(
            "retirement candidate set drifted: "
            f"missing={sorted(expected_retirement_paths - retirement_paths)!r} "
            f"extra={sorted(retirement_paths - expected_retirement_paths)!r}"
        )

    all_paths = git_visible_paths()
    for path in all_paths:
        role = _asset_role_for(path, manifest)
        asset = assets_by_path.get(path)
        if (
            role["asset_role"] in AUTHORITY_ASSET_ROLES
            and asset is not None
            and asset["primary_class"] == "historical_evidence"
        ):
            raise GovernanceError(f"current authority/control asset was downgraded to evidence: {path}")
    return measured


def _validate_pytest_lanes(manifest: Mapping[str, Any]) -> None:
    lane_rules = manifest["logical_isolation"]["pytest"]["lane_rules"]
    test_files = sorted(
        path
        for path in git_visible_paths()
        if path.startswith("src/tests/") and path.endswith(".py")
    )
    for path in test_files:
        matches = [rule for rule in lane_rules if _matches_glob(path, rule["glob"])]
        if not matches:
            raise GovernanceError(f"pytest lane rules do not cover {path}")
        if matches[0]["lane"] not in PYTEST_LANES:
            raise GovernanceError(f"pytest lane rule for {path} is invalid")


def _validate_capability_index(manifest: Mapping[str, Any]) -> None:
    visible = set(git_visible_paths())
    for capability in manifest["capability_index"]:
        implementations = capability["implementations"]
        identities: set[str] = set()
        for implementation in implementations:
            path = implementation["path"]
            symbol = implementation["symbol"]
            if path not in visible:
                raise GovernanceError(
                    f"capability index path is not Git-visible: {path}"
                )
            try:
                tree = ast.parse((ROOT / path).read_bytes(), filename=path)
            except (OSError, SyntaxError) as exc:
                raise GovernanceError(
                    f"cannot AST-parse capability implementation {path}: {exc}"
                ) from exc
            top_level_symbols = {
                node.name
                for node in tree.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if symbol not in top_level_symbols:
                raise GovernanceError(
                    f"capability index symbol is stale: {path}::{symbol}"
                )
            identities.add(f"{path}::{symbol}")
        shared_authority = capability["shared_authority"]
        if shared_authority is not None and shared_authority not in identities:
            raise GovernanceError(
                f"capability shared authority is not an indexed implementation: {shared_authority}"
            )
        preferred_active = [
            f"{implementation['path']}::{implementation['symbol']}"
            for implementation in implementations
            if implementation["role"] == "preferred_active"
        ]
        if shared_authority is None and preferred_active:
            raise GovernanceError(
                "capability without shared authority cannot declare preferred_active: "
                f"{capability['capability']}"
            )
        if shared_authority is not None and preferred_active != [shared_authority]:
            raise GovernanceError(
                "capability shared authority must be its unique preferred_active implementation: "
                f"{capability['capability']}"
            )


def _validate_enabled_projections(manifest: Mapping[str, Any]) -> None:
    isolation = manifest["logical_isolation"]
    if isolation["search"]["enabled"]:
        rgignore = ROOT / ".rgignore"
        if not rgignore.is_file():
            raise GovernanceError("search projection is enabled but .rgignore is absent")
        actual = [
            line
            for raw_line in rgignore.read_text(encoding="utf-8").splitlines()
            if (line := raw_line.strip()) and not line.startswith("#")
        ]
        expected = isolation["search"]["excluded_rules"]
        if actual != expected:
            raise GovernanceError(".rgignore rules are not the ordered manifest projection")
    # G1 deliberately has no external lint or pytest projection dependency.
    # Their enabled behavior is enforced by the owning G2 runner/hook and tests.


def _source_discovery_receipt(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if manifest is None:
        manifest = load_manifest()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    path_tuples: list[tuple[str, ...]] = []
    digests: list[str] = []
    for module_name in SOURCE_DISCOVERY_MODULES:
        module = importlib.import_module(module_name)
        discover = getattr(module, "_discover_certified_exact_source_hash_files", None)
        digest_function = getattr(module, "compute_certified_exact_source_digest", None)
        if not callable(discover) or not callable(digest_function):
            raise GovernanceError(f"{module_name} does not expose exact source discovery")
        paths = tuple(discover())
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise GovernanceError(f"{module_name} source discovery is not sorted and unique")
        path_tuples.append(paths)
        digests.append(str(digest_function()))
    if path_tuples[0] != path_tuples[1]:
        raise GovernanceError("independent certified exact source path tuples disagree")
    if digests[0] != digests[1]:
        raise GovernanceError("independent certified exact source digests disagree")
    forbidden = [
        path
        for path in path_tuples[0]
        if path == "devtools/check_repository_code_assets.py" or path.startswith("devtools/")
    ]
    if forbidden:
        raise GovernanceError(f"developer governance tooling entered certified source: {forbidden!r}")
    tuple_sha256 = hashlib.sha256(
        b"".join(path.encode("utf-8") + b"\n" for path in path_tuples[0])
    ).hexdigest()
    receipt = {
        "path_count": len(path_tuples[0]),
        "path_tuple_sha256": tuple_sha256,
        "sha256": digests[0],
        "devtools_paths": forbidden,
    }
    baseline = manifest["measurement"]["certified_exact_source_baseline"]
    expected = {
        "path_count": baseline["path_count"],
        "path_tuple_sha256": baseline["path_tuple_sha256"],
        "sha256": baseline["source_digest"],
        "devtools_paths": [],
    }
    if receipt != expected:
        raise GovernanceError(
            f"certified exact source identity drifted: expected={expected!r} actual={receipt!r}"
        )
    return receipt


def _validate_no_production_devtools_import() -> None:
    candidates = sorted(ROOT.glob("*.py"))
    candidates.extend(
        path
        for path in (ROOT / "src").rglob("*.py")
        if not path.relative_to(ROOT).as_posix().startswith("src/tests/")
    )
    candidates.extend((ROOT / "scripts").rglob("*.py"))
    violations: list[str] = []
    for path in candidates:
        relative = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_bytes(), filename=relative)
        except (OSError, SyntaxError) as exc:
            raise GovernanceError(f"cannot AST-parse production source {relative}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "devtools" or alias.name.startswith("devtools.") for alias in node.names):
                    violations.append(f"{relative}:{node.lineno}:import")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "devtools" or (
                    isinstance(node.module, str) and node.module.startswith("devtools.")
                ):
                    violations.append(f"{relative}:{node.lineno}:from")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                normalized = node.value.replace("\\", "/")
                if normalized == "devtools" or normalized.startswith("devtools/"):
                    violations.append(f"{relative}:{getattr(node, 'lineno', 0)}:literal")
    if violations:
        raise GovernanceError(f"production source references developer governance tooling: {violations!r}")


def _validate_developer_import_boundary(manifest: Mapping[str, Any]) -> None:
    measured = inventory(include_assets=True)
    forbidden_prefixes = {
        "docs.research",
        "paths",
        "scripts.phase3b",
        "src.tests.phase3b",
        "third_party_snapshots",
    }
    for record in measured["assets"]:
        if (
            record["primary_class"] not in {"active_implementation", "common_infrastructure"}
            or "developer" not in record["workflow_membership"]
            or PurePosixPath(record["path"]).suffix not in {".py", ".pyi"}
        ):
            continue
        path = ROOT / record["path"]
        try:
            tree = ast.parse(path.read_bytes(), filename=record["path"])
        except (OSError, SyntaxError) as exc:
            raise GovernanceError(
                f"cannot AST-parse developer import surface {record['path']}: {exc}"
            ) from exc
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and isinstance(node.module, str):
                modules.append(node.module)
            for module in modules:
                if any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    raise GovernanceError(
                        "developer import surface reaches an isolated historical module: "
                        f"{record['path']}:{node.lineno}:{module}"
                    )


def check() -> dict[str, Any]:
    # The adjacent schema is the structural contract; semantic checks below add
    # repository-specific invariants that JSON Schema cannot express.
    schema = _load_json_object(SCHEMA_PATH)
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise GovernanceError("code asset schema must use JSON Schema 2020-12")
    manifest = load_manifest()
    _validate_against_schema(schema, manifest)
    _validate_manifest_shape(manifest)
    _validate_read_only_historical_evidence_roots(manifest)
    baseline = _validate_baseline(manifest)
    current = _validate_current(manifest)
    _validate_pytest_lanes(manifest)
    _validate_capability_index(manifest)
    _validate_enabled_projections(manifest)
    source_receipt = _source_discovery_receipt(manifest)
    _validate_no_production_devtools_import()
    _validate_developer_import_boundary(manifest)
    return {
        "status": "PASS",
        "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
        "baseline": {
            key: baseline[key]
            for key in (
                "revision",
                "git_visible_count",
                "code_asset_count",
                "raw_bytes",
                "lf_count",
                "class_counts",
            )
        },
        "current": {
            key: current[key]
            for key in (
                "revision",
                "git_visible_count",
                "code_asset_count",
                "raw_bytes",
                "lf_count",
                "class_counts",
            )
        },
        "logical_isolation": {
            name: manifest["logical_isolation"][name]["enabled"]
            for name in ("search", "lint", "pytest")
        },
        "certified_exact_source": source_receipt,
    }


def _projected_lint_paths(profile: str) -> dict[str, Any]:
    manifest = load_manifest()
    projection = manifest["logical_isolation"]["lint"]
    measured = inventory(include_assets=True)
    assets = [
        asset
        for asset in measured["assets"]
        if PurePosixPath(asset["path"]).suffix in {".py", ".pyi"}
    ]
    if profile == "full" or not projection["enabled"]:
        selected = [asset["path"] for asset in assets]
    else:
        selected = [
            asset["path"]
            for asset in assets
            if not any(
                _matches_glob(asset["path"], pattern)
                for pattern in projection["excluded_rules"]
            )
        ]
    return {
        "profile": profile,
        "projection_enabled": projection["enabled"],
        "count": len(selected),
        "paths": selected,
    }


def _emit(value: Any, output_format: str) -> None:
    if output_format == "nul":
        if not isinstance(value, dict) or not isinstance(value.get("paths"), list):
            raise GovernanceError("NUL output is available only for path projections")
        sys.stdout.buffer.write(
            b"".join(os.fsencode(path) + b"\0" for path in value["paths"])
        )
        return
    if output_format == "json":
        print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))
        return
    if isinstance(value, dict) and "assets" in value:
        summary = {key: item for key, item in value.items() if key != "assets"}
        print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
        for asset in value["assets"]:
            print(f"{asset['primary_class']}\t{asset['path']}")
        return
    if isinstance(value, dict) and "paths" in value:
        summary = {key: item for key, item in value.items() if key != "paths"}
        print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
        for path in value["paths"]:
            print(path)
        return
    if isinstance(value, list):
        for item in value:
            print(json.dumps(item, sort_keys=True, ensure_ascii=False))
        return
    print(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser(
        "inventory",
        help="recompute the code-asset inventory",
    )
    inventory_parser.add_argument("--commit", help="measure a committed tree instead of the worktree")
    inventory_parser.add_argument("--format", choices=("text", "json"), default="text")

    check_parser = subparsers.add_parser("check", help="run fail-closed governance validation")
    check_parser.add_argument("--format", choices=("text", "json"), default="text")

    lint_parser = subparsers.add_parser("lint", help="emit the requested lint path projection")
    lint_parser.add_argument("--profile", choices=("developer", "full"), required=True)
    lint_parser.add_argument("--format", choices=("text", "json", "nul"), default="text")

    pytest_parser = subparsers.add_parser(
        "pytest-entrypoints",
        help="emit the registered pytest entrypoint receipts",
    )
    pytest_parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(commit=args.commit, include_assets=True)
        elif args.command == "check":
            result = check()
        elif args.command == "lint":
            result = _projected_lint_paths(args.profile)
        elif args.command == "pytest-entrypoints":
            result = load_manifest()["pytest_entrypoints"]
        else:
            parser.error(f"unsupported command: {args.command}")
            return 2
        _emit(result, args.format)
    except GovernanceError as exc:
        print(f"repository code asset check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
