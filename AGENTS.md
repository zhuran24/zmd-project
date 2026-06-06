# Project Agent Instructions

## Packaging Default

When the user asks to package this project without specifying another format, use the full-directory package style established by `C:\codex pj\zmd_pj\上传包\zmd_1.7z` and `zmd_2.7z`.

- Create the archive under `C:\codex pj\zmd_pj\上传包\` using the next sequence name, for example `zmd_3.7z`.
- Archive the whole top-level `zmd` directory so the package restores as `zmd\...`.
- Include `.git` by default, because the user expects this package form to preserve repository state like `zmd_1.7z`.
- Keep project artifacts such as `.artifacts`, `.claude`, `cc_context`, `docs`, `data`, `rules`, `scripts`, `specs`, `src`, and top-level project files unless the user explicitly narrows the package.
- Exclude local regenerated caches and test scratch output: `.mypy_cache`, `.pytest_cache`, `.pytest_tmp`, `.ruff_cache`, `__pycache__`, `*.pyc`, and `*.pyo`.
- After packaging, run `7z t` on the archive, compute SHA256, and report the archive path, size, hash, whether `.git` is present, and which cache classes were excluded.

If the user asks for a publish/upload-safe source package instead, do not include `.git`; state the difference clearly before reporting success.
