from __future__ import annotations

from collections.abc import Callable
import importlib
import os
from pathlib import Path
import subprocess
from typing import TypeAlias

import pytest


MODULE_PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
FIXED_LAUNCHER = importlib.import_module(f"{MODULE_PREFIX}.launch_fixed_geometry_router")
FIXED_WORKER = importlib.import_module(f"{MODULE_PREFIX}.solve_fixed_geometry_router")
SHELF_LAUNCHER = importlib.import_module(f"{MODULE_PREFIX}.launch_shelf_power")

Guard: TypeAlias = Callable[[Path], Path]
GuardCase: TypeAlias = tuple[str, Guard, type[Exception]]

GUARDS: tuple[GuardCase, ...] = (
    (
        "fixed-launcher",
        FIXED_LAUNCHER._resolve_project_root,
        FIXED_LAUNCHER.FixedRouterLaunchError,
    ),
    (
        "fixed-worker",
        FIXED_WORKER._resolve_project_root,
        FIXED_WORKER.FixedRouterCliError,
    ),
    (
        "shelf-launcher",
        SHELF_LAUNCHER._resolve_project_root,
        SHELF_LAUNCHER.ShelfPowerLaunchError,
    ),
)


def _git_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=10.0,
        env=_git_env(),
    )


@pytest.fixture(scope="module")
def git_roots(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    fixture_root = tmp_path_factory.mktemp("git-worktree-guards")
    ordinary = fixture_root / "ordinary"
    _git("init", "--quiet", str(ordinary))
    (ordinary / "tracked.txt").write_text("fixture\n", encoding="utf-8")
    _git("-C", str(ordinary), "add", "tracked.txt")
    _git(
        "-C",
        str(ordinary),
        "-c",
        "user.name=Git Guard Fixture",
        "-c",
        "user.email=git-guard@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    linked = fixture_root / "linked"
    _git("-C", str(ordinary), "worktree", "add", "--quiet", "--detach", str(linked), "HEAD")
    assert (ordinary / ".git").is_dir()
    assert (linked / ".git").is_file()
    return {
        "ordinary": ordinary.resolve(strict=True),
        "linked": linked.resolve(strict=True),
    }


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
@pytest.mark.parametrize("root_kind", ("ordinary", "linked"))
def test_git_root_guard_accepts_exact_checkout_top_levels(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    root_kind: str,
    git_roots: dict[str, Path],
) -> None:
    del name, error_type
    root = git_roots[root_kind]
    assert guard(root) == root


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_ignores_git_environment_poisoning(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    git_roots: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del name, error_type
    ordinary = git_roots["ordinary"]
    linked = git_roots["linked"]
    monkeypatch.setenv("GIT_DIR", str(ordinary / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(ordinary))
    assert guard(linked) == linked


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_rejects_plain_directory(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    tmp_path: Path,
) -> None:
    del name
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(plain)


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_rejects_empty_git_directory(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    tmp_path: Path,
) -> None:
    del name
    forged = tmp_path / "forged-directory"
    (forged / ".git").mkdir(parents=True)
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(forged)


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_rejects_non_top_level_subdirectory(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    git_roots: dict[str, Path],
) -> None:
    del name
    child = git_roots["ordinary"] / "nested"
    child.mkdir(exist_ok=True)
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(child)


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
@pytest.mark.parametrize(
    "payload",
    (
        b"gitdir: /definitely/missing\n",
        b"gitdir: /definitely/missing\nextra\n",
        b"gitdir: /definitely/missing",
    ),
    ids=("dangling", "extra-line", "missing-newline"),
)
def test_git_root_guard_rejects_damaged_gitdir_pointer(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    payload: bytes,
    tmp_path: Path,
) -> None:
    del name
    damaged = tmp_path / "damaged"
    damaged.mkdir()
    (damaged / ".git").write_bytes(payload)
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(damaged)


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_rejects_forged_linked_worktree_pointer(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    git_roots: dict[str, Path],
    tmp_path: Path,
) -> None:
    del name
    forged = tmp_path / "forged"
    forged.mkdir()
    (forged / ".git").write_bytes((git_roots["linked"] / ".git").read_bytes())
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(forged)


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_rejects_pointer_to_foreign_ordinary_gitdir(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    git_roots: dict[str, Path],
    tmp_path: Path,
) -> None:
    del name
    forged = tmp_path / "foreign-ordinary"
    forged.mkdir()
    foreign_git_dir = git_roots["ordinary"] / ".git"
    (forged / ".git").write_text(f"gitdir: {foreign_git_dir}\n", encoding="utf-8")
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(forged)


def test_fixed_worker_git_root_guard_preserves_absolute_path_requirement(
    git_roots: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ordinary = git_roots["ordinary"]
    monkeypatch.chdir(ordinary.parent)
    with pytest.raises(FIXED_WORKER.FixedRouterCliError, match="PROJECT_ROOT_INVALID"):
        FIXED_WORKER._resolve_project_root(Path(ordinary.name))


@pytest.mark.parametrize(("name", "guard", "error_type"), GUARDS, ids=[case[0] for case in GUARDS])
def test_git_root_guard_rejects_symlinked_git_marker(
    name: str,
    guard: Guard,
    error_type: type[Exception],
    git_roots: dict[str, Path],
    tmp_path: Path,
) -> None:
    del name
    forged = tmp_path / "symlinked"
    forged.mkdir()
    (forged / ".git").symlink_to(git_roots["ordinary"] / ".git", target_is_directory=True)
    with pytest.raises(error_type, match="PROJECT_ROOT_INVALID"):
        guard(forged)
