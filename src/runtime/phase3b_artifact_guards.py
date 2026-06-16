from __future__ import annotations

import re
from pathlib import Path

LOCAL_TUNING_ARTIFACT_ROOT = Path(".artifacts") / "phase3b_local_13900ks_tuning_20260430"

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


def resolve_artifact_namespace(project_root: Path, output_dir: Path, namespace: str | Path) -> Path:
    """Resolve an artifact output directory and require it to stay in one namespace."""
    root = Path(project_root).resolve()
    namespace_root = (root / LOCAL_TUNING_ARTIFACT_ROOT / Path(namespace)).resolve()
    resolved = _resolve_under_project(root, output_dir)
    _require_within(resolved, namespace_root, f"Refusing to write outside artifact namespace {namespace_root}: {resolved}")
    return resolved


def validate_artifact_run_id(run_id: str) -> str:
    text = str(run_id).strip()
    if (
        not text
        or text in {".", ".."}
        or ".." in text
        or "/" in text
        or "\\" in text
        or ":" in text
        or not _RUN_ID_PATTERN.fullmatch(text)
    ):
        raise ValueError(
            "Invalid artifact run_id; expected 1-120 characters from "
            "[A-Za-z0-9_.-] with no empty value, path separators, drive prefix, "
            "'.', '..', or '..' segment."
        )
    return text


def safe_child_artifact_dir(namespace_root: Path, run_id: str) -> Path:
    safe_run_id = validate_artifact_run_id(run_id)
    root = Path(namespace_root).resolve()
    child = (root / safe_run_id).resolve()
    _require_within(child, root, f"Refusing to create artifact child outside namespace {root}: {child}")
    return child


def _resolve_under_project(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    return (candidate if candidate.is_absolute() else project_root / candidate).resolve()


def _require_within(path: Path, root: Path, message: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(message) from exc
