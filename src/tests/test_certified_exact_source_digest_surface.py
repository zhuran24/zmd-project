"""Regression tests for the conservative certified-exact source authority."""

from __future__ import annotations

from pathlib import Path

from src.search import exact_campaign


def _expected_production_source_paths(source_root: Path) -> tuple[str, ...]:
    paths = {
        path.relative_to(source_root).as_posix()
        for path in (source_root / "src").rglob("*.py")
        if not path.relative_to(source_root).as_posix().startswith("src/tests/")
    }
    scripts_root = source_root / "scripts"
    if scripts_root.exists():
        paths.update(
            path.relative_to(source_root).as_posix()
            for path in scripts_root.rglob("*.py")
        )
    for relative_path in (
        "NO_CLOSE_KERNEL_EXPERIMENT.md",
        "NO_CLOSE_KERNEL_EXPERIMENT.json",
    ):
        if (source_root / relative_path).is_file():
            paths.add(relative_path)
    return tuple(sorted(paths))


def test_certified_exact_source_digest_covers_entire_production_python_surface() -> None:
    source_root = Path(exact_campaign.__file__).resolve().parent.parent.parent

    assert exact_campaign.CERTIFIED_EXACT_SOURCE_HASH_FILES == _expected_production_source_paths(
        source_root
    )
    assert "src/render/industrial_planner_exact_status.py" in (
        exact_campaign.CERTIFIED_EXACT_SOURCE_HASH_FILES
    )
    assert "src/render/industrial_planner_single_base_delivery_viewer.py" in (
        exact_campaign.CERTIFIED_EXACT_SOURCE_HASH_FILES
    )
    assert "src/adapters/industrial_planner/export_blueprint.py" in (
        exact_campaign.CERTIFIED_EXACT_SOURCE_HASH_FILES
    )


def test_no_close_source_digest_does_not_require_intentionally_removed_checker() -> None:
    source_root = Path(exact_campaign.__file__).resolve().parent.parent.parent
    removed_checker = source_root / "scripts" / "check_p1_2_proof_obligations.py"

    if not removed_checker.exists():
        assert "scripts/check_p1_2_proof_obligations.py" not in (
            exact_campaign.CERTIFIED_EXACT_SOURCE_HASH_FILES
        )


def test_certified_exact_source_digest_paths_are_existing_regular_files() -> None:
    source_root = Path(exact_campaign.__file__).resolve().parent.parent.parent

    for relative_path in exact_campaign.CERTIFIED_EXACT_SOURCE_HASH_FILES:
        path = source_root / relative_path
        assert path.is_file(), relative_path
        assert not path.is_symlink(), relative_path
