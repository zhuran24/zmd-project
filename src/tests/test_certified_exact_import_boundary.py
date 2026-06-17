"""Import-boundary checks for the certified-exact source digest."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from src.search.exact_campaign import CERTIFIED_EXACT_SOURCE_HASH_FILES


REPO_ROOT = Path(__file__).resolve().parents[2]


def _package_dirs_for_source(relative_source: str) -> list[Path]:
    relative_parent = PurePosixPath(relative_source).parent
    if relative_parent == PurePosixPath("."):
        return []

    package_dirs: list[Path] = []
    current = REPO_ROOT
    for part in relative_parent.parts:
        current = current / part
        package_dirs.append(current)
    return package_dirs


def test_certified_exact_source_hash_files_cover_package_init_execution_surface():
    protected_sources = set(CERTIFIED_EXACT_SOURCE_HASH_FILES)
    unprotected_init_files: set[str] = set()

    for relative_source in sorted(protected_sources):
        for package_dir in _package_dirs_for_source(relative_source):
            init_file = package_dir / "__init__.py"
            if not init_file.exists():
                continue

            relative_init_file = init_file.relative_to(REPO_ROOT).as_posix()
            if relative_init_file not in protected_sources:
                unprotected_init_files.add(relative_init_file)

    assert not unprotected_init_files, (
        "Certified-exact source files sit below package __init__.py files that "
        "are not in CERTIFIED_EXACT_SOURCE_HASH_FILES:\n"
        + "\n".join(f"  - {path}" for path in sorted(unprotected_init_files))
    )
