"""Build the V80 implementation-task dispatch package (Windows, single-layer zip).

打包规则版本考古:
- v22-v28 (CC 时代): 全项目 root copy, 但排除 CC 侧工件 (cc_context/_cc_live_memory/
  补丁包/build 脚本) 与含密钥风险的 scripts/gemini_cross_check*.py。
- v80 起 (2026-06-10 用户裁决): **除缓存文件外全部入包**。cc_context、_cc_live_memory、
  补丁包 历史归档、.artifacts、.claude、.githooks、.github 全打。打包前已 grep 确认
  全树无硬编码 API key (gemini 脚本从 env 读 key), 安全检查通过才允许全打。
- 本包性质是 **实现任务委托包** (发 GPT Pro 沙盒做 V80 三件套实现), 不是审查包;
  no-priming 原则只约束审查包, 不约束实现任务包。

排除 (纯缓存/VCS/可重建):
  .git, __pycache__, .pytest_cache, .pytest_tmp, .ruff_cache, .mypy_cache,
  node_modules, .venv, .upstream_clones, *.pyc, 输出 zip 自身。

输出 (浏览器插件 file_upload 单次 10MB 上限, 单包 LZMA 14.2MB 超限 → 动态分卷):
  补丁包/zmd_v80_impl_full_<date>_partN.zip — 按压缩后物理大小分卷, 每卷 ≤9MB
  (写包时实时读 zip 输出偏移, 逼近阈值即开新卷; 卷数自适应, 不靠目录语义切,
   语义切法在体积漂移后会再次超限 — part1_project 11.7MB 实测教训)。
所有卷 zip 内都是 project/ 前缀, 全部解到同一目录即合并复原。
压缩用 ZIP_LZMA; 接收端解包用 Python zipfile (Linux unzip 6.0 不支持 LZMA method):
    for p in zmd_v80_impl_full_*_part*.zip; do python -m zipfile -e "$p" .; done
本 build 脚本自身入包; GPT prompt 文件 (GPT_v80_实现任务_prompt.md) 排除 —
prompt 是临时 directive 且内含包 sha256, 入包会造成自引用悖论。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_STEM = f"zmd_v80_impl_full_{date.today().strftime('%Y%m%d')}"
OUT_DIR = REPO_ROOT / "补丁包"
PROMPT_FILE = REPO_ROOT / "cc_context" / "review" / "GPT_v80_实现任务_prompt.md"
VOLUME_BUDGET_BYTES = 9 * 1024 * 1024

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".pytest_tmp",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    ".upstream_clones",
}
EXCLUDED_FILE_SUFFIXES = {".pyc"}


def iter_package_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT)
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
            continue
        if path.suffix in EXCLUDED_FILE_SUFFIXES:
            continue
        if path == PROMPT_FILE:
            continue
        if path.parent == OUT_DIR and path.name.startswith(OUT_STEM):
            continue
        files.append(path)
    return files


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def build_info_payload(part_index: int, file_count: int) -> str:
    return json.dumps(
        {
            "package": f"{OUT_STEM}_part{part_index}.zip",
            "merge_instruction": "extract ALL partN zips into the same directory; every part uses the project/ prefix",
            "purpose": "V80 implementation-task dispatch (GPT Pro sandbox)",
            "built_on": date.today().isoformat(),
            "git_head": git_head(),
            "file_count_this_part": file_count,
            "packaging_rule": "full project except caches (owner ruling 2026-06-10)",
            "excluded_dir_names": sorted(EXCLUDED_DIR_NAMES),
            "known_absent_artifact": "data/preprocessed/candidate_placements.json (53.6MB, externalized; causes ~20 known environmental test failures)",
            "build_script": "cc_context/review/build_v80_impl_win.py",
        },
        ensure_ascii=False,
        indent=2,
    )


def main() -> int:
    files = iter_package_files()
    OUT_DIR.mkdir(exist_ok=True)
    for stale in OUT_DIR.glob(f"{OUT_STEM}_part*.zip"):
        stale.unlink()

    volumes: list[tuple[Path, int]] = []
    part_index = 1
    zf: zipfile.ZipFile | None = None
    out_path: Path | None = None
    count = 0

    def open_volume() -> None:
        nonlocal zf, out_path, count
        out_path = OUT_DIR / f"{OUT_STEM}_part{part_index}.zip"
        zf = zipfile.ZipFile(out_path, "w", zipfile.ZIP_LZMA)
        count = 0

    def close_volume() -> None:
        nonlocal zf
        assert zf is not None and out_path is not None
        zf.writestr("PACKAGE_BUILD_INFO.json", build_info_payload(part_index, count))
        zf.close()
        volumes.append((out_path, count))
        zf = None

    open_volume()
    for path in files:
        assert zf is not None
        rel = path.relative_to(REPO_ROOT).as_posix()
        zf.write(path, f"project/{rel}")
        count += 1
        if zf.fp.tell() >= VOLUME_BUDGET_BYTES:
            close_volume()
            part_index += 1
            open_volume()
    close_volume()

    failed = False
    for vol_path, vol_count in volumes:
        digest = hashlib.sha256(vol_path.read_bytes()).hexdigest()
        size_mb = vol_path.stat().st_size / 1024 / 1024
        print(f"package: {vol_path}")
        print(f"files: {vol_count}")
        print(f"zip_mb: {size_mb:.1f}")
        print(f"sha256: {digest}")
        if vol_path.stat().st_size > 10 * 1024 * 1024:
            print(f"FATAL: {vol_path.name} exceeds the 10MB upload limit")
            failed = True
    print(f"total_files: {sum(c for _, c in volumes)} across {len(volumes)} volumes")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
