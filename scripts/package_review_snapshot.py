#!/usr/bin/env python3
"""Build a review archive from the committed HEAD tree and self-test it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_DOC_SENTINEL = Path("docs") / "项目说明" / "soundness_gap_roadmap.md"
SCRIPT_REL_PATH = "scripts/package_review_snapshot.py"
PACKAGE_EXCLUDED_PREFIXES = (
    ".artifacts/",
    "P1_2_TECHNICAL_CLOSE_PACKET/",
    "补丁包/",
)
PACKAGE_EXCLUDED_EXACT_NAMES = frozenset(
    {
        "agents.md",
        "claude.md",
    }
)
PACKAGE_EXCLUDED_PATH_PREFIXES = (
    ".artifacts/",
    ".claude/",
    ".codex/",
    "P1_2_TECHNICAL_CLOSE_PACKET/",
    "_cc_live_memory/",
    "cc_context/",
    "cc_memory/",
    "补丁包/",
)
PACKAGE_EXCLUDED_PATH_SEGMENTS = frozenset(
    {
        "external_review",
        "external_reviews",
        "review_packet",
        "review_packets",
        "review_package",
        "review_packages",
    }
)
DIRTY_GUARD_PREFIXES = (
    "data/proof_obligations/",
    "main.py",
    "scripts/",
    "src/",
)
PROMPT_BASENAME_RE = re.compile(r"(^|[_-])prompt([_.-]|$)|^prompt\.(json|md|txt)$")
PROMPT_CONTENT_MARKERS = (
    "<INSTRUCTIONS>",
    "You are ChatGPT",
    "You are Codex",
    "review request",
    "review prompt",
    "Package SHA256",
    "Sources tab",
    "添加源",
    "Pro 扩展",
    "boxed project chat composer",
    "你是子代理",
)
# Prompt/instruction content-sniffing applies only to PROSE/DATA document formats. Source code
# (.py/.ps1) is the artifact being reviewed and legitimately contains words like "review"/"prompt"
# and even marker strings as test fixtures (e.g. src/tests/test_package_review_snapshot.py exercises
# the prompt markers themselves) — content-sniffing source would wrongly drop the reviewed code from
# the snapshot. Actual prompt/instruction documents are caught by basename/exact-name/path rules and
# the .artifacts/ prefix; named prompt files use .md/.txt/.json. So .py/.ps1 are intentionally NOT
# content-sniff candidates.
TEXT_SNIFF_SUFFIXES = frozenset(
    {
        ".adoc",
        ".cfg",
        ".csv",
        ".ini",
        ".json",
        ".jsonl",
        ".md",
        ".rst",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)
REJECTED_ARCHIVE_SUFFIXES = (
    ".7z",
    ".zip",
    ".rar",
    ".tar",
    ".tgz",
    ".gz",
)
DEFAULT_TARGETED_TESTS = (
    "src/tests/test_p1_2_proof_obligations.py",
    "src/tests/test_delivery_manifest.py",
    "src/tests/test_p1_2_sink_replay_authority.py",
    "src/tests/test_p1_2_supervisor_pr1.py",
    "src/tests/test_exact_contract.py",
    "src/tests/test_exact_campaign_inspector.py",
    "src/tests/test_render_output.py",
    "src/tests/test_industrial_planner_export.py",
    "src/tests/test_v83_certified_surface_soundness.py",
    "src/tests/phase3b/b5a/test_b5_anchor_sprint.py",
)
EMBEDDED_MANIFEST_NAME = "REVIEW_SNAPSHOT_MANIFEST.json"
EMBEDDED_INVENTORY_NAME = "REVIEW_SNAPSHOT_INVENTORY.json"
KEY_FILE_PATHS = (
    SCRIPT_REL_PATH,
    "scripts/check_p1_2_proof_obligations.py",
    "scripts/check_strong_status_write_allowlist.py",
    "data/proof_obligations/p1_2_proof_obligations.json",
    "data/proof_obligations/strong_status_write_allowlist.json",
    "src/search/certified_surface.py",
    "src/io/delivery_manifest.py",
    *DEFAULT_TARGETED_TESTS,
)


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    capture: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        env=dict(env) if env is not None else None,
    )


def _require_success(result: subprocess.CompletedProcess[str], command: Sequence[str]) -> str:
    if result.returncode != 0:
        output = result.stdout or ""
        raise RuntimeError(
            f"command failed with exit code {result.returncode}: {' '.join(command)}\n{output}"
        )
    return result.stdout or ""


def _git_bytes(args: Sequence[str], *, cwd: Path) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def _git_success(args: Sequence[str], *, cwd: Path) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _tree_entries(repo_root: Path, treeish: str) -> Iterable[tuple[str, str, str]]:
    raw = _git_bytes(
        ["ls-tree", "-r", "-z", "--full-tree", treeish],
        cwd=repo_root,
    )
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, obj_type, sha = meta.decode("ascii").split(" ")
        if obj_type != "blob":
            continue
        yield mode, sha, raw_path.decode("utf-8")


def _normalize_rel_path(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/").strip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def _path_segments(rel_path: str) -> tuple[str, ...]:
    return tuple(segment for segment in _normalize_rel_path(rel_path).split("/") if segment)


def _is_prompt_like_path(rel_path: str) -> bool:
    normalized = _normalize_rel_path(rel_path)
    basename = Path(normalized).name.lower()
    stem = Path(basename).stem.lower()
    return bool(
        PROMPT_BASENAME_RE.search(basename)
        or "review_request" in stem
        or "review-prompt" in stem
        or "review_prompt" in stem
        or "external_review" in stem
        or "chatgpt_prompt" in stem
        or "gpt_prompt" in stem
    )


def _is_archive_path(rel_path: str) -> bool:
    return _normalize_rel_path(rel_path).lower().endswith(REJECTED_ARCHIVE_SUFFIXES)


def _is_text_sniff_candidate(rel_path: str) -> bool:
    normalized = _normalize_rel_path(rel_path).lower()
    suffix = Path(normalized).suffix
    return suffix in TEXT_SNIFF_SUFFIXES and any(
        marker in normalized for marker in ("prompt", "review", "packet", "chatgpt")
    )


def _has_prompt_content_marker(rel_path: str, blob: bytes | None) -> bool:
    if blob is None or not _is_text_sniff_candidate(rel_path) or len(blob) > 256 * 1024:
        return False
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return False
    lowered = text.lower()
    for marker in PROMPT_CONTENT_MARKERS:
        if marker in text or marker.lower() in lowered:
            return True
    return False


def _package_exclusion_reason(rel_path: str, blob: bytes | None = None) -> str | None:
    normalized = _normalize_rel_path(rel_path)
    segments = _path_segments(normalized)
    lowered_segments = tuple(segment.lower() for segment in segments)
    basename = segments[-1] if segments else ""
    if basename.lower() in PACKAGE_EXCLUDED_EXACT_NAMES:
        return "agent_instruction_file"
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in PACKAGE_EXCLUDED_PATH_PREFIXES):
        return "excluded_package_prefix"
    if any(segment in PACKAGE_EXCLUDED_PATH_SEGMENTS for segment in lowered_segments):
        return "old_review_packet_path"
    if _is_prompt_like_path(normalized):
        return "prompt_like_path"
    if _is_archive_path(normalized):
        return "archive_path"
    if _has_prompt_content_marker(normalized, blob):
        return "prompt_like_content"
    return None


def _is_excluded_package_path(rel_path: str) -> bool:
    return _package_exclusion_reason(rel_path) is not None


def _package_inventory_violations(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for rel_path in paths:
        normalized = _normalize_rel_path(rel_path)
        reason = _package_exclusion_reason(normalized)
        if reason is not None:
            violations.append(f"{reason}:{normalized}")
    return violations


def _git_status_entries(repo_root: Path) -> list[dict[str, str]]:
    raw = _git_bytes(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repo_root,
    )
    parts = raw.decode("utf-8", errors="replace").split("\0")
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(parts):
        entry = parts[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4 or entry[2] != " ":
            raise RuntimeError(f"unexpected git status porcelain entry: {entry!r}")
        status = entry[:2]
        payload = {
            "status": status,
            "path": _normalize_rel_path(entry[3:]),
        }
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            if index >= len(parts) or not parts[index]:
                raise RuntimeError(
                    f"git status porcelain {status.strip() or status!r} entry is missing original path"
                )
            payload["orig_path"] = _normalize_rel_path(parts[index])
            index += 1
        entries.append(payload)
    return sorted(entries, key=lambda item: (item["path"], item.get("orig_path", "")))


def _dirty_status_paths(entry: Mapping[str, str]) -> list[str]:
    paths = [entry["path"]]
    original = entry.get("orig_path")
    if original:
        paths.append(original)
    return paths


def _guarded_dirty_paths(repo_root: Path) -> list[str]:
    guarded: list[str] = []
    for entry in _git_status_entries(repo_root):
        for rel_path in _dirty_status_paths(entry):
            if any(
                rel_path == prefix.rstrip("/") or rel_path.startswith(prefix)
                for prefix in DIRTY_GUARD_PREFIXES
            ):
                guarded.append(rel_path)
    return sorted(set(guarded))


def _require_tree_ready(repo_root: Path, treeish: str, *, allow_dirty_guarded: bool = False) -> None:
    if not _git_success(["cat-file", "-e", f"{treeish}:{SCRIPT_REL_PATH}"], cwd=repo_root):
        raise RuntimeError(
            f"{SCRIPT_REL_PATH} must be committed in {treeish} before building a review package"
        )
    dirty = _guarded_dirty_paths(repo_root)
    if dirty and not allow_dirty_guarded:
        formatted = ", ".join(dirty[:12])
        if len(dirty) > 12:
            formatted += f", ... ({len(dirty)} total)"
        raise RuntimeError(
            "review package must be built from committed PR1.1c source paths; "
            f"dirty guarded path(s): {formatted}"
        )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _selftest_python_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def _command_summary(output: str) -> str:
    stripped = output.strip()
    return stripped.splitlines()[-1] if stripped else ""


def _run_review_selftests(stage_root: Path, *, skip_tests: bool) -> list[dict[str, object]]:
    env = _selftest_python_env()
    verification: list[dict[str, object]] = []
    proof_cmd = [sys.executable, "scripts/check_p1_2_proof_obligations.py"]
    proof_output = _require_success(_run(proof_cmd, cwd=stage_root, env=env), proof_cmd)
    verification.append(
        {
            "kind": "proof_checker",
            "command": proof_cmd,
            "exit_code": 0,
            "summary": _command_summary(proof_output),
            "env": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]},
        }
    )
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        *DEFAULT_TARGETED_TESTS,
        "-q",
    ]
    if skip_tests:
        verification.append(
            {
                "kind": "targeted_pytest",
                "command": pytest_cmd,
                "skipped": True,
                "skip_reason": "--skip-tests",
                "env": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]},
            }
        )
        return verification
    pytest_output = _require_success(_run(pytest_cmd, cwd=stage_root, env=env), pytest_cmd)
    verification.append(
        {
            "kind": "targeted_pytest",
            "command": pytest_cmd,
            "exit_code": 0,
            "summary": _command_summary(pytest_output),
            "env": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]},
        }
    )
    return verification


def _has_command(receipt: Mapping[str, object]) -> bool:
    command = receipt.get("command")
    return isinstance(command, list) and bool(command) and all(isinstance(part, str) for part in command)


def _is_success_receipt(receipt: Mapping[str, object], *, kind: str) -> bool:
    return (
        receipt.get("kind") == kind
        and _has_command(receipt)
        and receipt.get("exit_code") == 0
        and isinstance(receipt.get("summary"), str)
    )


def _is_skip_marker(receipt: Mapping[str, object]) -> bool:
    return (
        receipt.get("kind") == "targeted_pytest"
        and _has_command(receipt)
        and receipt.get("skipped") is True
        and receipt.get("skip_reason") == "--skip-tests"
        and _receipt_runs_default_targeted_tests(receipt)
    )


def _receipt_runs_default_targeted_tests(receipt: Mapping[str, object]) -> bool:
    """A receipt is only acceptable proof if its command is EXACTLY the canonical pytest invocation
    over the FULL DEFAULT_TARGETED_TESTS set under hermetic plugin-autoload isolation. The command
    tail (everything after the interpreter path) must equal ``-m pytest <DEFAULT_TARGETED_TESTS> -q``.
    Membership-only matching is not enough: a forged command like ``python -c '...' pytest <paths>``
    or ``... pytest <paths> --collect-only`` contains the right tokens without actually running the
    target set, so it must be rejected. This binds the embedded receipt to the real coverage."""
    command = receipt.get("command")
    if not (isinstance(command, list) and command and all(isinstance(part, str) for part in command)):
        return False
    expected_tail = ["-m", "pytest", *DEFAULT_TARGETED_TESTS, "-q"]
    if list(command[1:]) != expected_tail:
        return False
    env = receipt.get("env")
    return isinstance(env, Mapping) and env.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"


def _validate_embedded_verification(
    verification: Sequence[dict[str, object]],
    *,
    targeted_tests_skipped: bool,
) -> None:
    if not verification:
        raise RuntimeError("embedded review snapshot manifest missing verification receipt")
    if not any(_is_success_receipt(receipt, kind="proof_checker") for receipt in verification):
        raise RuntimeError("embedded review snapshot manifest missing proof checker receipt")

    pytest_receipts = [
        receipt
        for receipt in verification
        if receipt.get("kind") == "targeted_pytest"
    ]
    if targeted_tests_skipped:
        if not any(_is_skip_marker(receipt) for receipt in pytest_receipts):
            raise RuntimeError(
                "embedded review snapshot manifest missing --skip-tests marker for the full "
                "DEFAULT_TARGETED_TESTS set"
            )
        return

    if any(receipt.get("skipped") is True for receipt in pytest_receipts):
        raise RuntimeError("embedded review snapshot manifest marks pytest skipped without --skip-tests")
    if not any(
        _is_success_receipt(receipt, kind="targeted_pytest")
        and _receipt_runs_default_targeted_tests(receipt)
        for receipt in pytest_receipts
    ):
        raise RuntimeError(
            "embedded review snapshot manifest missing a successful targeted pytest receipt that runs "
            "the full DEFAULT_TARGETED_TESTS set under plugin-autoload isolation"
        )


def _inventory_digest(inventory: Sequence[dict[str, object]]) -> str:
    return _sha256_bytes(_canonical_json_bytes(list(inventory)))


def _git_commit_metadata(repo_root: Path, treeish: str) -> dict[str, object]:
    head_commit = _require_success(
        _run(["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=repo_root),
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
    ).strip()
    head_tree = _require_success(
        _run(["git", "rev-parse", "--verify", "HEAD^{tree}"], cwd=repo_root),
        ["git", "rev-parse", "--verify", "HEAD^{tree}"],
    ).strip()
    packaged_commit = _require_success(
        _run(["git", "rev-parse", "--verify", f"{treeish}^{{commit}}"], cwd=repo_root),
        ["git", "rev-parse", "--verify", f"{treeish}^{{commit}}"],
    ).strip()
    packaged_tree = _require_success(
        _run(["git", "rev-parse", "--verify", f"{treeish}^{{tree}}"], cwd=repo_root),
        ["git", "rev-parse", "--verify", f"{treeish}^{{tree}}"],
    ).strip()
    status_entries = _git_status_entries(repo_root)
    dirty_paths = sorted({path for entry in status_entries for path in _dirty_status_paths(entry)})
    dirty_guarded_paths = [
        path
        for path in dirty_paths
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in DIRTY_GUARD_PREFIXES)
    ]
    return {
        "head_commit": head_commit,
        "head_tree": head_tree,
        "packaged_commit": packaged_commit,
        "packaged_tree": packaged_tree,
        "packaged_equals_head": packaged_commit == head_commit and packaged_tree == head_tree,
        "working_tree_dirty": bool(status_entries),
        "dirty_status": status_entries,
        "dirty_paths": dirty_paths,
        "dirty_guarded_paths": sorted(dirty_guarded_paths),
        "dirty_changes_included": False,
    }


def _materialize_tree(
    repo_root: Path,
    destination: Path,
    treeish: str,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    inventory: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    for mode, sha, rel_path in _tree_entries(repo_root, treeish):
        normalized = _normalize_rel_path(rel_path)
        if mode == "160000":
            continue
        if _package_exclusion_reason(normalized) is not None:
            excluded.append({"path": normalized, "reason": _package_exclusion_reason(normalized) or "excluded"})
            continue
        blob = _git_bytes(["cat-file", "-p", sha], cwd=repo_root)
        reason = _package_exclusion_reason(normalized, blob)
        if reason is not None:
            excluded.append({"path": normalized, "reason": reason})
            continue
        target = destination / Path(*normalized.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            target.write_text(blob.decode("utf-8"), encoding="utf-8", newline="\n")
        else:
            target.write_bytes(blob)
        inventory.append(
            {
                "path": normalized,
                "mode": mode,
                "git_blob_oid": sha,
                "size": len(blob),
                "content_sha256": _sha256_bytes(blob),
            }
        )
    inventory = sorted(inventory, key=lambda item: str(item["path"]))
    violations = _package_inventory_violations(str(item["path"]) for item in inventory)
    if violations:
        raise RuntimeError("package inventory rejected: " + "; ".join(violations[:20]))
    return inventory, sorted(excluded, key=lambda item: item["path"])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ascii_temp_dir(prefix: str) -> tempfile.TemporaryDirectory[str]:
    temp_root = Path(os.environ.get("TEMP") or tempfile.gettempdir()).resolve()
    if not str(temp_root).isascii():
        temp_root = Path.cwd().resolve() / ".package_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=str(temp_root))


def _find_7z() -> str:
    for name in ("7z", "7zz", "7za"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("7z/7zz/7za was not found on PATH")


def _write_sidecar_manifest(
    *,
    manifest_path: Path,
    payload: dict[str, object],
) -> None:
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_json_file(path: Path, payload: Any) -> None:
    path.write_bytes(_canonical_json_bytes(payload))


def _key_file_inventory(inventory: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    by_path = {str(item["path"]): item for item in inventory}
    return [by_path[path] for path in KEY_FILE_PATHS if path in by_path]


def _build_embedded_manifest(
    *,
    repo_root: Path,
    treeish: str,
    provenance: dict[str, object],
    inventory: Sequence[dict[str, object]],
    excluded: Sequence[dict[str, str]],
    verification: Sequence[dict[str, object]],
    targeted_tests_skipped: bool,
) -> dict[str, object]:
    _validate_embedded_verification(
        list(verification),
        targeted_tests_skipped=bool(targeted_tests_skipped),
    )
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "committed_git_tree",
        "treeish": treeish,
        "repo_root": str(repo_root),
        "provenance": provenance,
        "file_count": len(inventory),
        "inventory_file": EMBEDDED_INVENTORY_NAME,
        "inventory_sha256": _inventory_digest(inventory),
        "key_files": _key_file_inventory(inventory),
        "excluded_paths": list(excluded),
        "excluded_path_rules": {
            "prefixes": list(PACKAGE_EXCLUDED_PATH_PREFIXES),
            "exact_names": sorted(PACKAGE_EXCLUDED_EXACT_NAMES),
            "path_segments": sorted(PACKAGE_EXCLUDED_PATH_SEGMENTS),
            "prompt_like_names": True,
            "prompt_like_content_markers": True,
            "archive_suffixes": list(REJECTED_ARCHIVE_SUFFIXES),
        },
        "default_targeted_tests": list(DEFAULT_TARGETED_TESTS),
        "targeted_tests_skipped": bool(targeted_tests_skipped),
        "verification": list(verification),
        "dirty_worktree_policy": (
            "Archive bytes are from the committed packaged tree only; dirty working-tree "
            "changes are recorded in provenance and are not included."
        ),
    }


def _write_embedded_snapshot_metadata(
    *,
    stage_root: Path,
    manifest: dict[str, object],
    inventory: Sequence[dict[str, object]],
) -> None:
    _write_json_file(stage_root / EMBEDDED_INVENTORY_NAME, list(inventory))
    _write_json_file(stage_root / EMBEDDED_MANIFEST_NAME, manifest)


def _verify_inventory_entries(root: Path, inventory: Sequence[dict[str, object]]) -> None:
    for raw_entry in inventory:
        rel_path = str(raw_entry["path"])
        path = root / Path(*rel_path.split("/"))
        if not path.is_file():
            raise RuntimeError(f"inventory file missing after extraction: {rel_path}")
        blob = path.read_bytes()
        expected_size = int(raw_entry["size"])
        expected_sha = str(raw_entry["content_sha256"])
        if len(blob) != expected_size:
            raise RuntimeError(f"inventory size mismatch after extraction: {rel_path}")
        if _sha256_bytes(blob) != expected_sha:
            raise RuntimeError(f"inventory sha256 mismatch after extraction: {rel_path}")


def _load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_package(args: argparse.Namespace) -> int:
    repo_root = Path.cwd().resolve()
    treeish = str(args.treeish)
    _require_tree_ready(repo_root, treeish, allow_dirty_guarded=bool(args.allow_dirty_guarded))
    # Resolve the (possibly mutable) treeish to an immutable commit SHA ONCE, then use that resolved
    # commit for BOTH provenance metadata and tree materialization. This closes the TOCTOU where a
    # concurrent ref move between resolving provenance and archiving bytes would split the archived
    # bytes from the recorded packaged_commit.
    resolved_commit = _require_success(
        _run(["git", "rev-parse", "--verify", f"{treeish}^{{commit}}"], cwd=repo_root),
        ["git", "rev-parse", "--verify", f"{treeish}^{{commit}}"],
    ).strip()
    provenance = _git_commit_metadata(repo_root, resolved_commit)
    if not provenance["packaged_equals_head"] and not args.allow_non_head:
        raise RuntimeError(
            "review package treeish must resolve to HEAD by default; pass --allow-non-head "
            "only for explicitly labeled historical packages"
        )
    short_commit = _require_success(
        _run(["git", "rev-parse", "--short=12", str(provenance["packaged_commit"])], cwd=repo_root),
        ["git", "rev-parse", "--short=12", str(provenance["packaged_commit"])],
    ).strip()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    package_name = args.name or f"zmd_pr1_1c_{short_commit}_{timestamp}.7z"
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / package_name
    if package_path.exists() and not args.force:
        raise RuntimeError(f"package already exists: {package_path}")
    package_path.unlink(missing_ok=True)

    seven_zip = _find_7z()
    inventory: list[str]
    with _ascii_temp_dir("zmd_pkg_stage_") as stage_raw:
        stage_root = Path(stage_raw) / "root"
        stage_root.mkdir(parents=True)
        source_inventory, excluded_paths = _materialize_tree(repo_root, stage_root, resolved_commit)
        embedded_verification = _run_review_selftests(stage_root, skip_tests=bool(args.skip_tests))
        embedded_manifest = _build_embedded_manifest(
            repo_root=repo_root,
            treeish=resolved_commit,
            provenance=provenance,
            inventory=source_inventory,
            excluded=excluded_paths,
            verification=embedded_verification,
            targeted_tests_skipped=bool(args.skip_tests),
        )
        _write_embedded_snapshot_metadata(
            stage_root=stage_root,
            manifest=embedded_manifest,
            inventory=source_inventory,
        )
        inventory = sorted(
            [str(item["path"]) for item in source_inventory]
            + [EMBEDDED_INVENTORY_NAME, EMBEDDED_MANIFEST_NAME]
        )
        sentinel = stage_root / PROJECT_DOC_SENTINEL
        if not sentinel.exists():
            raise RuntimeError(f"{treeish} materialization is missing Unicode sentinel path: {sentinel}")
        # The staging selftest (proof checker + pytest) imports modules and so generates transient
        # __pycache__/*.pyc and .pytest_cache artifacts in the stage tree. Those are NOT part of the
        # materialized git inventory, so exclude them from the archive — otherwise extract-time
        # inventory verification rejects the package for unexpected generated files.
        create_cmd = [
            seven_zip,
            "a",
            "-t7z",
            "-mx=9",
            "-xr!__pycache__",
            "-xr!.pytest_cache",
            "-xr!.pytest_tmp",
            str(package_path),
            ".",
        ]
        _require_success(_run(create_cmd, cwd=stage_root), create_cmd)

    test_cmd = [seven_zip, "t", str(package_path)]
    _require_success(_run(test_cmd, cwd=repo_root), test_cmd)
    package_sha = _sha256_file(package_path)

    verification: list[dict[str, object]] = [
        {
            "kind": "archive_integrity",
            "command": test_cmd,
            "exit_code": 0,
        }
    ]
    with _ascii_temp_dir("zmd_pkg_extract_") as extract_raw:
        extract_root = Path(extract_raw) / "extract"
        extract_root.mkdir(parents=True)
        extract_cmd = [seven_zip, "x", "-y", f"-o{extract_root}", str(package_path)]
        _require_success(_run(extract_cmd, cwd=repo_root), extract_cmd)
        extracted_sentinel = extract_root / PROJECT_DOC_SENTINEL
        if not extracted_sentinel.exists():
            raise RuntimeError(
                f"extracted archive is missing Unicode sentinel path: {PROJECT_DOC_SENTINEL}"
            )
        extracted_inventory = sorted(
            path.relative_to(extract_root).as_posix()
            for path in extract_root.rglob("*")
            if path.is_file()
        )
        if extracted_inventory != inventory:
            extra = sorted(set(extracted_inventory) - set(inventory))
            missing = sorted(set(inventory) - set(extracted_inventory))
            raise RuntimeError(
                "extracted archive inventory does not match materialized tree; "
                f"unexpected={extra[:12]} missing={missing[:12]}"
            )
        inventory_violations = _package_inventory_violations(extracted_inventory)
        if inventory_violations:
            raise RuntimeError(
                "extracted archive inventory rejected: " + "; ".join(inventory_violations[:20])
            )
        embedded_inventory = _load_json_file(extract_root / EMBEDDED_INVENTORY_NAME)
        embedded_manifest = _load_json_file(extract_root / EMBEDDED_MANIFEST_NAME)
        if not isinstance(embedded_inventory, list):
            raise RuntimeError("embedded review snapshot inventory must be a list")
        if not isinstance(embedded_manifest, dict):
            raise RuntimeError("embedded review snapshot manifest must be an object")
        if embedded_manifest.get("inventory_sha256") != _inventory_digest(embedded_inventory):
            raise RuntimeError("embedded review snapshot inventory hash mismatch")
        _verify_inventory_entries(extract_root, embedded_inventory)
        embedded_verification = embedded_manifest.get("verification")
        if not isinstance(embedded_verification, list) or not embedded_verification:
            raise RuntimeError("embedded review snapshot manifest missing verification receipt")
        if bool(embedded_manifest.get("targeted_tests_skipped")) != bool(args.skip_tests):
            raise RuntimeError("embedded review snapshot skip-tests marker mismatch")
        _validate_embedded_verification(
            embedded_verification,
            targeted_tests_skipped=bool(args.skip_tests),
        )
        verification.extend(embedded_verification)

    manifest_path = package_path.with_suffix(package_path.suffix + ".manifest.json")
    inventory_path = package_path.with_suffix(package_path.suffix + ".inventory.txt")
    inventory_text = "\n".join(inventory) + "\n"
    inventory_path.write_text(inventory_text, encoding="utf-8", newline="\n")
    sidecar_payload = dict(embedded_manifest)
    sidecar_payload.update(
        {
            "archive": str(package_path),
            "archive_sha256": package_sha,
            "embedded_manifest_sha256": _sha256_bytes(_canonical_json_bytes(embedded_manifest)),
            "verification": verification,
            "sidecar_inventory": str(inventory_path),
            "sidecar_inventory_sha256": hashlib.sha256(inventory_text.encode("utf-8")).hexdigest(),
        }
    )
    _write_sidecar_manifest(
        manifest_path=manifest_path,
        payload=sidecar_payload,
    )
    print(f"archive={package_path}")
    print(f"sha256={package_sha}")
    print(f"manifest={manifest_path}")
    print(f"inventory={inventory_path}")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--treeish", default="HEAD", help="committed tree-ish to package")
    parser.add_argument(
        "--allow-non-head",
        action="store_true",
        help="permit packaging a historical commit; manifest records that it is not HEAD",
    )
    parser.add_argument(
        "--allow-dirty-guarded",
        action="store_true",
        help="permit dirty guarded source paths while still packaging committed-tree bytes only",
    )
    parser.add_argument("--output-dir", default="补丁包", help="directory for the .7z package")
    parser.add_argument("--name", help="archive filename; default includes PR tag, commit, and UTC timestamp")
    parser.add_argument("--force", action="store_true", help="replace an existing archive with the same name")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="only run archive integrity, Unicode sentinel, and proof checker self-tests",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return build_package(parse_args(list(argv) if argv is not None else sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"package_review_snapshot failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
