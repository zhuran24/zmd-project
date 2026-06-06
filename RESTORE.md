# RESTORE.md - zmd Transfer Package 20260606 004 (7z)

This archive follows the layout of the 20260605 slim transfer package referenced during packaging:

- `RESTORE.md` at archive root
- `_cc_live_memory/` at archive root
- `zmd/` project directory, including `.git/`

Package source state:

- Source workspace: `C:\codex pj\zmd\zmd`
- Branch: `doc_tree_closeout_v20260606_004`
- Commit: `89b5a641aee1b52b922a1c7da1db098b7fffe440`
- Package format: 7z

The package keeps project source, docs, data, rules, scripts, tests, `.github/`, `.claude/`, `.artifacts/`, `cc_context/`, `third_party_snapshots/`, and git history.

The package omits local/reproducible cache artifacts only:

- `.mypy_cache/`
- `.pytest_cache/`
- `.pytest_tmp/`
- `.ruff_cache/`
- `__pycache__/`
- `*.pyc`
- `*.pyo`

## Extract

Windows PowerShell:

```powershell
7z x .\zmd_transfer_like_20260605_slim_full_project_v20260606_004_89b5a64.7z
cd .\zmd
```

Linux/macOS shell with 7z installed:

```bash
7z x zmd_transfer_like_20260605_slim_full_project_v20260606_004_89b5a64.7z
cd zmd
```

## Verify git state

```bash
git status --short --branch
git rev-parse HEAD
git fsck --no-dangling
```

Expected HEAD:

```text
89b5a641aee1b52b922a1c7da1db098b7fffe440
```

## Rebuild Python environment

Use the project's current Python/runtime policy from `README.md`, `CLAUDE.md`, and `requirements.lock.txt`.
A typical local rebuild is:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock.txt
```

On Windows PowerShell, activation is usually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock.txt
```

## Current 004 doc-tree closeout files to expect

```text
zmd/docs/DOC_TREE_COMPLETENESS.json
zmd/docs/DOC_TREE_COMPLETENESS.md
zmd/docs/subjects/doc_tree_completeness.md
zmd/scripts/check_doc_tree_completeness.py
```

## Suggested smoke checks

```bash
python scripts/preflight_gate.py
python scripts/check_doc_tree_completeness.py
python scripts/sync_doc_subjects.py --check
```
