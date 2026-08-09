"""Import-boundary checks for the certified-exact source digest."""

from __future__ import annotations

import json
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


def test_certified_exact_source_hash_files_cover_registered_p1_2_proof_bearing_sinks():
    manifest_path = REPO_ROOT / "data" / "proof_obligations" / "p1_2_proof_obligations.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    protected_sources = set(CERTIFIED_EXACT_SOURCE_HASH_FILES)
    proof_bearing_classifications = {
        "p1_2_certified_path",
        "p1_2_public_surface",
        "p1_2_close_kernel",
    }

    missing_sources = []
    for entry in manifest["close_kernel_contract"]["sink_files"]:
        rel_path = str(entry.get("path", ""))
        classification = str(entry.get("classification", ""))
        if (
            classification in proof_bearing_classifications
            and rel_path.endswith(".py")
            and rel_path not in protected_sources
        ):
            missing_sources.append(rel_path)

    assert not missing_sources, (
        "P1.2 proof-bearing close-kernel sinks are missing from "
        "CERTIFIED_EXACT_SOURCE_HASH_FILES, so source drift would not invalidate "
        "certified_exact checkpoints:\n"
        + "\n".join(f"  - {path}" for path in sorted(missing_sources))
    )
