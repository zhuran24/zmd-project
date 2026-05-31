#!/usr/bin/env python3
"""Windows rebuild of phase1_2_spike_review_v22 package (single portable zip).

Imports the original Linux build script module to reuse ALL data, text, and
git-overlay helpers; only replaces the packaging mechanism (7z+zip shell ->
single zipfile) and the path globals (Linux hardcoded -> Windows repo paths).

Does NOT modify the source build script. Run with the venv python.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import zipfile
from pathlib import Path

# --- Windows paths (override the Linux hardcoded module globals) ---
REPO = Path(r"D:\追光\zmd\zmd")
SRC = REPO / "scripts" / "build_phase1_2_spike_review_v22.py"
OUT_DIR = Path(r"D:\追光\zmd\_pkg_build_v22")
# zip root dir name kept == README's `cd _phase1_2_pkg_v22` reference so the
# README extraction step stays correct after the single-zip rewrite.
ZIP_ROOT_NAME = "_phase1_2_pkg_v22"
PROJECT_DIR = OUT_DIR / "project"
OUT_ZIP = Path(r"D:\追光\zmd\phase1_2_spike_review_v22.zip")

# --- import source module (main() guarded by __main__, no side effects) ---
spec = importlib.util.spec_from_file_location("v22src", SRC)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Monkeypatch path globals BEFORE calling helpers (functions read module globals
# late-bound: overlay_spike_files / overlay_spike_code_snapshot use mod.PROJECT_DIR,
# fetch_spike_commit_log uses mod.REPO / mod.SPIKE_BRANCH).
mod.REPO = REPO
mod.OUT_DIR = OUT_DIR
mod.PROJECT_DIR = PROJECT_DIR

# Windows fix: fetch_spike_commit_log() runs `git log` with text=True and no
# explicit encoding -> Python on Windows decodes stdout as GBK and crashes on
# the UTF-8 (Chinese) commit messages, returning None. Wrap mod.subprocess.run
# so any text-mode call forces utf-8 decoding. byte-mode calls (overlay git
# show, used for data/code) are passed through unchanged.
_orig_run = mod.subprocess.run


def _run_utf8(*args, **kwargs):  # type: ignore[no-untyped-def]
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _orig_run(*args, **kwargs)


mod.subprocess.run = _run_utf8

# Windows fix: source should_skip() does str(rel) and rel_str.startswith(
# "scripts/build_phase1_") and fnmatch with "**/" patterns — all assume POSIX
# "/" separators. On Windows str(WindowsPath) uses "\\", so the EXCLUDE_REVIEW_BUILD
# and EXCLUDE_PATTERNS / SPIKE_FORBIDDEN_PATHS string checks silently miss and
# build scripts leak in. (parts-based EXCLUDE_TOPLEVEL/NAMES are separator-agnostic
# so those still work.) Wrap should_skip to feed it a PurePosixPath so str()
# yields "/" and the source logic runs unchanged.
from pathlib import PurePosixPath as _PurePosix

_orig_should_skip = mod.should_skip


def _should_skip_posix(rel: Path) -> bool:  # type: ignore[no-untyped-def]
    return _orig_should_skip(_PurePosix(*rel.parts))


mod.should_skip = _should_skip_posix

# --- README single-zip extraction rewrite (strip 7za / project.7z double layer) ---
# The package is now a single portable zip; there is no project.7z / tools/7za
# intermediate layer. Replace the double-layer extraction block with a direct
# unzip. Match on the bash block (header `## 解包步骤` has multibyte chars that
# can vary; matching the ascii bash lines is robust).
OLD_EXTRACT = (
    "```bash\n"
    "unzip -q phase1_2_spike_review_v22.zip\n"
    "cd _phase1_2_pkg_v22\n"
    "chmod +x tools/7za && ./tools/7za x project.7z\n"
    "cd project\n"
    "```\n"
)
NEW_EXTRACT = (
    "单层 zip — 直接 unzip 即得 `project/` 目录, 无中间压缩层.\n"
    "\n"
    "```bash\n"
    "unzip -q phase1_2_spike_review_v22.zip\n"
    "cd _phase1_2_pkg_v22\n"
    "cd project\n"
    "```\n"
)

readme_text = mod.README_V22
if OLD_EXTRACT not in readme_text:
    raise SystemExit("FATAL: README extraction block not found verbatim; aborting.")
if readme_text.count(OLD_EXTRACT) != 1:
    raise SystemExit(f"FATAL: extraction block appears {readme_text.count(OLD_EXTRACT)}x; expected 1.")
readme_text = readme_text.replace(OLD_EXTRACT, NEW_EXTRACT)

# Defensive: ensure the double-layer extraction COMMAND is gone (the package no
# longer ships project.7z / tools/7za). Prose mentions are fine; we ban the
# actual shell tokens that would point at a missing intermediate archive.
for token in ("7za", "project.7z"):
    if token in readme_text:
        raise SystemExit(f"FATAL: README still references '{token}' after rewrite.")

changelog_text = mod.CHANGELOG


def build_tree() -> tuple[int, int]:
    """Replicate source main() copy+overlay+README+selfcheck (lines 1106-1167)."""
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    PROJECT_DIR.mkdir(parents=True)

    file_count = 0
    skipped = 0
    total_bytes = 0
    for src in REPO.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(REPO)
        if mod.should_skip(rel):
            skipped += 1
            continue
        dst = PROJECT_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        file_count += 1
        total_bytes += src.stat().st_size

    print(f"Project copy: {file_count} files / {total_bytes/(1024*1024):.1f} MB unzipped")
    print(f"Skipped: {skipped} files")

    print("Overlaying spike data files from spike branch...")
    spike_added = mod.overlay_spike_files()
    file_count += spike_added
    print(f"Spike data overlay: {spike_added} files added")

    print("Overlaying spike code snapshot to code_context/spike/ ...")
    snapshot_added = mod.overlay_spike_code_snapshot()
    file_count += snapshot_added
    print(f"Spike code snapshot: {snapshot_added} files added")

    spike_commit_log = mod.fetch_spike_commit_log()
    (PROJECT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    (PROJECT_DIR / "README.md").write_text(readme_text, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(changelog_text, encoding="utf-8")
    file_count += 3

    # forbidden-path self-check
    forbidden_hits = []
    for forbidden in mod.SPIKE_FORBIDDEN_PATHS:
        check_path = PROJECT_DIR / forbidden
        if check_path.exists():
            forbidden_hits.append(str(check_path.relative_to(PROJECT_DIR)))
    if forbidden_hits:
        raise SystemExit(f"FATAL: spike-only paths leaked into scripts/: {forbidden_hits}")
    print(f"Canonical scripts/ forbidden path check: 0 leak "
          f"(all {len(mod.SPIKE_FORBIDDEN_PATHS)} paths absent)")

    # code_context/spike snapshot present self-check
    snapshot_check_dir = PROJECT_DIR / "code_context" / "spike"
    for rel_str in mod.SPIKE_CODE_SNAPSHOT_FILES:
        dst_rel = rel_str[len("scripts/"):] if rel_str.startswith("scripts/") else rel_str
        if not (snapshot_check_dir / dst_rel).exists():
            raise SystemExit(f"FATAL: spike snapshot missing: {dst_rel}")
    print(f"code_context/spike/ snapshot present check: "
          f"{len(mod.SPIKE_CODE_SNAPSHOT_FILES)}/{len(mod.SPIKE_CODE_SNAPSHOT_FILES)} OK")

    # top-level copies (mirror source main() lines 1186-1188)
    (OUT_DIR / "README.md").write_text(readme_text, encoding="utf-8")
    (OUT_DIR / "COMMIT_LOG.md").write_text(changelog_text, encoding="utf-8")
    (OUT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")

    return file_count, total_bytes


def make_zip(use_lzma_for_big: bool) -> None:
    """Zip the whole OUT_DIR tree under ZIP_ROOT_NAME/ as the archive root."""
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    big_ext = (".json", ".jsonl")
    with zipfile.ZipFile(OUT_ZIP, "w") as zf:
        for path in sorted(OUT_DIR.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(OUT_DIR)
            arcname = f"{ZIP_ROOT_NAME}/{rel.as_posix()}"
            if use_lzma_for_big and path.suffix.lower() in big_ext and path.stat().st_size > 1_000_000:
                zf.write(path, arcname, compress_type=zipfile.ZIP_LZMA)
            else:
                zf.write(path, arcname, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    file_count, total_bytes = build_tree()

    # First attempt: DEFLATED level 9.
    print("Zipping (DEFLATED level 9)...")
    make_zip(use_lzma_for_big=False)
    zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    used = "DEFLATED"
    print(f"DEFLATED zip size: {zip_mb:.2f} MB")
    if zip_mb > 45.0:
        print("  > 45 MB threshold — re-zipping big .json/.jsonl with LZMA...")
        make_zip(use_lzma_for_big=True)
        zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
        used = "LZMA(big json/jsonl)+DEFLATED(rest)"
        print(f"LZMA-hybrid zip size: {zip_mb:.2f} MB")

    sha = hashlib.sha256(OUT_ZIP.read_bytes()).hexdigest()
    print("=" * 60)
    print(f"OUT_ZIP : {OUT_ZIP}")
    print(f"SIZE_MB : {zip_mb:.2f}")
    print(f"SHA256  : {sha}")
    print(f"COMPRESS: {used}")
    print(f"FILES   : {file_count} (project + top-level)")
    print(f"UNZIPPED: {total_bytes/(1024*1024):.1f} MB (master copy) + overlays")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
