#!/usr/bin/env python3
"""Resolve the active Claude harness memory directory.

This resolver is deliberately conservative. If there is ambiguity, it refuses to
guess. Tools that need the live harness should call this single file instead of
hard-coding ~/.claude/projects/<slug>/memory in several places.

Resolution order:
  1. ZMD_ACTIVE_HARNESS_DIR
  2. explicit --harness-dir
  3. recent ~/.claude/projects/*/*.jsonl sessions whose cwd/projectRoot mentions this repo
  4. cwd-slug fallback, marked weak
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class HarnessResolution:
    path: Path | None
    confidence: str
    reason: str

    def ok(self) -> bool:
        return self.path is not None and self.path.exists()


def _repo_markers(root: Path) -> set[str]:
    return {str(root.resolve()), root.name, str(root).replace("/", "-").replace("\\", "-")}


def _session_mentions_repo(path: Path, markers: set[str]) -> bool:
    try:
        # Read tail-ish without loading huge files: last 80KB is enough for cwd/projectRoot hints.
        data = path.read_bytes()
        text = data[-80_000:].decode("utf-8", errors="replace")
    except OSError:
        return False
    return any(m and m in text for m in markers)


def resolve_harness(root: Path = ROOT, explicit: Path | None = None) -> HarnessResolution:
    env = os.environ.get("ZMD_ACTIVE_HARNESS_DIR")
    if env:
        p = Path(env).expanduser()
        return HarnessResolution(p if p.exists() else None, "explicit", f"ZMD_ACTIVE_HARNESS_DIR={p}")
    if explicit is not None:
        p = explicit.expanduser()
        return HarnessResolution(p if p.exists() else None, "explicit", f"--harness-dir={p}")

    projects = Path.home() / ".claude" / "projects"
    if projects.exists():
        markers = _repo_markers(root)
        candidates: list[tuple[float, Path]] = []
        for js in projects.glob("*/*.jsonl"):
            if _session_mentions_repo(js, markers):
                mem = js.parent / "memory"
                if mem.exists():
                    try:
                        mtime = js.stat().st_mtime
                    except OSError:
                        mtime = 0
                    candidates.append((mtime, mem))
        unique: list[Path] = []
        for _, mem in sorted(candidates, reverse=True):
            if mem not in unique:
                unique.append(mem)
        if len(unique) == 1:
            return HarnessResolution(unique[0], "session", "unique recent session for this repo")
        if len(unique) > 1:
            return HarnessResolution(None, "ambiguous", "multiple session harness candidates: " + ", ".join(str(x) for x in unique[:5]))

    slug = str(root.resolve()).replace(":", "").replace("\\", "-").replace("/", "-").strip("-")
    weak = projects / slug / "memory"
    if weak.exists():
        return HarnessResolution(weak, "weak", "cwd slug fallback; verify before writing")
    return HarnessResolution(None, "missing", "no active harness resolved")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--harness-dir", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = resolve_harness(ROOT, args.harness_dir)
    if args.json:
        print(json.dumps({"path": str(res.path) if res.path else None, "confidence": res.confidence, "reason": res.reason, "ok": res.ok()}, ensure_ascii=False, indent=2))
    else:
        print(f"path={res.path}\nconfidence={res.confidence}\nreason={res.reason}\nok={res.ok()}")
    return 0 if res.ok() else 1


if __name__ == "__main__":
    raise SystemExit(main())
