"""Target capability descriptors for downstream exporters and viewers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

_VALID_DUAL_LAYER = {"none", "partial", "full"}


@dataclass(frozen=True)
class TargetCapabilities:
    """Describes what a downstream target can represent.

    The exact solver and canonical blueprint remain the internal truth. This
    object is only used by additive adapters/exporters and compatibility
    manifests.
    """

    supports_power_overlay: bool = False
    supports_exact_proof_metadata: bool = False
    supports_dual_layer_routing: str = "none"
    supports_active_ports: bool = False
    supports_layout_editing: bool = False
    supports_persistence: bool = False
    supports_share_links: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        dual_layer = str(self.supports_dual_layer_routing)
        if dual_layer not in _VALID_DUAL_LAYER:
            raise ValueError(
                "supports_dual_layer_routing must be one of "
                f"{sorted(_VALID_DUAL_LAYER)!r}, got {dual_layer!r}"
            )
        return {
            "supports_power_overlay": bool(self.supports_power_overlay),
            "supports_exact_proof_metadata": bool(self.supports_exact_proof_metadata),
            "supports_dual_layer_routing": dual_layer,
            "supports_active_ports": bool(self.supports_active_ports),
            "supports_layout_editing": bool(self.supports_layout_editing),
            "supports_persistence": bool(self.supports_persistence),
            "supports_share_links": bool(self.supports_share_links),
            "notes": [str(note) for note in self.notes],
        }


def normalize_target_capabilities(value: TargetCapabilities | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return TargetCapabilities().to_dict()
    if isinstance(value, TargetCapabilities):
        return value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError("target capabilities must be a mapping or TargetCapabilities")

    raw_notes = value.get("notes", ())
    notes: Iterable[Any]
    if raw_notes is None:
        notes = ()
    elif isinstance(raw_notes, (list, tuple, set)):
        notes = raw_notes
    else:
        notes = (raw_notes,)

    capabilities = TargetCapabilities(
        supports_power_overlay=bool(value.get("supports_power_overlay", False)),
        supports_exact_proof_metadata=bool(value.get("supports_exact_proof_metadata", False)),
        supports_dual_layer_routing=str(value.get("supports_dual_layer_routing", "none")),
        supports_active_ports=bool(value.get("supports_active_ports", False)),
        supports_layout_editing=bool(value.get("supports_layout_editing", False)),
        supports_persistence=bool(value.get("supports_persistence", False)),
        supports_share_links=bool(value.get("supports_share_links", False)),
        notes=tuple(str(note) for note in notes),
    )
    return capabilities.to_dict()
