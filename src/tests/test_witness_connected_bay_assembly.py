from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path

import pytest


MODULE = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.assemble_connected_bays"
)


def _selection(source: Path) -> dict[str, object]:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    selected: list[dict[str, object]] = []
    for template, count in MODULE.EXPECTED_TEMPLATE_COUNTS.items():
        for index in range(count):
            selected.append(
                {
                    "template": template,
                    "mode": "north_to_south",
                    "body": [[index, 0]],
                    "inputs": [[index, 1]],
                    "outputs": [[index, -1]],
                }
            )
    components = [
        {"component": component, "origin": [component, 0], "selected": []}
        for component in range(17)
    ]
    components[0]["selected"] = selected
    poles = [[x, y] for y in range(5) for x in range(7)]
    return {
        "schema_version": MODULE.SELECTION_SCHEMA_VERSION,
        "status": MODULE.SELECTION_READY_STATUS,
        "claim_boundary": "research geometry handoff only",
        "baseline_head": MODULE.EXPECTED_BASELINE_HEAD,
        "source_artifacts": [{"path": str(source), "sha256": digest}],
        "pole_anchors": poles,
        "protected_rectangle": [60, 10, 6, 7],
        "components": list(reversed(components)),
    }


def test_parse_selection_rehashes_sources_and_sorts_components(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    parsed = MODULE.parse_selection(_selection(source), selection_parent=tmp_path)
    assert len(parsed.pole_anchors) == 35
    assert parsed.protected_rectangle == (60, 10, 6, 7)
    assert [component.component for component in parsed.components] == list(range(17))
    assert sum(len(component.selected) for component in parsed.components) == 219


def test_parse_selection_rejects_pole_count_below_hard_shape(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    value = _selection(source)
    value["pole_anchors"] = value["pole_anchors"][:-1]
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE.parse_selection(value, selection_parent=tmp_path)
    assert caught.value.code == "POLE_COUNT"


def test_parse_selection_rejects_source_hash_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    value = _selection(source)
    value["source_artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE.parse_selection(value, selection_parent=tmp_path)
    assert caught.value.code == "SOURCE_HASH_MISMATCH"


def test_parse_selection_rejects_component_set_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    value = _selection(source)
    value["components"] = value["components"][:-1]
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE.parse_selection(value, selection_parent=tmp_path)
    assert caught.value.code == "COMPONENT_IDS"


def test_parse_selection_rejects_extra_fields(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    value = _selection(source)
    value["unexpected"] = True
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE.parse_selection(value, selection_parent=tmp_path)
    assert caught.value.code == "SCHEMA_FIELDS"


def test_parse_selection_accepts_legacy_fixed_protected_rectangle(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    value = _selection(source)
    value["schema_version"] = MODULE.LEGACY_SELECTION_SCHEMA_VERSION
    del value["protected_rectangle"]

    parsed = MODULE.parse_selection(value, selection_parent=tmp_path)

    assert parsed.protected_rectangle == (7, 36, 6, 7)


@pytest.mark.parametrize(
    "rectangle",
    ([60, 10, 7, 6], [65, 10, 6, 7], [60, 10, 6]),
)
def test_parse_selection_rejects_invalid_protected_rectangle(
    tmp_path: Path,
    rectangle: list[int],
) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    value = _selection(source)
    value["protected_rectangle"] = rectangle

    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE.parse_selection(value, selection_parent=tmp_path)

    assert caught.value.code == "PROTECTED_RECTANGLE"


def test_validation_count_contract_rejects_accepted_dry_port_drift() -> None:
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE._assert_dry_validation_counts(
            {"accepted": True, "port_spec_count": MODULE.EXPECTED_TOTAL_ACTIVE_PORTS - 1}
        )
    assert caught.value.code == "DRY_TOTAL_PORT_COUNT"


def test_validation_count_contract_rejects_local_binding_drift() -> None:
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE._assert_materializer_validation_counts(
            {
                "manufacturing_binding_instance_count": MODULE.EXPECTED_MANUFACTURING_COUNT,
                "manufacturing_binding_port_count": MODULE.EXPECTED_MANUFACTURING_ACTIVE_PORTS - 1,
            }
        )
    assert caught.value.code == "LOCAL_BINDING_PORT_COUNT"


def _publication_report() -> dict[str, object]:
    return {
        "schema_version": MODULE.REPORT_SCHEMA_VERSION,
        "status": "READY_TO_WRITE",
        "dry_validation": {"accepted": True, "port_spec_count": MODULE.EXPECTED_TOTAL_ACTIVE_PORTS},
        "geometry_output": None,
        "geometry_output_sha256": None,
    }


def test_geometry_publication_persists_report_before_final_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "RESEARCH_ROOT", tmp_path)
    geometry = tmp_path / "geometry.json"
    report_path = tmp_path / "report.json"
    payload = {"schema_version": "test.v1", "value": 7}
    real_link = os.link

    def checked_link(source: Path, target: Path) -> None:
        assert target == geometry
        persisted_report = json.loads(report_path.read_text(encoding="ascii"))
        assert persisted_report["status"] == "MATERIALIZED"
        assert persisted_report["geometry_output"] == str(geometry)
        assert persisted_report["publication_commit_condition"] == (
            "final_geometry_exists_with_declared_sha256"
        )
        assert not geometry.exists()
        real_link(source, target)

    monkeypatch.setattr(MODULE.os, "link", checked_link)
    result = MODULE._publish_geometry_after_report(
        geometry_output=geometry,
        geometry_payload=payload,
        report_output=report_path,
        report=_publication_report(),
    )

    assert result["status"] == "MATERIALIZED"
    assert json.loads(geometry.read_text(encoding="ascii")) == payload
    assert result == json.loads(report_path.read_text(encoding="ascii"))
    assert not list(tmp_path.glob(".geometry.json.pending.*"))


def test_geometry_publication_cleanup_failure_reports_already_published_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "RESEARCH_ROOT", tmp_path)
    geometry = tmp_path / "geometry.json"
    report_path = tmp_path / "report.json"
    real_unlink = Path.unlink

    def fail_pending_cleanup(path: Path, *args: object, **kwargs: object) -> None:
        if path.name.startswith(".geometry.json.pending."):
            raise PermissionError("injected pending cleanup failure")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(MODULE.Path, "unlink", fail_pending_cleanup)
    with pytest.raises(MODULE.ConnectedBayAssemblyError) as caught:
        MODULE._publish_geometry_after_report(
            geometry_output=geometry,
            geometry_payload={"schema_version": "test.v1"},
            report_output=report_path,
            report=_publication_report(),
        )

    assert caught.value.code == "GEOMETRY_PUBLISHED_PENDING_CLEANUP"
    assert "final geometry is published" in str(caught.value)
    assert geometry.is_file()
    assert report_path.is_file()
