"""Session-scoped immutable projections of Stage-B static artifacts.

This module establishes the typed-platform boundary by taking one recursive copy
of four explicitly supplied authoritative static artifacts.  The resulting
bundle never aliases builder inputs and carries a deterministic, content-derived
identity.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias, cast


FrozenScalar: TypeAlias = None | bool | int | float | str
FrozenValue: TypeAlias = (
    FrozenScalar | Mapping[str, "FrozenValue"] | tuple["FrozenValue", ...] | frozenset["FrozenValue"]
)

_BUNDLE_DIGEST_PREFIX = b"zmd.frozen-artifacts.v1:"


@dataclass(frozen=True, slots=True, init=False)
class FrozenArtifactBundle:
    """Deeply immutable static inputs shared by all Stage-B snapshots.

    Construction itself establishes the invariant, so even a direct caller
    cannot inject mutable mappings or choose a forged digest.  The public
    factory below accepts the same four artifacts explicitly.
    """

    canonical_rules: Mapping[str, FrozenValue]
    candidate_placements: Mapping[str, FrozenValue]
    facility_templates: Mapping[str, FrozenValue]
    instance_to_facility_type: Mapping[str, FrozenValue]
    artifact_hashes: Mapping[str, str]
    digest: str

    def __init__(
        self,
        *,
        canonical_rules: Mapping[str, object],
        candidate_placements: Mapping[str, object],
        facility_templates: Mapping[str, object],
        instance_to_facility_type: Mapping[str, object],
        artifact_hashes: Mapping[str, str] | None = None,
    ) -> None:
        # JSON-native validation happens inside the single freeze traversal so
        # each node is visited exactly once (validate-then-freeze in two passes
        # leaves a TOCTOU window on mutable inputs; B4 dual-review codex#0).
        raw_artifact_hashes: object = {} if artifact_hashes is None else artifact_hashes
        frozen_canonical_rules = _freeze_top_level_mapping(canonical_rules, field_name="canonical_rules")
        frozen_candidate_placements = _freeze_top_level_mapping(
            candidate_placements,
            field_name="candidate_placements",
        )
        frozen_facility_templates = _freeze_top_level_mapping(
            facility_templates,
            field_name="facility_templates",
        )
        frozen_instance_mapping = _freeze_top_level_mapping(
            instance_to_facility_type,
            field_name="instance_to_facility_type",
        )
        frozen_hashes = _freeze_artifact_hashes(raw_artifact_hashes)
        digest = _bundle_digest(
            canonical_rules=frozen_canonical_rules,
            candidate_placements=frozen_candidate_placements,
            facility_templates=frozen_facility_templates,
            instance_to_facility_type=frozen_instance_mapping,
            artifact_hashes=frozen_hashes,
        )
        object.__setattr__(self, "canonical_rules", frozen_canonical_rules)
        object.__setattr__(self, "candidate_placements", frozen_candidate_placements)
        object.__setattr__(self, "facility_templates", frozen_facility_templates)
        object.__setattr__(self, "instance_to_facility_type", frozen_instance_mapping)
        object.__setattr__(self, "artifact_hashes", frozen_hashes)
        object.__setattr__(self, "digest", digest)


def _freeze(value: object, *, path: str) -> FrozenValue:
    """Validate one exact JSON-native node and freeze it in the same visit.

    Validation and freezing are deliberately a single traversal: each node is
    read exactly once, so a concurrent mutation between "validated" and
    "frozen" cannot smuggle a non-JSON container into the bundle, and the
    admitted domain is exactly JSON-native (dict/list/str/int/float/bool/None
    — no tuple, set, or non-dict Mapping).
    """

    if value is None or type(value) in (bool, int, str):
        return cast(FrozenScalar, value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        frozen: dict[str, FrozenValue] = {}
        for key, item in mapping.items():
            if type(key) is not str:
                raise TypeError(f"{path} contains a mapping key that is not an exact str")
            frozen[key] = _freeze(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    if type(value) is list:
        sequence = cast(list[object], value)
        return tuple(_freeze(item, path=f"{path}[{index}]") for index, item in enumerate(sequence))
    raise TypeError(f"{path} contains value outside the exact JSON-native domain: {type(value).__name__}")


def _freeze_top_level_mapping(value: object, *, field_name: str) -> Mapping[str, FrozenValue]:
    if type(value) is not dict:
        raise TypeError(f"{field_name} must be an exact dict")
    frozen = _freeze(value, path=field_name)
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise AssertionError("top-level artifact freeze did not produce a mapping")
    return frozen


def _freeze_artifact_hashes(value: object) -> Mapping[str, str]:
    if type(value) is not dict:
        raise TypeError("artifact_hashes must be an exact dict")
    frozen: dict[str, str] = {}
    for key, digest in value.items():
        if type(key) is not str or type(digest) is not str:
            raise TypeError("artifact_hashes must map exact str keys to exact str values")
        frozen[key] = digest
    return MappingProxyType(frozen)


def _canonical_node(value: FrozenValue | Mapping[str, str]) -> object:
    """Return a type-tagged JSON value with deterministic mapping/set order."""

    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        if not math.isfinite(value):  # Defensive if this helper is reused directly.
            raise ValueError("bundle digest projection contains a non-finite number")
        return ["float", value]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, Mapping):
        return ["mapping", [[key, _canonical_node(value[key])] for key in sorted(value)]]
    if isinstance(value, tuple):
        return ["sequence", [_canonical_node(item) for item in value]]
    if isinstance(value, frozenset):
        nodes = [_canonical_node(item) for item in value]
        nodes.sort(key=_canonical_json_bytes)
        return ["set", nodes]
    raise TypeError(f"unsupported frozen value type {type(value).__name__}")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _bundle_digest(
    *,
    canonical_rules: Mapping[str, FrozenValue],
    candidate_placements: Mapping[str, FrozenValue],
    facility_templates: Mapping[str, FrozenValue],
    instance_to_facility_type: Mapping[str, FrozenValue],
    artifact_hashes: Mapping[str, str],
) -> str:
    projection: dict[str, object] = {
        "artifact_hashes": _canonical_node(artifact_hashes),
        "candidate_placements": _canonical_node(candidate_placements),
        "canonical_rules": _canonical_node(canonical_rules),
        "facility_templates": _canonical_node(facility_templates),
        "instance_to_facility_type": _canonical_node(instance_to_facility_type),
        "schema": "frozen-artifact-bundle-v1",
    }
    return hashlib.sha256(_BUNDLE_DIGEST_PREFIX + _canonical_json_bytes(projection)).hexdigest()


def build_frozen_artifact_bundle(
    *,
    canonical_rules: Mapping[str, object],
    candidate_placements: Mapping[str, object],
    facility_templates: Mapping[str, object],
    instance_to_facility_type: Mapping[str, object],
    artifact_hashes: Mapping[str, str] | None = None,
) -> FrozenArtifactBundle:
    """Build one immutable bundle from four explicitly supplied artifacts.

    ``artifact_hashes`` may be omitted when no external digest set exists.
    Requiring each artifact as a keyword keeps the identity source explicit and
    prevents an ambient mutable state object from becoming a second input path.
    """

    return FrozenArtifactBundle(
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
        artifact_hashes=artifact_hashes,
    )


__all__ = [
    "FrozenArtifactBundle",
    "FrozenValue",
    "build_frozen_artifact_bundle",
]
