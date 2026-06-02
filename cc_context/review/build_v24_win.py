#!/usr/bin/env python3
"""Windows build of phase1_2_spike_review_v24 (single portable faithful zip).

基于 build_v23_win.py。v24 = v23 外审第二次 B 后的 7-finding 全修版。改动 vs v23:
- v24 命名 (zip/root/extraction)
- SPIKE_OVERLAY_FILES += data/cuts/spike/remap_audit.json (F5 新 artifact)
- README v22→v24 changelog 段 (含 LSB 纠正数字 + 7 finding) + 标题 v24 + Build line spike HEAD 12f64dc
  + Finding5#2 表行 YES→PARTIAL (与 verdict 一致)
- 排除 cc_context + scripts/gemini_cross_check* (同 v23)
spike overlay 用 `git show {SPIKE_BRANCH}:`, 分支 HEAD 现 = 12f64dc, verdict/spike 代码/remap_audit 自动取修复版。
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath as _PurePosix

REPO = Path(r"D:\追光\zmd")
SRC = REPO / "scripts" / "build_phase1_2_spike_review_v22.py"
OUT_DIR = Path(tempfile.gettempdir()) / "_pkg_build_v24"
ZIP_ROOT_NAME = "_phase1_2_pkg_v24"
PROJECT_DIR = OUT_DIR / "project"
OUT_ZIP = REPO / "cc_context" / "review" / "phase1_2_spike_review_v24.zip"

spec = importlib.util.spec_from_file_location("v22src", SRC)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.REPO = REPO
mod.OUT_DIR = OUT_DIR
mod.PROJECT_DIR = PROJECT_DIR
mod.EXCLUDE_TOPLEVEL.add("cc_context")
mod.EXCLUDE_PATTERNS.append("scripts/gemini_cross_check*")
# F5: 把 v24 新增的 remap_audit.json 纳入 spike data overlay
if "data/cuts/spike/remap_audit.json" not in mod.SPIKE_OVERLAY_FILES:
    mod.SPIKE_OVERLAY_FILES.append("data/cuts/spike/remap_audit.json")

_orig_run = mod.subprocess.run


def _run_utf8(*args, **kwargs):  # type: ignore[no-untyped-def]
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _orig_run(*args, **kwargs)


mod.subprocess.run = _run_utf8

_orig_should_skip = mod.should_skip


def _should_skip_posix(rel: Path) -> bool:  # type: ignore[no-untyped-def]
    return _orig_should_skip(_PurePosix(*rel.parts))


mod.should_skip = _should_skip_posix


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"FATAL: README transform '{label}' matched {n}x (expected 1).")
    return text.replace(old, new)


V22_TO_V24_SECTION = """## v22 → v24 状态变化 (两轮外审 B → 全修)

**v22 → v23 (第九审 B → 4 soundness 修 + sizing 口径收窄)**: GPT pro 第九审 (faithful + clean 双版独立)
判 B, 复核属实, 已修: (1) `_decode_cert_b64` 加 `validate=True` (合法 b64 混入垃圾字符现 fail-closed,
micro-probe 9 → 12 case); (2) salted `hash()` → blake2b `_stable_hash` (跨进程可复现); (3) unknown-pose 静默
remap 加 telemetry; (4) A3 G10 加 `schema_err_count == 0`。Finding 5 #2 "真 cut body 分布 sizing" YES → PARTIAL。

**v23 → v24 (v23 外审第二次 B → 7 finding 全修)**: v23 送外审又判 B。最重一条是**我们自己的 sizing gate
有 bitset bug**: v1 `sizing_gate.py` 用 MSB-first 解 bitset, 但真源 `src/cuts/oracles/region_capacity_oracle.
_encode_region_bitset` 是 **LSB-first** (`arr[idx//8] |= 1 << (idx % 8)`) → region cells 解错, term 数偏高约
10x (region 大池子真实 **264** 不是 v1 写的 2026)。**"F1/F9 大池子 → 100K ~1.9 GB blow-up" 是该 bug 的假数字。**
v24 全修 7 条:
- **F1**: `sizing_gate.py` 改读**包内** `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` + `data/preprocessed/
  candidate_placements.json` (不再读外部 v22 zip), 包内一键可复现。
