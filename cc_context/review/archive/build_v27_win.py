#!/usr/bin/env python3
"""Windows build of phase1_2_spike_review_v27 (single portable faithful zip).

基于 build_v26_win.py。v27 = v26 外审第五次 B/PATCH (GPT pro 复审) 后的 3-finding 全修版。
GPT pro v26 verdict: 无 soundness 洞 / 无 cap 方向错; 应用 3 finding 修后判 GO_WITH_MINOR
for sizing-only close → 可进 P1.3A。改动 vs v26:
- v27 命名 (zip/root/extraction)
- spike 分支 HEAD dc3516a → a45b8b2 (F1 _resolve_repo_root + F2/F3 verdict scope, overlay 自动取)
- README v22→v27 changelog 段 (含 v26→v27 3 finding) + 标题 v27 + Build line spike HEAD a45b8b2
- Finding 5 #1 行 YES → PARTIAL/proxy (F3; 与 verdict 一致)
- master sizing_gate v5→v6 (F2: F9 single-group cross-group-proxy 标注) + RESULTS v5→v6 澄清段 (自然进包)
- 排除 cc_context + scripts/gemini_cross_check* (同 v26)
spike overlay 用 `git show {SPIKE_BRANCH}:`, 分支 HEAD 现 = a45b8b2, verdict/spike 代码自动取修复版。
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
OUT_DIR = Path(tempfile.gettempdir()) / "_pkg_build_v27"
ZIP_ROOT_NAME = "_phase1_2_pkg_v27"
PROJECT_DIR = OUT_DIR / "project"
OUT_ZIP = REPO / "cc_context" / "review" / "phase1_2_spike_review_v27.zip"

spec = importlib.util.spec_from_file_location("v22src", SRC)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.REPO = REPO
mod.OUT_DIR = OUT_DIR
mod.PROJECT_DIR = PROJECT_DIR
mod.EXCLUDE_TOPLEVEL.add("cc_context")
mod.EXCLUDE_PATTERNS.append("scripts/gemini_cross_check*")
# F5 (since v24): 把 remap_audit.json 纳入 spike data overlay
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


V22_TO_V27_SECTION = """## v22 → v27 状态变化 (五轮外审 B → 全修)

**v26 → v27 (v26 外审第五次 B/PATCH → 3 finding 全修; GPT pro: 应用后判 GO_WITH_MINOR for
sizing-only close → 可进 P1.3A)**: v26 送外审, **无新 soundness 洞, 无 concrete-literal cap 方向错**,
核心 sizing 结论成立。3 finding (reproducibility + scoping, 主代理逐条 reproduce 后修):
- **[F1, MED reproducibility] review-mirror runner repo-root 解析未闭**: 从包内 `code_context/spike/`
  实跑 Phase B 时, mirror lib 的 `REPO_ROOT` 多走一层到 `project/code_context` → 读不存在数据
  FileNotFound (v25 的 import shim 只解决 import 不解决数据路径)。spike 分支 runner + 6 lib
  (failfast_probe / feasible_smoke / oracle_emit_fixture / scale_ramp / telemetry / toy_translator)
  加 `_resolve_repo_root()`: 探测含 `data/preprocessed/candidate_placements.json` + `src/` 的真根,
  production (`scripts/`) 与 review-mirror (`code_context/spike/`) 两布局都对。单测两布局 PASS。
  F1 修复本身已由**两布局单测** (production 选 repo 根 / mirror 选 `project` 不选 `code_context`) +
  **重建包上 mirror runner 越过 v26 的精确失败点** (`feasible_smoke.load_pose_registry` 现成功 load,
  不再 FileNotFound) 双证实。re-audit 顺带发现 `read_text()`/`.open()` 几处漏 `encoding` (V21-8F2 当时
  只改了 PLACEMENTS, 漏了 MANDATORY/HINT/jsonl) → 在 **非-utf-8 locale** (Windows GBK 或 Linux C/POSIX
  locale, 如 minimal Docker) 读含 0x80 的 UTF-8 JSON 会崩; 补全 8 处 `encoding="utf-8"` (utf-8 locale
  行为不变)。注: mirror runner 目标平台是 Linux (reviewer 已在 Linux 实跑过), 其余 Linux-ism (如
  `measure_proto_bytesize` 的 `/tmp` 临时目录) 非本轮 scope。
