from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CODEGRAPH_TIMEOUT_SECONDS = 30
FULL_PREFLIGHT_COMMAND = "python scripts/preflight_gate.py --full"
ADVISORY_REMINDER = "advisory only, 提交前仍跑 preflight_gate。"

FULL_MODE = "FULL"
SELECTED_MODE = "SELECTED"

FULL_EXACT_PATHS = {
    "PROJECT_LOCK.md",
    "scripts/preflight_gate.py",
    "src/tests/conftest.py",
    "pytest.ini",
    "src/search/exact_campaign.py",
    "src/search/certified_surface.py",
    "src/search/candidate_proof_replay.py",
    "scripts/check_p1_2_proof_obligations.py",
    "scripts/check_strong_status_write_allowlist.py",
}

FULL_PREFIX_PATHS = (
    "rules/",
    "data/preprocessed/",
    "data/proof_obligations/",
    ".github/workflows/",
)


@dataclass(frozen=True)
class AffectedQuery:
    tests: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class TestSelection:
    mode: str
    selected_tests: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        if self.mode == SELECTED_MODE:
            return 0
        if self.mode == FULL_MODE:
            return 2
        return 1


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _normalize_slashes(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_test_file(path: str) -> bool:
    normalized = _normalize_slashes(path)
    name = normalized.rsplit("/", 1)[-1]
    return normalized.startswith("src/tests/") and name.startswith("test_") and name.endswith(".py")


def _is_test_target(path: str) -> bool:
    normalized = _normalize_slashes(path)
    name = normalized.rsplit("/", 1)[-1]
    return normalized.startswith("src/tests/") and name.startswith("test_") and name.endswith(".py")


def _full_reason_for_path(path: str) -> str | None:
    normalized = _normalize_slashes(path)
    if not normalized:
        return "empty or unresolved path"
    if normalized in FULL_EXACT_PATHS:
        return f"{normalized} is a lock/gate surface"
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in FULL_PREFIX_PATHS):
        return f"{normalized} is under a lock/gate data surface"
    if normalized.startswith("src/search/pr2_l0_"):
        return f"{normalized} is a PR2 L0 proof surface"
    if normalized.endswith(".json"):
        return f"{normalized} is a JSON artifact; fail closed to full preflight"
    return None


def full_trigger_reasons(changed_paths: Iterable[str]) -> tuple[str, ...]:
    reasons: list[str] = []
    for path in changed_paths:
        reason = _full_reason_for_path(path)
        if reason is not None:
            reasons.append(reason)
    return tuple(reasons)


def _coerce_affected_query(value: AffectedQuery | Iterable[str] | None, path: str) -> AffectedQuery:
    if value is None:
        return AffectedQuery(error=f"no codegraph affected result for {path}")
    if isinstance(value, AffectedQuery):
        return value
    return AffectedQuery(tests=tuple(value))


def decide_tests_for_paths(
    changed_paths: Sequence[str],
    affected_by_path: Mapping[str, AffectedQuery | Iterable[str]],
) -> TestSelection:
    normalized_paths = tuple(dict.fromkeys(_normalize_slashes(path) for path in changed_paths))
    if not normalized_paths:
        return TestSelection(
            mode=FULL_MODE,
            reasons=("no changed paths supplied; fail closed",),
        )

    reasons = list(full_trigger_reasons(normalized_paths))
    if reasons:
        return TestSelection(mode=FULL_MODE, reasons=tuple(reasons))

    selected: set[str] = set()
    for path in normalized_paths:
        if _is_test_file(path):
            selected.add(path)
            continue

        affected = _coerce_affected_query(affected_by_path.get(path), path)
        if affected.error:
            return TestSelection(mode=FULL_MODE, reasons=(affected.error,))
        for test_path in affected.tests:
            normalized_test = _normalize_slashes(test_path)
            if _is_test_target(normalized_test):
                selected.add(normalized_test)

    if not selected:
        return TestSelection(
            mode=FULL_MODE,
            reasons=("codegraph returned no src/tests/*.py targets; fail closed",),
        )

    return TestSelection(mode=SELECTED_MODE, selected_tests=tuple(sorted(selected)))


def _resolve_repo_path(raw_path: str, project_root: Path) -> tuple[str | None, str | None]:
    try:
        candidate = Path(raw_path)
        full_path = candidate if candidate.is_absolute() else project_root / candidate
        resolved = full_path.resolve(strict=False)
        root = project_root.resolve(strict=True)
        if not resolved.is_relative_to(root):
            return None, f"{raw_path} is outside repository root"
        return resolved.relative_to(root).as_posix(), None
    except OSError as exc:
        return None, f"cannot resolve {raw_path}: {exc}"


