#!/usr/bin/env python3
r"""Repo-native INSTANCE/projection transclusion engine for the memory tree.

Memory architecture: an INSTANCE is the single authoritative value for a
context-independent, mechanically derivable fact; a projection is a slot inside a
memory node:

    <!-- INSTANCE:current_phase -->...<!-- /INSTANCE:current_phase -->

`--sync` renders instance values into all slots. `--check` fails if any slot is
stale, unknown, or malformed.  The default memory tree is the repository mirror
`cc_context/memory`, so the gate works in clean archives, GitHub clones, local
Codex worktrees, and the old CC live directory when explicitly passed with
`--memory-dir`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_DIR = REPO / "cc_context" / "memory"
LATEST_PACKAGE = REPO / "cc_context" / "review" / "LATEST_PACKAGE.json"
SPIKE_BRANCH = "spike/prod_scale_master_integration_20260526"
SLOT = re.compile(
    r"<!-- INSTANCE:([a-z0-9_]+) -->(?:(?!<!-- /?INSTANCE:).)*?<!-- /INSTANCE:\1 -->",
    re.DOTALL,
)
OPEN = re.compile(r"<!-- INSTANCE:[a-z0-9_]+ -->")


@dataclass(frozen=True)
class RenderResult:
    rendered: str
    slots: int
    unknown: tuple[str, ...]


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _r_latest_review_package() -> str:
    if not LATEST_PACKAGE.exists():
        return ""
    data = json.loads(LATEST_PACKAGE.read_text(encoding="utf-8"))
    version = str(data.get("version", "")).strip()
    digest = str(data.get("sha256", "")).strip()[:12]
    return f"{version} (sha `{digest}…`)" if version else ""


def _r_spike_head() -> str:
    value = _git("rev-parse", "--short", SPIKE_BRANCH)
    if value:
        return value
    if LATEST_PACKAGE.exists():
        try:
            data = json.loads(LATEST_PACKAGE.read_text(encoding="utf-8"))
            return str(data.get("spike_head", "")).strip()
        except Exception:
            return ""
    return ""


def _r_current_phase() -> str:
    phase_file = REPO / "CLAUDE.md"
    if not phase_file.exists():
        return ""
    for line in phase_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Current Phase:"):
            return line.split(":", 1)[1].strip()
    return ""


def _r_repo_url() -> str:
    url = _git("remote", "get-url", "origin")
    match = re.search(r"github\.com[/:]([^/]+/[^/.]+)", url)
    return match.group(1) if match else url


def _r_current_head() -> str:
    return _git("rev-parse", "--short", "HEAD")


INSTANCES: dict[str, Callable[[], str]] = {
    "latest_review_package": _r_latest_review_package,
    "spike_head": _r_spike_head,
    "current_phase": _r_current_phase,
    "repo_url": _r_repo_url,
    "current_head": _r_current_head,
}


def resolve_instances() -> dict[str, str]:
    values: dict[str, str] = {}
    for instance_id, resolver in INSTANCES.items():
        try:
            values[instance_id] = (resolver() or "").strip()
        except Exception:
            values[instance_id] = ""
    return values


def render_text(text: str, values: dict[str, str]) -> RenderResult:
    unknown: set[str] = set()
    slots = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal slots
        instance_id = match.group(1)
        if instance_id not in INSTANCES:
            unknown.add(instance_id)
            return match.group(0)
        value = values.get(instance_id, "")
        if not value:
            return match.group(0)
        slots += 1
        return f"<!-- INSTANCE:{instance_id} -->{value}<!-- /INSTANCE:{instance_id} -->"

    return RenderResult(SLOT.sub(repl, text), slots, tuple(sorted(unknown)))


def _memory_files(memory_dir: Path) -> list[Path]:
    return sorted(memory_dir.glob("*.md"))


def check_or_sync(memory_dir: Path, *, write: bool, verbose: bool) -> int:
    values = resolve_instances()
    changed: list[str] = []
    malformed: list[str] = []
    unknown: set[str] = set()
    filled_slots = 0

    for path in _memory_files(memory_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[instances] cannot read {path}: {exc}", file=sys.stderr)
            return 1
        if "<!-- INSTANCE:" not in text:
            continue
        opens = len(OPEN.findall(text))
        complete_slots = len(SLOT.findall(text))
        if opens != complete_slots:
            malformed.append(f"{path.name}: opens={opens}, complete_slots={complete_slots}")
            continue
        result = render_text(text, values)
        filled_slots += result.slots
        unknown.update(result.unknown)
        if result.rendered != text:
            changed.append(path.name)
            if write:
                path.write_text(result.rendered, encoding="utf-8", newline="\n")

    if malformed:
        print("[instances] malformed INSTANCE slots:", file=sys.stderr)
        for item in malformed:
            print(f"  {item}", file=sys.stderr)
    if unknown:
        print(f"[instances] unknown INSTANCE ids: {sorted(unknown)}", file=sys.stderr)

    if changed and not write:
        print("[instances] stale projection slots:", file=sys.stderr)
        for name in changed[:30]:
            print(f"  {name}", file=sys.stderr)
        if len(changed) > 30:
            print(f"  ... {len(changed) - 30} more", file=sys.stderr)

    if verbose or not (malformed or unknown or changed):
        mode = "sync" if write else "check"
        print(
            f"[instances] {mode}: files={len(_memory_files(memory_dir))}, "
            f"slots={filled_slots}, changed={len(changed)}, values={values}"
        )

    return 1 if malformed or unknown or (changed and not write) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync/check memory INSTANCE projection slots.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail if any projection is stale; do not write.")
    mode.add_argument("--sync", action="store_true", help="Rewrite stale projection slots in place.")
    parser.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    memory_dir = args.memory_dir.resolve()
    if not memory_dir.is_dir():
        print(f"[instances] memory dir not found: {memory_dir}", file=sys.stderr)
        return 1

    # Historical behavior was "run = sync" from a pre-commit hook.  Keep that
    # default for humans, while gates call --check explicitly.
    write = args.sync or not args.check
    return check_or_sync(memory_dir, write=write, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