- **F2**: bitset 解码改 LSB-first, 与真 oracle 字节一致 (verdict.md「第九审修正」附 MSB→LSB 对照表)。
- **F3**: scope 不再写 "只 F1/F9 blow-up" —— blow-up 是 **region-size × pool-density** 的函数, 跨**所有**族;
  compact (witness/no-good) lowering 全 9 族安全, 任何族走 expanded lowering 才需设 per-cut term cap。
- **F4**: 补 F9 `density_envelope` window → pose overlap 真实计数 (10×10 window 大池子 ~360–524 term)。
- **F5**: remap telemetry 进 artifact —— `scale_ramp` jsonl 加 `n_pairs_remapped` / `true_registry_bound`,
  新增 `data/cuts/spike/remap_audit.json` (50 cert 150 pair 中 **36 unknown-remapped**: density_envelope 24 +
  port_exposure 12) → B2 cut_count_applied=100% 是 synthetic/remap 吞吐, **不是**真 registry-bound body sizing。
- **F6**: verdict writer (`spike_prod_scale_runner`) 的 G10 不再硬编码 PASS, 从 A3 fixture 真算
  (≥45 cert / 0 unsound / 0 schema_err / ≥9 family) + Finding 5 #2 模板 YES → PARTIAL (重跑 phase-B 不回归)。
- **F7**: 文案明确 toy_translator **只有 F3 `port_exposure` malformed fail-closed**, 非 F3 仍走 synthetic
  fallback —— 不泛化成 "全局 fail-closed"; 非 F3 synthetic 只算 synthetic sizing, 非真 registry-bound evidence。

**纠正后 sizing 结论 (LSB)**: fixture 尺度下 (a) 全 9 族 compact lowering → 100K 便宜 (~1–3 MB); (b) expanded
lowering 随 region × pool 变, fixture 尺度 region (139 cells) / window (10×10) 给 ~百级 term/cut → 100K
~0.1–0.3 GB (**可控, 不爆**); 只有大 region/window 趋近全 pool (~16–18K term) 才数 GB。P1.3A lowering 硬约束 =
对任何 geometric/expanded lowering 设 per-cut term cap + cumulative proto budget (跨所有族, 不止 F1/F9)。
详 `project/docs/research/p1_2_spike_sizing_gate_20260601/` (v2 LSB) + verdict.md「第九审修正」。

build: spike 分支 HEAD `12f64dc` (overlay 经 git show 自动取); master sizing gate fix `a7eff5d`。