- **[F2, MED/LOW scoping] F9 11,644 误标成当前 concrete per-cut group expansion**: `density_envelope`
  cert 带 `group_id`, family validator 拒 witness group ≠ cert group (源码 `src/cuts/families/
  density_envelope.py` 已核) → F9 现有 lowering 是 **single-group**。sizing_gate 的 **11,644** 是
  all-manufacturing cross-group **stress proxy**, 不是当前 F9 per-cut concrete literal vector; 当前
  cert-group max 仍 **784**, same-template proxy max **4,608**。这是 F9 被保守夸大不是隐藏 blow-up,
  但文案不能把 stress proxy 当 current literal bound。sizing_gate v5→v6 拆
  `cert-grp / type-all / same-tpl / all-mfg / group-all` 列 + stress-proxy 标注; RESULTS/verdict 同步。
- **[F3, LOW/MED scoping] Finding 5 #1 行过度 claim**: README/verdict 表 "81,795 BoolVar | YES" 与
  A-F1 修正冲突 → 降为 **PARTIAL/proxy** (81,795 是 type-pool toy build, 非真 concrete pose-bool
  master build/solve; concrete proxy 325,747 由 mandatory group 展开 cheap-counted, B2 未 build/solve)。
  同步把 spike `write_verdict_md` 的 #1 行模板也改 PARTIAL (re-audit backstop 逮到的源头一致: 防 writer
  重跑把 verdict.md 的 #1 PARTIAL 覆盖回 YES; #2 行 writer 模板前轮已 PARTIAL)。

**v22 → v26 (四轮外审 B 全修, 历史)**: v25 送外审 (两份独立都 substantive), 都判 **B/PATCH, 无 soundness 洞**,
核心 framing 都 sound。并集 4 条 sizing 证据 + 1 条 guard 硬化 (主代理逐条对真代码核实):
- **[A-F1, 最重] type-pool 数 ≠ 真 master concrete literal 数**: sizing_gate 之前按 facility **type** pose pool overlap (total 81,795); 但真 pose-bool master 按 `(facility_type, operation_type)` **group×pose** 建变量 (266 inst → 19 group; mfg_3x3=8/mfg_5x5=4/mfg_6x4=5) → concrete ≈4× (**325,747**)。F4 5429 → **20,157** 是 group-expanded proxy。**F9 现有 cert 是 single-group** (v27 收窄): 当前 per-cut cert-group max 仍是 **784**; same-template proxy max **4,608**; all-manufacturing cross-group stress proxy **11,644**, 不是当前 F9 per-cut literal vector。→ **all-type UB 数 (F9 3341 / F4 5429 / ~16–18K) 是 type-pool cheap proxy, 不是真-master literal 上界**; 单 group F9 **784** + region LSB **~264** 仍是真实单 group/region 尺度。P1.3A expanded cap 输入 = `len(final_concrete_literals)` (group/template/optional 展开后), 不是 type-pool 数。sizing_gate v6 列 + cross-group proxy 标注。
- **[B-F1]** sizing_gate family summary 的 density_envelope 行不再 fallback 到 compact 4.0 (现承载真实 window→pose overlap), 与详细 F9 表 (784/3341) 不再矛盾。
- **[B-F2]** bytes/term 现脚本内可复现实测 (`ExportToFile`; 实跑 linear **4.03** / BoolOr **10.01**), 不再只 hardcode; 避开了 9.15 `CpModelProto` 无 `.ByteSize` 的坑。
- **[A-F2]** F9 `window_rect` 读序修正 `[x,y,h,w]` (现 fixture 全 10×10 故数字不变, 非方形会错)。
- **[B-F3]** 主线 F7/F8 `_validate_facility_cells_match_pose_registry` 加 **duplicate pose_id 唯一性守卫** (len(matches)==1 else unsound, fail-closed 硬化; 当前 registry 无 dup 故非现漏洞) + 2 回归测试 (cuts **414→416**)。

