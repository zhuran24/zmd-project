#!/usr/bin/env python3
"""Publish-safety secret scanner for the tracked repository tree.

The scanner is intentionally small and dependency-free.  It checks the current
working tree, not Git history.  History cleanup and credential rotation are
separate owner actions; this gate prevents new/current-tree leaks from being
committed again.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_TEXT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]


PATTERNS = [
    SecretPattern("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    SecretPattern("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    SecretPattern("openai_project_key", re.compile(r"\bsk-(?:proj|admin|sess|svcacct|live|test|user|key)-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("openai_classic_key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    SecretPattern("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
]

SKIP_PATH_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "__pycache__/",
)

SKIP_PATH_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".7z",
    ".tar",
    ".tar.gz",
    ".tar.xz",
    ".whl",
    ".pyc",
    ".pyd",
    ".so",
    ".dll",
)


def _git_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [str(p.relative_to(PROJECT_ROOT)) for p in PROJECT_ROOT.rglob("*") if p.is_file()]
    raw = result.stdout.decode("utf-8", errors="surrogateescape")
    return [item for item in raw.split("\0") if item]


def _safe_paths(paths: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for rel in sorted(set(paths)):
        norm = rel.replace("\\", "/")
        if norm.startswith(SKIP_PATH_PREFIXES) or norm.endswith(SKIP_PATH_SUFFIXES):
            continue
        if "/.git/" in norm or norm == ".git":
            continue
        safe.append(norm)
    return safe


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > MAX_TEXT_BYTES:
        return None
    if b"\x00" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{value[:4]}…{value[-4:]} sha256:{digest}"


def scan(paths: Iterable[str]) -> list[str]:
    findings: list[str] = []
    for rel in _safe_paths(paths):
        path = PROJECT_ROOT / rel
        text = _read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in PATTERNS:
                for match in pattern.regex.finditer(line):
                    findings.append(
                        f"{rel}:{lineno}: {pattern.name}: {_fingerprint(match.group(0))}"
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan current repository files for publish-blocking secrets.")
    parser.add_argument("paths", nargs="*", help="Optional repo-relative paths to scan. Defaults to git tracked/untracked files.")
    args = parser.parse_args()

    paths = args.paths or _git_files()
    findings = scan(paths)
    if findings:
        print("repo secret scan failed:")
        for finding in findings[:50]:
            print(f"  {finding}")
        if len(findings) > 50:
            print(f"  ... {len(findings) - 50} more")
        return 1

    print(f"repo secret scan passed: {len(_safe_paths(paths))} candidate text paths checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