"""


def build_readme() -> str:
    text = mod.README_V22
    text = _replace_once(text, "# 终末地工业规划器 — 项目快照 (v22)",
                         "# 终末地工业规划器 — 项目快照 (v24)", "title")
    text = _replace_once(text, "`66cf16e`; data-producing",
                         "`12f64dc` (v24: 两轮外审 B 全修, 详下方 v22→v24 节); data-producing",
                         "build-line-spike-head")
    text = _replace_once(text, "## v21 → v22 状态变化",
                         V22_TO_V24_SECTION + "## v21 → v22 状态变化", "insert-v22-to-v24")
    # Finding 5 cover 表 #2 行 YES → PARTIAL (与 verdict.md / v22→v24 节一致, 防自相矛盾)
    text = _replace_once(
        text,
        "| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family (F3 special-case phase Stage 1 generator live) with real `pose_count` / `cell_count` / `literal_count` per cert | YES |",
        "| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family 真 oracle emit ✅; **但** B2 translator 把 body lower 成合成/remap 小约束 (remap_audit 36/50 unknown), 非真 registry-bound body sizing | **PARTIAL** — 见 v22→v24 节 + verdict.md: compact lowering 全族安全, expanded lowering 跨所有族需 term cap, 已移交 P1.3A |",
        "finding5-row2-yes-to-partial",
    )
    old_extract = (
        "```bash\n"
        "unzip -q phase1_2_spike_review_v22.zip\n"
        "cd _phase1_2_pkg_v22\n"
        "chmod +x tools/7za && ./tools/7za x project.7z\n"
        "cd project\n"
        "```\n"
    )
    new_extract = (
        "单层 zip — 直接 unzip 即得 `project/` 目录, 无中间压缩层.\n"
        "\n"
        "```bash\n"
        "unzip -q phase1_2_spike_review_v24.zip\n"
        "cd _phase1_2_pkg_v24\n"
        "cd project\n"
        "```\n"
    )
    text = _replace_once(text, old_extract, new_extract, "extract-block")
    for token in ("7za", "project.7z"):
        if token in text:
            raise SystemExit(f"FATAL: README 仍引用 '{token}'。")
    return text


README_V24 = build_readme()
CHANGELOG = mod.CHANGELOG


def build_tree() -> tuple[int, int]:
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

    print(f"Project copy: {file_count} files / {total_bytes/(1024*1024):.1f} MB unzipped, skipped {skipped}")
    print("Overlaying spike data (HEAD 12f64dc)...")
    file_count += mod.overlay_spike_files()
    print("Overlaying spike code snapshot...")
    file_count += mod.overlay_spike_code_snapshot()

    spike_commit_log = mod.fetch_spike_commit_log()
    (PROJECT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    (PROJECT_DIR / "README.md").write_text(README_V24, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    file_count += 3

    forbidden_hits = [str((PROJECT_DIR / f).relative_to(PROJECT_DIR))
                      for f in mod.SPIKE_FORBIDDEN_PATHS if (PROJECT_DIR / f).exists()]
    if forbidden_hits:
        raise SystemExit(f"FATAL: spike-only paths leaked into scripts/: {forbidden_hits}")
    leaked = []
    if (PROJECT_DIR / "cc_context").exists():
        leaked.append("cc_context/")
    for g in (PROJECT_DIR / "scripts").glob("gemini_cross_check*"):
        leaked.append(str(g.relative_to(PROJECT_DIR)))
    if leaked:
        raise SystemExit(f"FATAL: 应排除项进了包: {leaked}")
    # remap_audit 在包内 (F5)
    if not (PROJECT_DIR / "data" / "cuts" / "spike" / "remap_audit.json").exists():
        raise SystemExit("FATAL: remap_audit.json 未进包 (F5 overlay 失败)")
    snap = PROJECT_DIR / "code_context" / "spike"
    for rel_str in mod.SPIKE_CODE_SNAPSHOT_FILES:
        dst_rel = rel_str[len("scripts/"):] if rel_str.startswith("scripts/") else rel_str
        if not (snap / dst_rel).exists():
            raise SystemExit(f"FATAL: spike snapshot missing: {dst_rel}")
    print("self-checks OK: 0 forbidden, 0 excluded-leak, remap_audit present, snapshot present")

    (OUT_DIR / "README.md").write_text(README_V24, encoding="utf-8")
    (OUT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    (OUT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    return file_count, total_bytes


def make_zip(use_lzma_for_big: bool) -> None:
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
    make_zip(use_lzma_for_big=False)
    zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    used = "DEFLATED"
    if zip_mb > 45.0:
        make_zip(use_lzma_for_big=True)
        zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
        used = "LZMA(big json/jsonl)+DEFLATED(rest)"
    sha = hashlib.sha256(OUT_ZIP.read_bytes()).hexdigest()
    print("=" * 60)
    print(f"OUT_ZIP : {OUT_ZIP}")
    print(f"SIZE_MB : {zip_mb:.2f}")
    print(f"SHA256  : {sha}")
    print(f"COMPRESS: {used}")
    print(f"FILES   : {file_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
