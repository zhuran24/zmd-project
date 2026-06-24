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
from typing import Iterable, Sequence


PROJECT_DOC_SENTINEL = Path("docs") / "项目说明" / "soundness_gap_roadmap.md"
SCRIPT_REL_PATH = "scripts/package_review_snapshot.py"
PACKAGE_EXCLUDED_PREFIXES = (
    ".artifacts/",
    "P1_2_TECHNICAL_CLOSE_PACKET/",
    "补丁包/",
)
DIRTY_GUARD_PREFIXES = (
    "data/proof_obligations/",
    "main.py",
    "scripts/",
    "src/",
)
PROMPT_BASENAME_RE = re.compile(r"(^|[_-])prompt([_.-]|$)|^prompt\.(json|md|txt)$")
REJECTED_ARCHIVE_SUFFIXES = (
    ".7z",
    ".zip",
    ".rar",
    ".tar",
    ".tgz",
    ".gz",
)
DEFAULT_TARGETED_TESTS = (
    "src/tests/test_p1_2_supervisor_pr1.py",
    "src/tests/test_render_output.py",
    "src/tests/test_product_view_models.py",
    "src/tests/test_v83_certified_surface_soundness.py",
)


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    capture: bool = True,
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


def _is_prompt_like_path(rel_path: str) -> bool:
    basename = Path(rel_path.replace("\\", "/")).name.lower()
    return bool(PROMPT_BASENAME_RE.search(basename))


def _is_archive_path(rel_path: str) -> bool:
    return rel_path.replace("\\", "/").lower().endswith(REJECTED_ARCHIVE_SUFFIXES)


def _is_excluded_package_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return (
        any(normalized.startswith(prefix) for prefix in PACKAGE_EXCLUDED_PREFIXES)
        or _is_prompt_like_path(normalized)
        or _is_archive_path(normalized)
    )


def _package_inventory_violations(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for rel_path in paths:
        normalized = rel_path.replace("\\", "/")
        lower_path = normalized.lower()
        if _is_excluded_package_path(normalized):
            violations.append(f"excluded_path_present:{normalized}")
        elif _is_prompt_like_path(normalized):
            violations.append(f"prompt_like_path_present:{normalized}")
        elif _is_archive_path(lower_path):
            violations.append(f"archive_path_present:{normalized}")
    return violations


def _guarded_dirty_paths(repo_root: Path) -> list[str]:
    raw = _git_bytes(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repo_root,
    )
    guarded: list[str] = []
    for entry in raw.decode("utf-8", errors="replace").split("\0"):
        if not entry:
            continue
        rel_path = entry[3:].replace("\\", "/")
        if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in DIRTY_GUARD_PREFIXES):
            guarded.append(rel_path)
    return sorted(set(guarded))


def _require_tree_ready(repo_root: Path, treeish: str) -> None:
    if not _git_success(["cat-file", "-e", f"{treeish}:{SCRIPT_REL_PATH}"], cwd=repo_root):
        raise RuntimeError(
            f"{SCRIPT_REL_PATH} must be committed in {treeish} before building a review package"
        )
    dirty = _guarded_dirty_paths(repo_root)
    if dirty:
        formatted = ", ".join(dirty[:12])
        if len(dirty) > 12:
            formatted += f", ... ({len(dirty)} total)"
        raise RuntimeError(
            "review package must be built from committed PR1.1c source paths; "
            f"dirty guarded path(s): {formatted}"
        )


