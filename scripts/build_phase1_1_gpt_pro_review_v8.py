#!/usr/bin/env python3
"""Build phase1_1_gpt_pro_review_v8.zip — 全项目 scope + 7z 高压 + zip 壳.

User 反馈 v7 包 87 file 太小. v8 改 strategy:
- 全项目 root copy (排除 .venv / .git / .artifacts / .codex_test_logs /
  .upstream_clones / .claude / _codex_archive / __pycache__ / cache db /
  telemetry .jsonl / tree.txt)
- candidate_placements production 全集 53 MB
- 7z 高压缩率 (-mx=9 ultra) 项目 dir → project.7z
- zip 壳含: README + COMMIT_LOG + project.7z + tools/7za (Linux x64 binary)

按 [[review-pkg-no-prompt-inside]]:
- 不放 prompt
- 不放 plan/roadmap (PHASE_POST_1_1_REFACTOR_PLAN.md 不进包)
- README/COMMIT_LOG factual only
"""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/zhuran24/claude-pj/zmd")
OUT_DIR = Path("/tmp/_phase1_1_pkg_v8")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_1_gpt_pro_review_v8.zip")

# Path 7za binary (Linux x64, dynamically linked to glibc; 兼容 GPT pro Linux sandbox)
SEVENZA_SRC = Path("/usr/lib/7zip/7za")


# 排除 path patterns
EXCLUDE_TOPLEVEL = {
    ".venv", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".artifacts", ".codex_test_logs", ".upstream_clones", ".claude",
    "_codex_archive", "node_modules",
}

EXCLUDE_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}

EXCLUDE_PATTERNS = [
    "**/telemetry_samples.jsonl",
    "**/exact_campaign_state.json.*",
    "**/exact_campaign_telemetry.json.*",
    "**/cache.*.db",
    "**/tree.txt",
    "**/*.tar.xz",
    "**/.DS_Store",
    "**/Thumbs.db",
]

# 主动性内容 ([[review-pkg-no-prompt-inside]] 不放包)
EXCLUDE_FILES = {
    "docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md",
}

EXCLUDE_REVIEW_BUILD = "scripts/build_phase1_1_gpt_pro_review_v"


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    if not parts:
        return True
    if parts[0] in EXCLUDE_TOPLEVEL:
        return True
    if any(p in EXCLUDE_NAMES for p in parts):
        return True
    rel_str = str(rel)
    if rel_str in EXCLUDE_FILES:
        return True
    if rel_str.startswith(EXCLUDE_REVIEW_BUILD):
        return True
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_str, pat):
            return True
    return False


README_V8 = """# Phase 1.1 audit pkg (全项目 scope, 7z inner archive)

终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver. 全项目
content (src + docs + rules + data + scripts + main.py + spec + audit archive).

## 解包步骤

zip 壳含 7z 高压缩 archive + 解压工具 (Linux x64):

```bash
# 1. unzip 当前 zip
unzip -q phase1_1_gpt_pro_review_v8.zip
cd _phase1_1_pkg_v8

# 2. 用 ship 的 7za 解 project.7z
chmod +x tools/7za
./tools/7za x project.7z

# 3. 进 project dir
cd project
```

如 sandbox 没 glibc 兼容 (`./tools/7za` ELF 64 LSB pie x86-64), 用系统的
`p7zip` / `7-Zip` 替代解 `project.7z`.

## 怎么跑 (解包后, cd project/)

依赖包 `zmd_deps_v3.zip` 单独上传.

```bash
python3.10+ -m venv .venv && source .venv/bin/activate
unzip -q ../zmd_deps_v3.zip -d /tmp/deps
pip install --find-links /tmp/deps -r requirements.txt

# Cut framework 单元测试
.venv/bin/python -m pytest src/tests/cuts/ -q

# python -O 防线
.venv/bin/python -O -m pytest src/tests/cuts/ -q

# 静态工具 (deps 含)
.venv/bin/python -m ruff check src/cuts/ src/tests/cuts/
.venv/bin/python -m mypy --explicit-package-bases --strict src/cuts/
.venv/bin/python -m vulture src/cuts/
.venv/bin/python -m bandit -r src/cuts/
.venv/bin/python -m radon cc src/cuts/ -s -a
```

## 文件清单 (project/ 解包后)

```
main.py                              # Campaign entry point
src/
├── cuts/                            # Phase 1.1 cut framework (本次 audit 主对象)
│   ├── lifecycle.py
│   ├── store.py
│   ├── replay.py
│   ├── families/                    # F1-F4 validator + evaluator
│   ├── oracles/                     # F1 production; F2/F3/F4 stub
│   ├── helpers/
│   └── assumptions/
├── search/                          # Outer search + benders loop (Phase 1.3 接合点)
├── models/                          # Master + binding + routing + flow
├── render/                          # Visualization
├── adapters/                        # Postprocess (Phase 3A delivery)
└── tests/                           # 单元测试 (含 cuts/)

data/preprocessed/                   # 真数据
├── candidate_placements.json        # production 全集 (81K pose / BSP 134)
├── mandatory_exact_instances.json   # 266 instance
├── generic_io_requirements.json
└── ...

rules/canonical_rules.json           # facility_templates + recipes + targets

docs/research/p3_b_design_v2_20260521/
├── cut_lifecycle_v2.md
├── state_machine_v2.md
├── PHASE_1_PLAN.md
├── cut_family_specs/                # F1-F9 spec
├── cross_check/                     # 22 round Gemini archives
└── external_review/                 # GPT pro audit archives (v1-v6)

scripts/                             # 各种 wrapper/refresh/audit script
CLAUDE.md                            # 项目 instructions
PROJECT_LOCK.md                      # 3A invariants
COMMIT_LOG.md                        # cut framework Step A-O commit timeline
README.md
requirements.txt
```

## 数据说明

`data/preprocessed/candidate_placements.json` 是 production 全集 (53 MB, 81795
pose, BSP=134).

跟历史 audit archive cite 的 viewer sample 数字 (273 pose, BSP=54, 14 outside
union) 不同 — sample 在 `data/examples/industrial_planner/current_delivery/
viewer/candidate_placements.json`.

Audit archive 的 "BSP 14/54 outside" 反例数字来自 viewer sample. production
全集 BSP 134 pose 的 outside count 不同, 跑反例 reproduce 时按 sample 数字
verify.
"""


