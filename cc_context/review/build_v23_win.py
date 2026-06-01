#!/usr/bin/env python3
"""Windows build of phase1_2_spike_review_v23 (single portable faithful zip).

基于 build_v22_win.py, 复用原 Linux build 脚本的全部 helper/overlay/CHANGELOG/
file-list。v23 改动:
- REPO 路径修正 (旧 dual-slug D:\\追光\\zmd\\zmd -> 现仓库根 D:\\追光\\zmd)
- OUT_DIR 放 REPO 外 (否则 rglob 自包含)
- **排除 cc_context/** (CC 内部记忆/审查工件, v22 build 时 REPO 旧路径无此目录)
- **排除 scripts/gemini_cross_check*.py** (内含 Gemini API key — v22 包误含, 见报告)
- v23 命名 (zip/root/extraction)
- README 加 v22->v23 节 (第九审 B -> 4 修 + sizing 口径收窄), 标题 + Build line + 解包块改 v23

spike overlay 用 `git show {SPIKE_BRANCH}:...`, 分支 HEAD 现 = a29fb44, 故 verdict.md +
spike 代码自动取到修复版, 无需改 SPIKE_BRANCH。
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath as _PurePosix

# --- paths ---
REPO = Path(r"D:\追光\zmd")
SRC = REPO / "scripts" / "build_phase1_2_spike_review_v22.py"
OUT_DIR = Path(tempfile.gettempdir()) / "_pkg_build_v23"  # REPO 外, 防 rglob 自包含
ZIP_ROOT_NAME = "_phase1_2_pkg_v23"
PROJECT_DIR = OUT_DIR / "project"
OUT_ZIP = REPO / "cc_context" / "review" / "phase1_2_spike_review_v23.zip"

# --- import source module (main() guarded, no side effects) ---
spec = importlib.util.spec_from_file_location("v22src", SRC)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# --- override path globals (helpers read them late-bound) ---
mod.REPO = REPO
mod.OUT_DIR = OUT_DIR
mod.PROJECT_DIR = PROJECT_DIR

# --- v23 新增排除 (mutate module globals; should_skip 调用时读) ---
mod.EXCLUDE_TOPLEVEL.add("cc_context")              # CC 内部工件 (含 gemini key in memory + 旧包)
mod.EXCLUDE_PATTERNS.append("scripts/gemini_cross_check*")  # 内含 live Gemini API key

# --- Windows: force utf-8 on text-mode subprocess (git log 中文 commit msg) ---
_orig_run = mod.subprocess.run


def _run_utf8(*args, **kwargs):  # type: ignore[no-untyped-def]
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _orig_run(*args, **kwargs)


mod.subprocess.run = _run_utf8

# --- Windows: feed should_skip a PurePosixPath so "/"-based string checks fire ---
_orig_should_skip = mod.should_skip


def _should_skip_posix(rel: Path) -> bool:  # type: ignore[no-untyped-def]
    return _orig_should_skip(_PurePosix(*rel.parts))


mod.should_skip = _should_skip_posix


# ============================================================================
# README v22 -> v23 transform (asserted replacements, fail-closed)
# ============================================================================

def _replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"FATAL: README transform '{label}' matched {n}x (expected 1).")
    return text.replace(old, new)


V22_TO_V23_SECTION = """## v22 → v23 状态变化 (第九审 B → 4 soundness 修 + sizing 口径收窄)

GPT pro 正式第九审 (v22 faithful + clean 两版独立跑) 双双判 **B (未 clean close)**。finding
经逐条对真代码 + 真数据复核全属实, 本包 (v23) 已落修复:

| Commit | Branch | Subject |
|---|---|---|
| `a29fb44` | spike | [SPIKE-V23-PATCH] 第九审 4 soundness 修 + Finding 5 #2 sizing 口径收窄 |
| `af9054a` | master | docs(spike-sizing): 第九审 sizing cheap gate 归档 |

**toy_translator / oracle_emit_fixture 4 修 (spike `a29fb44`):**
1. `_decode_cert_b64` 加 `validate=True` —— 合法 b64 混入垃圾字符现 fail-closed (旧码静默丢弃
   非 alphabet 字符 → F3 不 fail-closed)。micro-probe 9 → 12 case (加 prefix/suffix/middle), 全 PASS。
2. salted `hash()` → `_stable_hash` (blake2b): fallback / unknown-remap 跨进程可复现 (旧码
   PYTHONHASHSEED 随机, 每跑不同)。
3. unknown (facility_type, pose_id) 静默 hash-remap → 加 telemetry (`n_pairs_remapped` /
   `per_family_remapped`): applied 计数不再静默掩盖 "literal 没绑真 registry" (第九审实测 50 cert
   中 36 pair unknown: density_envelope 24 + port_exposure 12)。
4. A3 G10 pass 判定加 `schema_err_count == 0` (旧码放行 schema_err)。

