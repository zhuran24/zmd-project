"""Registry for additive target exporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from src.interchange.target_capabilities import normalize_target_capabilities

ExporterCallable = Callable[..., Mapping[str, Any]]


@dataclass(frozen=True)
class ExportTargetDefinition:
    name: str
    export_fn: ExporterCallable
    description: str = ""
    mode: str = "one_way"
    target_capabilities: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "target_capabilities": normalize_target_capabilities(self.target_capabilities),
            "provenance": dict(self.provenance),
        }


class ExportRegistry:
    def __init__(self) -> None:
        self._targets: dict[str, ExportTargetDefinition] = {}

    def register(
        self,
        name: str,
        export_fn: ExporterCallable,
        *,
        description: str = "",
        mode: str = "one_way",
        target_capabilities: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> ExportTargetDefinition:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("export target name must be non-empty")
        if normalized_name in self._targets:
            raise ValueError(f"export target {normalized_name!r} already registered")
        definition = ExportTargetDefinition(
            name=normalized_name,
            export_fn=export_fn,
            description=str(description),
            mode=str(mode),
            target_capabilities=normalize_target_capabilities(target_capabilities),
            provenance=dict(provenance or {}),
        )
        self._targets[normalized_name] = definition
        return definition

    def has_target(self, name: str) -> bool:
        return str(name) in self._targets

    def get(self, name: str) -> ExportTargetDefinition:
        normalized_name = str(name)
        if normalized_name not in self._targets:
            raise KeyError(f"unknown export target: {normalized_name}")
        return self._targets[normalized_name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._targets.keys()))

    def describe_targets(self) -> dict[str, dict[str, Any]]:
        return {name: self._targets[name].describe() for name in self.names()}

    def export_target(self, name: str, blueprint_payload: Mapping[str, Any], **kwargs: Any) -> Mapping[str, Any]:
        definition = self.get(name)
        return definition.export_fn(blueprint_payload=blueprint_payload, **kwargs)