**纠正后 sizing 结论 (LSB + bytes/term-by-kind + concrete-literal + F9 single-group)**: (a) 全 9 族 compact
lowering → 100K 便宜 (~1–4 MB, 任何约束类型); (b) expanded lowering 预算 = (region/window × pool) ×
(per-term 字节: linear ~4 / BoolOr ~11): fixture F9 current cert-group max 784 term/cut 走 linear ~0.3 GB /
走 BoolOr ~0.86 GB; routing/all-type UB (F4 5429 / F9 3341 type-pool) 走 BoolOr ~3.7–6 GB; F9 same-template
proxy 4608 / all-manufacturing cross-group proxy 11644 只作 stress bound, 非当前 F9 per-cut literal vector;
大 region/window 趋近全 pool (~16–18K term) 任何类型都数 GB。P1.3A lowering 硬约束 = **按约束类型**设 per-cut
term cap + cumulative proto budget (cap 按 max/p99 非 family-avg), 跨**所有**族; compact 全族安全。**关键收紧
(A-F1)**: expanded cap 的输入必须是真 translator group/template/optional 展开后的 **concrete literal vector
长度**, 不是 type-pool 数 (后者是 ~4× 偏小的 proxy); 别把 3341/5429/16–18K 当真-master 上界; 任何
cross-group/template lift 必须先经过这个 concrete-vector cap。详
`project/docs/research/p1_2_spike_sizing_gate_20260601/` (v6: concrete-literal + F9 single-group scope +
OR-Tools 实测) + verdict.md「第九审/v26 sizing 修正」段。

build: spike 分支 HEAD `a45b8b2` (overlay 经 git show 自动取; v27 = A-F3 repo-root resolution
两布局 + F9 single-group scope); master sizing gate v6 (concrete-literal + F9 single-group
cross-group-proxy 标注 + summary 锁门 + OR-Tools ExportToFile 实测) + F7/F8 唯一性守卫 (cuts 414→416)。

