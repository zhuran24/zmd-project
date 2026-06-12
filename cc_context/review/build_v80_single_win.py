"""V80+ 外发任务全项目单包构建 (Windows, ZIP_LZMA)。

打包规则 (2026-06-10 用户裁决): **除缓存文件外全项目入包**。排除仅:
.git / __pycache__ / .pytest_cache / .pytest_tmp / .ruff_cache / .mypy_cache /
node_modules / .venv / .upstream_clones / *.pyc / 本系列输出 zip / GPT prompt 文件
(prompt 是临时 directive 且内含包 sha256, 入包会自引用)。

上传走剪贴板或 gpt_dispatch 自动化 (无 10MB 工具上限) → 单包即可。
旧的动态分卷脚本 build_v80_impl_win.py 已归档 cc_context/review/archive/
(2026-06-11 owner 裁决: 暂时用不到), 如需复活注意它当时被本脚本 import 复用。
接收端解包: python -m zipfile -e <zip> .  (Linux unzip 不支持 LZMA method)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_STEM = f"zmd_v80_impl_full_{date.today().strftime('%Y%m%d')}"
OUT_DIR = REPO_ROOT / "补丁包"
# 每轮外发的 prompt 都含本包 sha256, 入包会自引用 → 按模式排除整个系列
PROMPT_DIR = REPO_ROOT / "cc_context" / "review"
PROMPT_GLOB = "GPT_*prompt*.md"

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
    # 外发产物堆放区: 历史 snapshot 包 (sha 唯一名副本) + GPT 交付目录。
    # 入包 = 自引用套娃, 2026-06-12 实测包从 54MB 指数膨胀到 818MB。
    "补丁包",
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
        if path.parent == PROMPT_DIR and path.match(PROMPT_GLOB):
            continue
        if path.parent == OUT_DIR and path.name.startswith("zmd_v80_impl_full_"):
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


def build_info_payload(file_count: int) -> str:
    return json.dumps(
        {
            "package": f"{OUT_STEM}_single.zip",
            "purpose": "external GPT Pro task dispatch (full-project snapshot)",
            "built_on": date.today().isoformat(),
            "git_head": git_head(),
            "file_count": file_count,
            "packaging_rule": "full project except caches (owner ruling 2026-06-10)",
            "excluded_dir_names": sorted(EXCLUDED_DIR_NAMES),
            "known_absent_artifact": "data/preprocessed/candidate_placements.json (53.6MB, externalized; causes ~20 known environmental test failures)",
            "build_script": "cc_context/review/build_v80_single_win.py",
        },
        ensure_ascii=False,
        indent=2,
    )


def main() -> int:
    files = iter_package_files()
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / (OUT_STEM + "_single.zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_LZMA) as zf:
        for p in files:
            zf.write(p, "project/" + p.relative_to(REPO_ROOT).as_posix())
        zf.writestr("PACKAGE_BUILD_INFO.json", build_info_payload(len(files)))
    print(f"package: {out}")
    print(f"files: {len(files)}")
    print(f"zip_mb: {out.stat().st_size / 1024 / 1024:.1f}")
    print(f"sha256: {hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