CHANGELOG = """# Commit log (Phase 1.1 cut framework Step A-O)

15 commit src/ 改动 + 6 commit infra. 每 commit message 在 git log.

| Commit | Files touched | Subject |
|---|---|---|
| 3d35a62 | families/{...}.py + lifecycle.py + tests | A: validator schema assert 改 explicit if/return |
| 45c44d2 | families/port_exposure.py + tests | B: F3 validator 加 cert ↔ literal multiset 绑定 |
| eaed85c | families/cutset.py + tests | C: F2 partition cells ⊆ free + patch enclosure + cut_edges 集合验 |
| 5c06dff | families/component_reach.py + tests | D: F4 cert.src/sink_component == BFS + commodity_id schema_err |
| 8a38401 | helpers + families/region_capacity.py + oracles + tests | E: F1 strict P(g)⊆R check |
| e0ec660 | families + tests | F: F1 evaluate 重算 cap_R; F4 separator_cells check |
| 3553efb | families + tests | G: lru_cache(256) + F4 commodity_id spec align |
| e5c41b9 | families + store.py + archive + scripts | H: Phase 1.3 P1.21 TODO docstring + archive |
| bdaa303 | lifecycle.py + families + tests | I/J/K: step_7 family dispatch; F3 slot binding; F4 separator in-grid; F2 evaluator enclosure |
| a38620c | families/region_capacity.py + tests + F401 cleanup | L: F1 contributing_groups 去重 + tuple demand + gap consistency |
| 273fbff | replay.py + lifecycle.py + families + tests | M: replay canonical_rules=None HOLD; F2 commodity_demands registry; F4 commodity_routes registry |
| afef8f1 | families/cutset.py + store.py + tests | N: F2 contributing 去重 + cross-partition; CutStore.add_cut default held |
| c8fb7ef | families + store.py + tests | O: F1 GHOST_AGNOSTIC ghost∩R=∅; F2/F4 reject GHOST_AGNOSTIC; on_ghost_rect_changed full replay gate; add_cut initial_state validate 前置 |
"""


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    PROJECT_DIR.mkdir(parents=True)

    # Walk REPO root, copy each file unless excluded
    file_count = 0
    skipped = 0
    total_bytes = 0
    for src in REPO.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(REPO)
        if should_skip(rel):
            skipped += 1
            continue
        dst = PROJECT_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        file_count += 1
        total_bytes += src.stat().st_size

    # Write README + COMMIT_LOG inside project/ (overwrite if exists)
    (PROJECT_DIR / "README.md").write_text(README_V8, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    file_count += 2

    print(f"Project copy: {file_count} files / {total_bytes/(1024*1024):.1f} MB unzipped")
    print(f"Skipped: {skipped} files")

    # 7z 高压缩 project/ → project.7z
    print("Compressing project/ → project.7z (-mx=9 ultra)...")
    subprocess.run(
        ["7z", "a", "-mx=9", "-bd", "-y", str(SEVENZ_PATH), "project"],
        cwd=str(OUT_DIR),
        check=True,
        capture_output=True,
    )
    sevenz_mb = SEVENZ_PATH.stat().st_size / (1024 * 1024)
    print(f"7z size: {sevenz_mb:.2f} MB")

    # 删 project/ 减空间
    shutil.rmtree(PROJECT_DIR)

    # Copy 7za binary 到 tools/
    tools_dir = OUT_DIR / "tools"
    tools_dir.mkdir()
    shutil.copy2(SEVENZA_SRC, tools_dir / "7za")
    (tools_dir / "7za").chmod(0o755)

    # 写 README 到 zip 壳 root (解 zip 后看到)
    (OUT_DIR / "README.md").write_text(README_V8, encoding="utf-8")
    (OUT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")

    # Build outer zip
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    subprocess.run(
        ["zip", "-rq", str(OUT_ZIP), OUT_DIR.name],
        cwd=str(OUT_DIR.parent),
        check=True,
    )
    zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"Output: {OUT_ZIP}")
    print(f"Zip 壳 size: {zip_mb:.2f} MB")
    print(f"  ├─ project.7z: {sevenz_mb:.2f} MB ({file_count} files, {total_bytes/(1024*1024):.1f} MB unzipped)")
    print(f"  ├─ tools/7za: {(SEVENZA_SRC.stat().st_size)/(1024*1024):.2f} MB (Linux x64 ELF)")
    print(f"  ├─ README.md")
    print(f"  └─ COMMIT_LOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
