#!/usr/bin/env python3
"""Windows rebuild of phase1_2_spike_review_v22 package — CLEAN README variant.

Identical to build_v22_win.py in EVERY respect (project/ full tree, spike data
overlay, code_context/spike snapshot, candidate_placements, single-layer zip,
SHA256 method) EXCEPT the README is cleaned of reviewer-priming before being
written:

  - DELETE the carry-forward version-history block (`## v21 → v22 状态变化`
    through `## v13-v17 状态变化`) — a new zero-history GPT window has never
    seen v17~v21; round-by-round narration only confuses. Replaced with one
    standalone "本包内容 / 怎么验" section that states what the package is and
    contains, factually, without round references.
  - NEUTRALIZE verdict / close result-labels: `— CLOSED` finding labels and
    `GO_WITH_MINOR`-as-this-package-conclusion assertions removed/neutralized
    (the carry-forward block carrying all 12 CLOSED labels is deleted wholesale;
    a few `... closed` carry-forward phrases embedded in the otherwise-factual
    Spike-verdict section are reworded to neutral factual statements).
  - PRESERVE all factual evidence: measured numbers (414 pytest / 9-family /
    build·RSS·proto·solve / radon / mypy 0), file lists, reproduce commands,
    SHA256 verify commands, dependency install steps, single-zip unzip steps,
    and data-provenance vN tags (e.g. "telemetry_278858 = v20 rerun") which
    distinguish actual data files and are factual, not priming.

The spike's own `verdict.md` (project/docs/research/.../spike_run_20260526/
verdict.md) is the reviewer's evidence and is overlaid byte-identically — NOT
touched. Only this README string differs from the existing package.

Does NOT modify build_v22_win.py or the source build script. Run with venv python.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import zipfile
from pathlib import Path
from pathlib import PurePosixPath as _PurePosix

# --- Windows paths (override the Linux hardcoded module globals) ---
REPO = Path(r"D:\追光\zmd\zmd")
SRC = REPO / "scripts" / "build_phase1_2_spike_review_v22.py"
OUT_DIR = Path(r"D:\追光\zmd\_pkg_build_v22_clean")
# zip root dir name kept == README's `cd _phase1_2_pkg_v22` reference.
ZIP_ROOT_NAME = "_phase1_2_pkg_v22"
PROJECT_DIR = OUT_DIR / "project"
OUT_ZIP = Path(r"D:\追光\zmd\phase1_2_spike_review_v22_clean.zip")

# --- import source module (main() guarded by __main__, no side effects) ---
spec = importlib.util.spec_from_file_location("v22src_clean", SRC)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Monkeypatch path globals BEFORE calling helpers (functions read module globals
# late-bound: overlay_spike_files / overlay_spike_code_snapshot use mod.PROJECT_DIR,
# fetch_spike_commit_log uses mod.REPO / mod.SPIKE_BRANCH).
mod.REPO = REPO
mod.OUT_DIR = OUT_DIR
mod.PROJECT_DIR = PROJECT_DIR

# Windows fix: force utf-8 for text-mode subprocess.run (git log Chinese commit
# messages crash under GBK default decode). byte-mode (git show overlay) passes
# through unchanged.
_orig_run = mod.subprocess.run


def _run_utf8(*args, **kwargs):  # type: ignore[no-untyped-def]
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _orig_run(*args, **kwargs)


mod.subprocess.run = _run_utf8

# Windows fix: should_skip() string checks assume POSIX "/" separators. Feed it a
# PurePosixPath so str() yields "/" and EXCLUDE_REVIEW_BUILD / SPIKE_FORBIDDEN_PATHS
# / glob patterns match (build scripts otherwise leak in).
_orig_should_skip = mod.should_skip


def _should_skip_posix(rel: Path) -> bool:  # type: ignore[no-untyped-def]
    return _orig_should_skip(_PurePosix(*rel.parts))


mod.should_skip = _should_skip_posix


# =====================================================================
# README cleaning
# =====================================================================
def _clean_readme(readme_text: str) -> str:
    """Strip reviewer-priming from README_V22; preserve all factual content.

    Every replacement is anchored on a verbatim substring of the source string
    and asserted to occur exactly the expected number of times — any drift in
    the source aborts the build rather than silently mis-cleaning.
    """

    def _require(text: str, needle: str, n: int = 1) -> None:
        c = text.count(needle)
        if c != n:
            raise SystemExit(
                f"FATAL(clean): expected {n}x of {needle!r}, found {c}."
            )

    # --- (1) Header: drop "(v22)" label + carry-forward narrative; keep facts ---
    OLD_HEADER = (
        "# 终末地工业规划器 — 项目快照 (v22)\n"
        "\n"
        "终末地 (Arknights: Endfield) 70×70 工业规划器 certified-exact 最大空矩形求解器.\n"
        "目标 `max_lex(area, min_side)`. 266 mandatory facility, OR-Tools 9.15\n"
        "CP-SAT, LBBD 分解 (master → binding → routing → flow). 详\n"
        "`docs/项目说明/01_overview.md` + `02_mathematical_foundations.md`.\n"
        "\n"
        "全项目内容 (src + docs + rules + data + scripts + main.py + spec + audit archive)\n"
        "+ v18 起 `code_context/spike/` review-only source snapshot\n"
        "(v22 含 v21 F9 generator refactor + toy_translator F3 fail-closed\n"
        "complete-for-malformed + Python 3.14 wording 降级 + spike-lib F3 micro-probe\n"
        "test 9 case + master gate script sys.executable fix).\n"
        "\n"
        "Build: master commit `5d214f4` (详 `COMMIT_LOG.md`) + spike overlay (7 data\n"
        "file + 1 SPIKE_COMMIT_LOG, 详 `SPIKE_COMMIT_LOG.md`, spike branch HEAD\n"
        "`66cf16e`; data-producing Phase B rerun commit `ed48a05` post-F3-real-parse fix —\n"
        "v21/v22 维持 v20 B2 数据, 不需要重跑 per v20 七审/v21 八审 reviewer 共识).\n"
        "\n"
    )
    NEW_HEADER = (
        "# 终末地工业规划器 — 项目快照\n"
        "\n"
        "终末地 (Arknights: Endfield) 70×70 工业规划器 certified-exact 最大空矩形求解器.\n"
        "目标 `max_lex(area, min_side)`. 266 mandatory facility, OR-Tools 9.15\n"
        "CP-SAT, LBBD 分解 (master → binding → routing → flow). 详\n"
        "`docs/项目说明/01_overview.md` + `02_mathematical_foundations.md`.\n"
        "\n"
        "本包是项目全量快照 (src + docs + rules + data + scripts + main.py + spec +\n"
        "audit archive) + `code_context/spike/` review-only source snapshot. 核心审查\n"
        "对象是 Phase 1.2 prod-scale spike 的 sizing-layer 证据: spike `verdict.md` +\n"
        "Phase B 实测 telemetry / fixture / scale-ramp 数据, 以及生成它们的 cut\n"
        "framework (9 family) 源码.\n"
        "\n"
        "Build: master commit `5d214f4` (详 `COMMIT_LOG.md`) + spike overlay (8 data\n"
        "file + 1 SPIKE_COMMIT_LOG, 详 `SPIKE_COMMIT_LOG.md`, spike branch HEAD\n"
        "`66cf16e`; data-producing Phase B rerun commit `ed48a05`).\n"
        "\n"
    )
    _require(readme_text, OLD_HEADER, 1)
    readme_text = readme_text.replace(OLD_HEADER, NEW_HEADER)

    # --- (2) Delete the carry-forward version-history block wholesale ---
    # From "## v21 → v22 状态变化" up to (not including) "## Spike close gate 段".
    # Replace with one standalone factual "本包内容" section.
    CARRY_START = "## v21 → v22 状态变化\n"
    CARRY_END = "## Spike close gate 段 (Finding 5)\n"
    s = readme_text.find(CARRY_START)
    e = readme_text.find(CARRY_END)
    if s < 0 or e < 0 or e <= s:
        raise SystemExit("FATAL(clean): carry-forward block boundaries not found.")
    # sanity: the deleted region must contain the priming we expect to remove
    deleted = readme_text[s:e]
    if "CLOSED" not in deleted or "GO_WITH_MINOR" not in deleted:
        raise SystemExit("FATAL(clean): carry-forward block missing expected priming tokens.")

    STANDALONE = (
        "## 本包内容\n"
        "\n"
        "顶层 `project/` 是完整项目树. 与本次审查直接相关的素材:\n"
        "\n"
        "- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`\n"
        "  — spike gate 自评 (13 hard G PASS / 1 G SOFT-FAIL G6a / 0 hard N) + Finding 5\n"
        "  cover + Layer 2 risk register. 这是 spike 自身的运行结论, 作为事实证据.\n"
        "- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`\n"
        "  — Phase A (A1 branch / A2 failfast probe / A3 oracle emit fixture) detail.\n"
        "- `data/cuts/spike/` — Phase B 实测原始数据 (A3 fixture jsonl + B2 scale-ramp\n"
        "  jsonl + Phase B aggregate json + 3 份 raw telemetry jsonl). 见下面 \"文件地图\".\n"
        "- `code_context/spike/` — 产生上述数据的 spike-only Phase B 实施 source snapshot\n"
        "  (review-only, NOT master merge target). 详 `code_context/README.md`.\n"
        "- `src/cuts/` — 9 family cut framework (F1-F9) 生产源码 + oracle + helper +\n"
        "  414 单元测试 (`src/tests/cuts/`).\n"
        "- `docs/项目说明/` — 21 sub-doc 项目顶层规格 (数学基础 / paradigm / phase plan /\n"
        "  go criteria / risk).\n"
        "\n"
        "`COMMIT_LOG.md` (master line) + `SPIKE_COMMIT_LOG.md` (spike branch) 列完整\n"
        "commit 区间 + per-commit stat. 下面分 \"Spike close gate 段\" / \"本次 build 实测\n"
        "数据\" / \"解包步骤\" / \"怎么跑\" / \"文件地图\" 几节给事实与复现命令.\n"
        "\n"
    )
    readme_text = readme_text[:s] + STANDALONE + readme_text[e:]

    # --- (3) Neutralize carry-forward "审 ... closed" priming embedded in the
    # otherwise-factual Spike-verdict section (these reference review rounds /
    # finding-close labels, not the spike's own measured evidence). ---

    # 3a. G10 SOFT-FAIL "closed by" narrative -> factual evidence-strengthening.
    OLD_G10 = (
        "13 hard G PASS / 1 G SOFT-FAIL (G6a wall hit 180s cap) / 0 hard N trigger.\n"
        "G10 SOFT-FAIL (v15/v16) closed by F3 special-case phase Stage 1 generator\n"
        "(master `c768806`) + A3 rerun (spike `1d935f3`) — fixture grew 44 → 50 cert,\n"
        "8 → 9 family coverage, 0 unsound unchanged.\n"
        "\n"
        "v18 五审 evidence bug closed (v19 spike `b0b8bef` + `4e80405`): B2 100K\n"
        "`cut_count_applied` from 88,039 (88%) to 100,000 (100%) after toy_translator\n"
        "`nogood_families` 增 `port_exposure`. 5/5 tier `cut_count_applied ==\n"
        "cut_count_target` 维持. v19 六审 MED semantics closed (v20 spike `b59f19d`\n"
        "+ `ed48a05`): F3 真 2-literal parse, 100K xlate 从 v19 1.66s 减到 v20\n"
        "1.27s (-23%). 100K tier numbers above are the v20 rerun data.\n"
    )
    NEW_G10 = (
        "13 hard G PASS / 1 G SOFT-FAIL (G6a wall hit 180s cap) / 0 hard N trigger.\n"
        "G10 oracle-emit fixture 由 F3 special-case phase Stage 1 generator (master\n"
        "`c768806`) + A3 rerun (spike `1d935f3`) 产出: fixture 44 → 50 cert, 8 → 9\n"
        "family coverage, 0 unsound.\n"
        "\n"
        "B2 100K `cut_count_applied` = 100,000 (100%): toy_translator `nogood_families`\n"
        "含 `port_exposure`, 5/5 tier `cut_count_applied == cut_count_target`. F3\n"
        "走真 2-literal parse, 100K xlate 1.27s. 上表 100K tier 数字即此 rerun 数据.\n"
    )
    _require(readme_text, OLD_G10, 1)
    readme_text = readme_text.replace(OLD_G10, NEW_G10)

    # 3b. "(v18 加 — MINOR #N)" parentheticals in 文件地图 reference finding labels
    # -> plain neutral section labels (the directory contents themselves stay).
    _require(readme_text, "### docs/research/p1_2b_f3_gemini_round{1,2}_20260526/ (v18 加 — MINOR #3)\n", 1)
    readme_text = readme_text.replace(
        "### docs/research/p1_2b_f3_gemini_round{1,2}_20260526/ (v18 加 — MINOR #3)\n",
        "### docs/research/p1_2b_f3_gemini_round{1,2}_20260526/ (F3 generator Gemini cross-check)\n",
    )
    _require(readme_text, "### code_context/spike/ (v18 加 — MINOR #2 spike-only review snapshot)\n", 1)
    readme_text = readme_text.replace(
        "### code_context/spike/ (v18 加 — MINOR #2 spike-only review snapshot)\n",
        "### code_context/spike/ (spike-only review snapshot)\n",
    )

    # 3c. verdict.md描述 bullet 里的 "六审 semantics close 段" = review-round +
    # finding-close label. 中性化为事实描述 (keep "v20 rerun 数字" 数据 provenance).
    _require(readme_text, "  Layer 2 risk register (v20 rerun 数字 + 六审 semantics close 段)\n", 1)
    readme_text = readme_text.replace(
        "  Layer 2 risk register (v20 rerun 数字 + 六审 semantics close 段)\n",
        "  Layer 2 risk register (v20 rerun 数字)\n",
    )

    return readme_text


# Build cleaned README from source module string, then apply the SAME single-zip
# extraction rewrite as build_v22_win.py (strip 7za / project.7z double layer),
# and update the unzip filename to the _clean zip.
readme_text = _clean_readme(mod.README_V22)

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
    "unzip -q phase1_2_spike_review_v22_clean.zip\n"
    "cd _phase1_2_pkg_v22\n"
    "cd project\n"
    "```\n"
)
if readme_text.count(OLD_EXTRACT) != 1:
    raise SystemExit(
        f"FATAL: README extraction block appears {readme_text.count(OLD_EXTRACT)}x; expected 1."
    )
readme_text = readme_text.replace(OLD_EXTRACT, NEW_EXTRACT)

# Defensive: package ships no project.7z / tools/7za; ban those shell tokens.
for token in ("7za", "project.7z"):
    if token in readme_text:
        raise SystemExit(f"FATAL: README still references '{token}' after rewrite.")

# Defensive: cleaned README must carry no carry-forward CLOSED labels nor a
# this-package GO_WITH_MINOR conclusion. (Data-provenance vN tags are allowed.)
for token in ("CLOSED",):
    if token in readme_text:
        raise SystemExit(f"FATAL: README still contains '{token}' after cleaning.")
if "GO_WITH_MINOR" in readme_text:
    raise SystemExit("FATAL: README still contains 'GO_WITH_MINOR' after cleaning.")

changelog_text = mod.CHANGELOG


def build_tree() -> tuple[int, int]:
    """Copy + spike overlay + code_context snapshot + README/changelog/commit-log,
    using the CLEANED readme_text. Mirrors build_v22_win.build_tree."""
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

    # forbidden-path self-check (spike-only code must NOT be in canonical scripts/)
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

    # top-level copies (mirror build_v22_win)
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