"""


def build_readme() -> str:
    text = mod.README_V22
    text = _replace_once(text, "# 终末地工业规划器 — 项目快照 (v22)",
                         "# 终末地工业规划器 — 项目快照 (v27)", "title")
    text = _replace_once(text, "`66cf16e`; data-producing",
                         "`a45b8b2` (v27: 五轮外审 B 全修, 详下方 v22→v27 节); data-producing",
                         "build-line-spike-head")
    text = _replace_once(text, "## v21 → v22 状态变化",
                         V22_TO_V27_SECTION + "## v21 → v22 状态变化", "insert-v22-to-v27")
    # Finding 5 cover 表 #1 行 YES → PARTIAL/proxy (F3; A-F1 修正后 81,795 是 type-pool toy build proxy,
    # 非真 concrete pose-bool master build/solve)。
    text = _replace_once(
        text,
        "| 1 | 真 prod registry build master var | A3 oracle emit + B1 load_pose_registry: 81,795 BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pool | YES |",
        "| 1 | prod type-pool registry build / master-var proxy | A3 oracle emit + B1 load_pose_registry build 81,795 type-pool BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pools; concrete pose-bool upper proxy is 325,747 by mandatory group expansion, cheap-counted in sizing_gate, not built/solved by B2 | PARTIAL — sizing-only evidence; P1.3A must measure/cap `len(final_concrete_literals)` |",
        "finding5-row1-yes-to-partial",
    )
    # Finding 5 cover 表 #2 行 YES → PARTIAL (与 verdict.md / v22→v26 节一致, 防自相矛盾)
    text = _replace_once(
        text,
        "| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family (F3 special-case phase Stage 1 generator live) with real `pose_count` / `cell_count` / `literal_count` per cert | YES |",
        "| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family 真 oracle emit ✅; **但** B2 translator 把 body lower 成合成/remap 小约束 (remap_audit 36/50 unknown), 非真 registry-bound body sizing | **PARTIAL** — 见 v22→v26 节 + verdict.md: compact lowering 全族安全, expanded lowering 跨所有族需 term cap, concrete cap 以 `len(final_concrete_literals)` 为准, 已移交 P1.3A |",
        "finding5-row2-yes-to-partial",
    )
    # G10 表 staleness 同步 (与 F6-patched runner 一致)
    text = _replace_once(
        text,
        "| G10 oracle real-emit cert fixture (A3) | ≥45 + 9 families + 0 unsound | 50 cert / 9 families / 0 unsound | PASS |",
        "| G10 oracle real-emit cert fixture (A3) | ≥45 + 0 unsound + 0 schema_err | 50 cert / 9 families / 0 unsound / 0 schema_err | PASS |",
        "g10-row-add-schema-err",
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
        "unzip -q phase1_2_spike_review_v27.zip\n"
        "cd _phase1_2_pkg_v27\n"
        "cd project\n"
        "```\n"
    )
    text = _replace_once(text, old_extract, new_extract, "extract-block")
    for token in ("7za", "project.7z"):
        if token in text:
            raise SystemExit(f"FATAL: README 仍引用 '{token}'。")
    return text


README_V27 = build_readme()
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
    print("Overlaying spike data (HEAD a45b8b2)...")
    file_count += mod.overlay_spike_files()
    print("Overlaying spike code snapshot...")
    file_count += mod.overlay_spike_code_snapshot()

    # v25 外审瑕疵 (b): manifest 用 LF 行尾 (Windows write_text 默认 CRLF), 否则 reviewer 跑
    # `sha256sum -c SHA256SUMS.spike_code.txt` 时 CR 进 path → spurious FAILED。
    _manifest = PROJECT_DIR / "code_context" / "SHA256SUMS.spike_code.txt"
    if _manifest.exists():
        _manifest.write_bytes(_manifest.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8"))
        print("  manifest CRLF→LF normalized (sha256sum -c 友好)")

    spike_commit_log = mod.fetch_spike_commit_log()
    (PROJECT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    (PROJECT_DIR / "README.md").write_text(README_V27, encoding="utf-8")
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

    (OUT_DIR / "README.md").write_text(README_V27, encoding="utf-8")
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

    # 写 single living-status 锚 LATEST_PACKAGE.json (cc_context/tools/stamp_living_status.py 读它,
    # pre-commit 自动把 handoff 的可推导现状字段 stamp 到这个最新包 → 现状不可能 stale)。
    import json as _json
    import subprocess as _sp

    def _short(ref: str) -> str:
        try:
            r = _sp.run(["git", "-C", str(REPO), "rev-parse", "--short", ref],
                        capture_output=True, text=True, encoding="utf-8")
            return r.stdout.strip() if r.returncode == 0 else "?"
        except Exception:
            return "?"

    (REPO / "cc_context" / "review" / "LATEST_PACKAGE.json").write_text(
        _json.dumps({
            "version": ZIP_ROOT_NAME.rsplit("_", 1)[-1],  # _phase1_2_pkg_v27 -> v27
            "sha256": sha,
            "spike_head": _short("spike/prod_scale_master_integration_20260526"),
            "built_at_master_commit": _short("HEAD"),
            "note": "Phase 1.2 spike review package anchor; written at build time, read by cc_context/tools/stamp_living_status.py.",
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote LATEST_PACKAGE.json (living-status anchor)")

    print("=" * 60)
    print(f"OUT_ZIP : {OUT_ZIP}")
    print(f"SIZE_MB : {zip_mb:.2f}")
    print(f"SHA256  : {sha}")
    print(f"COMPRESS: {used}")
    print(f"FILES   : {file_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
