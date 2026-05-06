"""Tests for parsing endfield-calc-style TypeScript source snapshots."""

from __future__ import annotations

from pathlib import Path
import zipfile

from src.adapters.endfield_calc.snapshot_ingest import (
    detect_snapshot_source_format,
    ingest_snapshot_source,
    load_snapshot_source,
)

FIXTURE_DIR = Path("third_party_snapshots/endfield_calc/typescript_fixture")
UPSTREAM_REPOSITORY_FIXTURE_DIR = Path("third_party_snapshots/endfield_calc/upstream_repository_fixture")


def _build_repository_layout_from_flat_fixture(target_root: Path) -> Path:
    repo_root = target_root / "endfield-calc"
    (repo_root / "src" / "data").mkdir(parents=True)
    (repo_root / "src" / "types").mkdir(parents=True)
    (repo_root / "package.json").write_text(
        '{"name":"endfield-calcs","version":"0.5.2"}\n',
        encoding="utf-8",
    )
    for filename in ("items.ts", "recipes.ts", "facilities.ts"):
        (repo_root / "src" / "data" / filename).write_text(
            (FIXTURE_DIR / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (repo_root / "src" / "types" / "constants.ts").write_text(
        (FIXTURE_DIR / "constants.ts").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return repo_root


def _zip_directory(root: Path, archive_path: Path, *, nested_prefix: str) -> Path:
    with zipfile.ZipFile(archive_path, "w") as archive:
        for file_path in sorted(root.rglob("*")):
            if not file_path.is_file():
                continue
            archive.write(
                file_path,
                arcname=(Path(nested_prefix) / file_path.relative_to(root)).as_posix(),
            )
    return archive_path


def test_detect_snapshot_source_format_recognizes_typescript_fixture() -> None:
    assert detect_snapshot_source_format(FIXTURE_DIR) == "typescript"


def test_detect_snapshot_source_format_recognizes_repository_root_layout(tmp_path: Path) -> None:
    repo_root = _build_repository_layout_from_flat_fixture(tmp_path)

    assert detect_snapshot_source_format(repo_root) == "typescript"


def test_detect_snapshot_source_format_recognizes_zip_archive(tmp_path: Path) -> None:
    archive_path = _zip_directory(
        UPSTREAM_REPOSITORY_FIXTURE_DIR,
        tmp_path / "endfield-calc-uploaded.zip",
        nested_prefix="uploaded/endfield-calc-master",
    )

    assert detect_snapshot_source_format(archive_path) == "typescript"


def test_load_snapshot_source_resolves_constants_from_typescript_fixture() -> None:
    loaded = load_snapshot_source(FIXTURE_DIR, source_format="typescript")

    assert loaded["items"][0]["id"] == "raw_ore"
    assert loaded["recipes"][0]["facilityId"] == "item_port_furnance_1"
    assert loaded["facilities"][0]["powerConsumption"] == 5
    assert loaded["snapshot_metadata"]["source"] == "JamboChen/endfield-calc TypeScript source"
    assert loaded["snapshot_metadata"]["source_layout"] == "flat_directory"



def test_load_snapshot_source_reads_repository_root_layout(tmp_path: Path) -> None:
    repo_root = _build_repository_layout_from_flat_fixture(tmp_path)

    loaded = load_snapshot_source(repo_root, source_format="typescript")

    assert loaded["items"][0]["id"] == "raw_ore"
    assert loaded["snapshot_metadata"]["source_version"] == "0.5.2"
    assert loaded["snapshot_metadata"]["package_name"] == "endfield-calcs"
    assert loaded["snapshot_metadata"]["source_layout"] == "repository_root"



def test_load_snapshot_source_reads_real_upstream_repository_fixture() -> None:
    loaded = load_snapshot_source(UPSTREAM_REPOSITORY_FIXTURE_DIR, source_format="typescript")

    assert len(loaded["items"]) == 130
    assert len(loaded["recipes"]) == 172
    assert len(loaded["facilities"]) == 14
    assert loaded["snapshot_metadata"]["source_version"] == "0.5.2"
    assert loaded["snapshot_metadata"]["package_name"] == "endfield-calcs"
    assert loaded["snapshot_metadata"]["source_layout"] == "repository_root"
    assert any(item["id"] == "item_liquid_water" and item["isLiquid"] for item in loaded["items"])
    assert any(
        recipe["id"] == "component_copper_cmpt_1" and recipe["facilityId"] == "item_port_cmpt_mc_1"
        for recipe in loaded["recipes"]
    )
    assert any(
        facility["id"] == "item_port_furnance_1" and facility["powerConsumption"] == 5
        for facility in loaded["facilities"]
    )



def test_load_snapshot_source_reads_real_upstream_zip_archive(tmp_path: Path) -> None:
    archive_path = _zip_directory(
        UPSTREAM_REPOSITORY_FIXTURE_DIR,
        tmp_path / "endfield-calc-uploaded.zip",
        nested_prefix="uploaded/endfield-calc-master/endfield-calc-master",
    )

    loaded = load_snapshot_source(archive_path, source_format="typescript")

    assert len(loaded["items"]) == 130
    assert loaded["snapshot_metadata"]["source_version"] == "0.5.2"
    assert loaded["snapshot_metadata"]["source_layout"] == "zip_archive_repository"



def test_ingest_snapshot_source_normalizes_typescript_fixture_into_catalog() -> None:
    catalog = ingest_snapshot_source(FIXTURE_DIR, source_format="typescript")

    assert catalog["metadata"]["source"] == "JamboChen/endfield-calc TypeScript source"
    assert any(item["id"] == "raw_ore" for item in catalog["items"])
    assert any(recipe["id"] == "smelt_iron" and recipe["cycle_seconds"] == 3.0 for recipe in catalog["recipes"])
    assert any(facility["id"] == "item_port_furnance_1" and facility["needs_power"] for facility in catalog["facilities"])
    assert any(power_entry["facility_id"] == "item_port_furnance_1" and power_entry["value_kw"] == 5.0 for power_entry in catalog["power"])



def test_ingest_snapshot_source_normalizes_real_upstream_fixture_into_catalog() -> None:
    catalog = ingest_snapshot_source(UPSTREAM_REPOSITORY_FIXTURE_DIR, source_format="typescript")

    assert catalog["metadata"]["source"] == "JamboChen/endfield-calc TypeScript source"
    assert catalog["metadata"]["source_version"] == "0.5.2"
    assert catalog["metadata"]["extensions"]["package_name"] == "endfield-calcs"
    assert catalog["metadata"]["extensions"]["source_layout"] == "repository_root"
    assert any(item["id"] == "item_liquid_water" and item["category"] == "liquid" for item in catalog["items"])
    assert any(
        recipe["id"] == "component_copper_cmpt_1" and recipe["cycle_seconds"] == 2.0
        for recipe in catalog["recipes"]
    )
    assert any(
        facility["id"] == "item_port_furnance_1" and facility["power"]["consumption_kw"] == 5.0
        for facility in catalog["facilities"]
    )
    assert any(
        power_entry["facility_id"] == "item_port_furnance_1" and power_entry["value_kw"] == 5.0
        for power_entry in catalog["power"]
    )