**Finding 5 #2 "真 cut body 分布 sizing" 口径收窄 (verdict.md 已 YES → PARTIAL + Layer-2 risk #6):**
sizing cheap gate (`docs/research/p1_2_spike_sizing_gate_20260601/`, 对真 fixture + 真 registry 直算)
结论: cut body 的 master 约束大小不是固定可测的事实, 而是 **~1000x lowering 设计变量**。100K sizing
有界便宜 (~1–40 MB), **唯一** blow-up 路径 = F1 region_capacity / F9 density_envelope 的**大池子**
(manufacturing ~17952 pose) 容量/面积 cut 按展开式 lower (每条 ~2000–3200 term → 100K ~1.9 GB)。
其余 7 族 (路由/no-good/小池子) 任意 lower 都是几项到几十项, 随便扛。spike 的 19.55 MB 是 "紧凑
no-good / 小池子" 的合理代理, 对大池子展开低估 50–100x。→ P1.3A lowering 设计硬约束: F1/F9 二选一
((a) witness 紧凑 no-good, 或 (b) 大池子展开容量 cut 设条数/规模上界); 其余 7 族任意 lower 都安全。
另一未测轴: cert 证书存储 + replay 校验在 100K 规模 (~613 字节 bitset/cert → ~60 MB store + 逐条
revalidate) 归 P1.3A proof lifecycle sizing。

**review-pkg 卫生 (v23 build)**: 排除 `scripts/gemini_cross_check*.py` (Gemini 咨询脚本, 与本 spike
审查无关) + `cc_context/` (CC 内部记忆/审查工件), 保持包聚焦 spike 证据。

"""


def build_readme() -> str:
    text = mod.README_V22
    # 1) 标题 v22 -> v23
    text = _replace_once(
        text,
        "# 终末地工业规划器 — 项目快照 (v22)",
        "# 终末地工业规划器 — 项目快照 (v23)",
        "title",
    )
    # 2) Build line: spike HEAD 66cf16e -> a29fb44 (只动 Build 段那一处, 历史表行不动)
    text = _replace_once(
        text,
        "`66cf16e`; data-producing",
        "`a29fb44` (v23: 第九审 4 修 + sizing gate, 详下方 v22→v23 节); data-producing",
        "build-line-spike-head",
    )
    # 3) 插 v22->v23 节 (在 v21->v22 节之前)
    text = _replace_once(
        text,
        "## v21 → v22 状态变化",
        V22_TO_V23_SECTION + "## v21 → v22 状态变化",
        "insert-v22-to-v23-section",
    )
    # 4) 解包块: 双层 7za -> 单层 + v23 命名
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
        "unzip -q phase1_2_spike_review_v23.zip\n"
        "cd _phase1_2_pkg_v23\n"
        "cd project\n"
        "```\n"
    )
    text = _replace_once(text, old_extract, new_extract, "extract-block")
    # 防御: 单层包不再有 7za / project.7z 命令 token
    for token in ("7za", "project.7z"):
        if token in text:
            raise SystemExit(f"FATAL: README 仍引用 '{token}'。")
    return text


README_V23 = build_readme()
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

    print(f"Project copy: {file_count} files / {total_bytes/(1024*1024):.1f} MB unzipped")
    print(f"Skipped: {skipped} files")

    print("Overlaying spike data files from spike branch (HEAD a29fb44)...")
    file_count += mod.overlay_spike_files()
    print("Overlaying spike code snapshot to code_context/spike/ ...")
    file_count += mod.overlay_spike_code_snapshot()

    spike_commit_log = mod.fetch_spike_commit_log()
    (PROJECT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    (PROJECT_DIR / "README.md").write_text(README_V23, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    file_count += 3

    # forbidden-path self-check (spike-only code 不得进 canonical scripts/)
    forbidden_hits = [
        str((PROJECT_DIR / f).relative_to(PROJECT_DIR))
        for f in mod.SPIKE_FORBIDDEN_PATHS if (PROJECT_DIR / f).exists()
    ]
    if forbidden_hits:
        raise SystemExit(f"FATAL: spike-only paths leaked into scripts/: {forbidden_hits}")
    print(f"forbidden path check: 0 leak ({len(mod.SPIKE_FORBIDDEN_PATHS)} paths absent)")

    # gemini key 脚本 / cc_context 不得进包 self-check
    leaked = []
    if (PROJECT_DIR / "cc_context").exists():
        leaked.append("cc_context/")
    for g in (PROJECT_DIR / "scripts").glob("gemini_cross_check*"):
        leaked.append(str(g.relative_to(PROJECT_DIR)))
    if leaked:
        raise SystemExit(f"FATAL: 应排除项进了包: {leaked}")
    print("cc_context / gemini_cross_check exclusion check: 0 leak")

    # code_context/spike snapshot present
    snap = PROJECT_DIR / "code_context" / "spike"
    for rel_str in mod.SPIKE_CODE_SNAPSHOT_FILES:
        dst_rel = rel_str[len("scripts/"):] if rel_str.startswith("scripts/") else rel_str
        if not (snap / dst_rel).exists():
            raise SystemExit(f"FATAL: spike snapshot missing: {dst_rel}")
    print(f"code_context/spike snapshot present: {len(mod.SPIKE_CODE_SNAPSHOT_FILES)} OK")

    # top-level mirrors
    (OUT_DIR / "README.md").write_text(README_V23, encoding="utf-8")
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
    print("Zipping (DEFLATED level 9)...")
    make_zip(use_lzma_for_big=False)
    zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    used = "DEFLATED"
    print(f"DEFLATED zip size: {zip_mb:.2f} MB")
    if zip_mb > 45.0:
        print("  > 45 MB — re-zip big json/jsonl with LZMA...")
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
    print(f"FILES   : {file_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