def _materialize_tree(repo_root: Path, destination: Path, treeish: str) -> tuple[int, list[str]]:
    count = 0
    inventory: list[str] = []
    for mode, sha, rel_path in _tree_entries(repo_root, treeish):
        if mode == "160000":
            continue
        if _is_excluded_package_path(rel_path):
            continue
        target = destination / Path(*rel_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        blob = _git_bytes(["cat-file", "-p", sha], cwd=repo_root)
        if mode == "120000":
            target.write_text(blob.decode("utf-8"), encoding="utf-8", newline="\n")
        else:
            target.write_bytes(blob)
        count += 1
        inventory.append(rel_path)
    violations = _package_inventory_violations(inventory)
    if violations:
        raise RuntimeError("package inventory rejected: " + "; ".join(violations[:20]))
    return count, sorted(inventory)


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


def build_package(args: argparse.Namespace) -> int:
    repo_root = Path.cwd().resolve()
    treeish = str(args.treeish)
    _require_tree_ready(repo_root, treeish)
    short_commit = _require_success(
        _run(["git", "rev-parse", "--short=12", treeish], cwd=repo_root),
        ["git", "rev-parse", "--short=12", treeish],
    ).strip()
    commit = _require_success(
        _run(["git", "rev-parse", treeish], cwd=repo_root),
        ["git", "rev-parse", treeish],
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
        file_count, inventory = _materialize_tree(repo_root, stage_root, treeish)
        sentinel = stage_root / PROJECT_DOC_SENTINEL
        if not sentinel.exists():
            raise RuntimeError(f"{treeish} materialization is missing Unicode sentinel path: {sentinel}")
        create_cmd = [seven_zip, "a", "-t7z", "-mx=9", str(package_path), "."]
        _require_success(_run(create_cmd, cwd=stage_root), create_cmd)

    test_cmd = [seven_zip, "t", str(package_path)]
    _require_success(_run(test_cmd, cwd=repo_root), test_cmd)
    package_sha = _sha256_file(package_path)

    verification: list[dict[str, object]] = [
        {
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
            raise RuntimeError("extracted archive inventory does not match materialized tree")
        inventory_violations = _package_inventory_violations(extracted_inventory)
        if inventory_violations:
            raise RuntimeError(
                "extracted archive inventory rejected: " + "; ".join(inventory_violations[:20])
            )
        proof_cmd = [sys.executable, "scripts/check_p1_2_proof_obligations.py"]
        proof_output = _require_success(_run(proof_cmd, cwd=extract_root), proof_cmd)
        verification.append(
            {
                "command": proof_cmd,
                "exit_code": 0,
                "summary": proof_output.strip().splitlines()[-1] if proof_output.strip() else "",
            }
        )
        if not args.skip_tests:
            pytest_cmd = [
                sys.executable,
                "-m",
                "pytest",
                *DEFAULT_TARGETED_TESTS,
                "-q",
            ]
            pytest_output = _require_success(_run(pytest_cmd, cwd=extract_root), pytest_cmd)
            verification.append(
                {
                    "command": pytest_cmd,
                    "exit_code": 0,
                    "summary": pytest_output.strip().splitlines()[-1] if pytest_output.strip() else "",
                }
            )

    manifest_path = package_path.with_suffix(package_path.suffix + ".manifest.json")
    inventory_path = package_path.with_suffix(package_path.suffix + ".inventory.txt")
    inventory_text = "\n".join(inventory) + "\n"
    inventory_path.write_text(inventory_text, encoding="utf-8", newline="\n")
    _write_sidecar_manifest(
        manifest_path=manifest_path,
        payload={
            "archive": str(package_path),
            "archive_sha256": package_sha,
            "commit": commit,
            "short_commit": short_commit,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": f"git ls-tree {treeish} materialized to a temporary staging directory",
            "file_count": file_count,
            "excluded_prefixes": list(PACKAGE_EXCLUDED_PREFIXES),
            "excluded_path_rules": [
                "prompt-like basenames",
                "archive suffixes",
            ],
            "inventory": str(inventory_path),
            "inventory_sha256": hashlib.sha256(inventory_text.encode("utf-8")).hexdigest(),
            "unicode_sentinel": str(PROJECT_DOC_SENTINEL).replace("\\", "/"),
            "prompt_in_archive": False,
            "verification": verification,
        },
    )
    print(f"archive={package_path}")
    print(f"sha256={package_sha}")
    print(f"manifest={manifest_path}")
    print(f"inventory={inventory_path}")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--treeish", default="HEAD", help="committed tree-ish to package")
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
