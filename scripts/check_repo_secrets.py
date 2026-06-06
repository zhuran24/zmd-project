#!/usr/bin/env python3
"""Repository publish-safety secret scanner.

This is a high-signal preflight gate for credentials that must not live in the
current tree. It is intentionally conservative about binary/archive data and
focuses on text files that GitHub would render or index.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".pytest_tmp",
    "__pycache__",
    ".venv",
    "venv",
    "wheels",
    "wheelhouse",
    "node_modules",
}

SKIP_SUFFIXES = {
    ".7z",
    ".zip",
    ".tar",
    ".gz",
    ".xz",
    ".bz2",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".pyc",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
}

MAX_TEXT_BYTES = 2_000_000


def _literal(*parts: str) -> str:
    """Build sensitive prefixes without placing them verbatim in this source."""
    return "".join(parts)


SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "google_api_key": re.compile(re.escape(_literal("AI", "za", "Sy")) + r"[0-9A-Za-z_\-]{20,}"),
    "openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "bearer_token": re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-.=]{24,}"),
}

ALLOWLIST_SUBSTRINGS = (
    # Historical scanner source files may contain regex examples such as
    # Google-style regex examples in older scanners may be harmless; keep
    # this explicit allowlist for future scanner text.
    _literal("AI", "za", "Sy") + "[",
    "re.escape(_literal(",
)


@dataclass(frozen=True)
class Hit:
    kind: str
    path: str
    line_no: int
    preview: str


def should_skip_path(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in SKIP_DIR_NAMES for part in rel_parts):
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def iter_candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path, root):
            continue
        files.append(path)
    return files


def read_text_candidate(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def redacted_preview(line: str, match: re.Match[str]) -> str:
    start, end = match.span()
    token = line[start:end]
    if len(token) <= 8:
        replacement = "<redacted>"
    else:
        replacement = f"{token[:4]}...{token[-4:]}"
    preview = line[:start] + replacement + line[end:]
    return preview.strip()[:180]


def scan_file(path: Path, root: Path) -> list[Hit]:
    text = read_text_candidate(path)
    if text is None:
        return []
    rel = path.relative_to(root).as_posix()
    hits: list[Hit] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if any(allowed in line for allowed in ALLOWLIST_SUBSTRINGS):
            continue
        for kind, pattern in SECRET_PATTERNS.items():
            match = pattern.search(line)
            if match:
                hits.append(Hit(kind, rel, line_no, redacted_preview(line, match)))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan repository text files for high-signal credentials")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)

    root = args.root.resolve()

    candidates = iter_candidate_files(root)
    hits: list[Hit] = []
    for path in candidates:
        hits.extend(scan_file(path, root))

    if hits:
        print(f"repo secret scan BLOCKED: {len(hits)} hit(s)")
        for hit in hits[:50]:
            print(f"  {hit.kind}: {hit.path}:{hit.line_no}: {hit.preview}")
        if len(hits) > 50:
            print(f"  ... +{len(hits) - 50} more")
        return 1

    print(f"repo secret scan passed: {len(candidates)} candidate text paths checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