def _run_git(args: Sequence[str], project_root: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _git_diff_paths(project_root: Path) -> tuple[list[str] | None, str | None]:
    result = _run_git(["diff", "--name-only", "HEAD"], project_root)
    if result is None:
        return None, "git diff failed or timed out"
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git diff failed").strip().splitlines()[0]
        return None, message
    return [line.strip() for line in result.stdout.splitlines() if line.strip()], None


def _ensure_tracked(path: str, project_root: Path) -> str | None:
    result = _run_git(["ls-files", "--error-unmatch", "--", path], project_root)
    if result is None:
        return "git ls-files failed or timed out"
    if result.returncode != 0:
        return f"{path} is not tracked by git"
    return None


def _changed_paths_from_args(args: argparse.Namespace, project_root: Path) -> TestSelection | tuple[str, ...]:
    if args.git_diff:
        raw_paths, error = _git_diff_paths(project_root)
        if error is not None:
            return TestSelection(mode=FULL_MODE, reasons=(error,))
    else:
        raw_paths = args.paths

    normalized: list[str] = []
    for raw_path in raw_paths:
        rel_path, error = _resolve_repo_path(raw_path, project_root)
        if error is not None or rel_path is None:
            return TestSelection(mode=FULL_MODE, reasons=(error or f"cannot resolve {raw_path}",))
        tracked_error = _ensure_tracked(rel_path, project_root)
        if tracked_error is not None:
            return TestSelection(mode=FULL_MODE, reasons=(tracked_error,))
        normalized.append(rel_path)
    return tuple(dict.fromkeys(normalized))


def _run_codegraph_affected(path: str, project_root: Path) -> AffectedQuery:
    codegraph = shutil.which("codegraph")
    if codegraph is None:
        return AffectedQuery(error="codegraph CLI is not available")

    try:
        result = subprocess.run(
            [codegraph, "affected", "--json", path],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=CODEGRAPH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return AffectedQuery(error="codegraph CLI is not available")
    except subprocess.TimeoutExpired:
        return AffectedQuery(error=f"codegraph affected timed out for {path}")

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "non-zero exit").strip().splitlines()[0]
        return AffectedQuery(error=f"codegraph affected failed for {path}: {message}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return AffectedQuery(error=f"codegraph affected returned invalid JSON for {path}: {exc}")

    affected_tests = payload.get("affectedTests")
    if not isinstance(affected_tests, list):
        return AffectedQuery(error=f"codegraph affected JSON missing affectedTests for {path}")

    tests = tuple(_normalize_slashes(item) for item in affected_tests if isinstance(item, str))
    return AffectedQuery(tests=tests)


def _collect_affected_queries(paths: Sequence[str], project_root: Path) -> Mapping[str, AffectedQuery]:
    results: dict[str, AffectedQuery] = {}
    for path in paths:
        if _is_test_file(path):
            continue
        results[path] = _run_codegraph_affected(path, project_root)
    return results


def _pytest_command(selected_tests: Sequence[str]) -> str:
    targets = " ".join(selected_tests)
    return (
        "python -m pytest -p no:randomly --basetemp=.pytest_tmp/selected "
        f'-m "not slow" {targets} -q'
    )


def _print_selection(selection: TestSelection, changed_paths: Sequence[str]) -> None:
    print(f"Test selection mode: {selection.mode}")
    if changed_paths:
        print("\nChanged paths:")
        for path in changed_paths:
            print(f"  - {path}")

    if selection.mode == SELECTED_MODE:
        print("\nSelected tests:")
        for test_path in selection.selected_tests:
            print(f"  - {test_path}")
        print("\nPytest command:")
        print(_pytest_command(selection.selected_tests))
    elif selection.mode == FULL_MODE:
        print("\nReasons:")
        for reason in selection.reasons:
            print(f"  - {reason}")
        print("\nFull preflight command:")
        print(FULL_PREFLIGHT_COMMAND)
    else:
        print("\nInternal error: invalid selection mode")
    print(ADVISORY_REMINDER)


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Advisory pytest selector for changed paths.")
    parser.add_argument("paths", nargs="*", help="Repo-relative or absolute changed paths.")
    parser.add_argument("--git-diff", action="store_true", help="Use git diff --name-only HEAD as input.")
    return parser


def run(argv: Sequence[str] | None = None, project_root: Path = PROJECT_ROOT) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.git_diff and args.paths:
        parser.error("use explicit paths or --git-diff, not both")
    if not args.git_diff and not args.paths:
        parser.error("provide at least one path or --git-diff")

    changed_or_selection = _changed_paths_from_args(args, project_root)
    if isinstance(changed_or_selection, TestSelection):
        _print_selection(changed_or_selection, ())
        return changed_or_selection.exit_code

    changed_paths = changed_or_selection
    precheck_reasons = full_trigger_reasons(changed_paths)
    if precheck_reasons:
        selection = TestSelection(mode=FULL_MODE, reasons=precheck_reasons)
        _print_selection(selection, changed_paths)
        return selection.exit_code

    affected_by_path = _collect_affected_queries(changed_paths, project_root)
    selection = decide_tests_for_paths(changed_paths, affected_by_path)
    _print_selection(selection, changed_paths)
    return selection.exit_code


def main() -> None:
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        print(ADVISORY_REMINDER)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
