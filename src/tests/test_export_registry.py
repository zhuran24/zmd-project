"""Tests for the additive export registry."""

from __future__ import annotations

from src.interchange.export_registry import ExportRegistry


def test_export_registry_registers_and_dispatches_targets() -> None:
    registry = ExportRegistry()

    def export_dummy(*, blueprint_payload, suffix: str = ""):
        return {"ok": True, "facility_count": len(blueprint_payload.get("facilities", [])), "suffix": suffix}

    registry.register(
        "dummy",
        export_dummy,
        description="dummy target",
        target_capabilities={"supports_layout_editing": True, "supports_dual_layer_routing": "none"},
        provenance={"source": "test"},
    )

    exported = registry.export_target("dummy", {"facilities": [{}, {}]}, suffix="phase1")

    assert registry.has_target("dummy") is True
    assert registry.names() == ("dummy",)
    assert registry.describe_targets()["dummy"]["target_capabilities"]["supports_layout_editing"] is True
    assert exported == {"ok": True, "facility_count": 2, "suffix": "phase1"}


def test_export_registry_rejects_duplicate_names() -> None:
    registry = ExportRegistry()
    registry.register("dummy", lambda **_: {"ok": True})

    try:
        registry.register("dummy", lambda **_: {"ok": False})
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected duplicate export target name to raise ValueError")
