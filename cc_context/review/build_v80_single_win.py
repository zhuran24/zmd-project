"""单包变体: 复用 build_v80_impl_win 的文件遍历/排除逻辑, 打一个不分卷的完整 LZMA zip。

用途: 经剪贴板 (SetFileDropList + Ctrl+V) 上传时没有 10MB 工具上限, 单包更省事;
分卷主脚本留给将来 file_upload 工具路径修好后的场景。
"""
import hashlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_v80_impl_win as b

files = b.iter_package_files()
out = b.OUT_DIR / (b.OUT_STEM + "_single.zip")
if out.exists():
    out.unlink()
with zipfile.ZipFile(out, "w", zipfile.ZIP_LZMA) as zf:
    for p in files:
        zf.write(p, "project/" + p.relative_to(b.REPO_ROOT).as_posix())
    zf.writestr("PACKAGE_BUILD_INFO.json", b.build_info_payload(1, len(files)))
print(f"package: {out}")
print(f"files: {len(files)}")
print(f"zip_mb: {out.stat().st_size / 1024 / 1024:.1f}")
print(f"sha256: {hashlib.sha256(out.read_bytes()).hexdigest()}")
