"""P-HOM structural gate: orbit homogeneity digest (M4-D4, orbit-lift v2 §4 ①).

The F5 master translation is inherently orbit-level: presence literals range
over a whole mandatory group ("ANY slot of group g takes pose p"), so a
forbidden pattern learned from one instance combination silently applies to
every same-group permutation. That lift is sound ONLY while the group really
is homogeneous — every member identical except for its instance_id, no
per-instance keys hiding in profiles or pose pools. Theorem 2 of the design
names this premise P-HOM.

This module machine-checks the premise and condenses it into a digest that
rides the existing CutScope.artifact_hashes drift mechanism: the state
builder injects the digest into BState.artifact_hashes, the F5 oracle copies
it into the cut's scope, and step-6 attach/replay quarantines any cut whose
digest no longer matches the current state. A failed check (None) makes the
state builder refuse to attach anything at all — fail-closed, not degraded.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

ORBIT_HOMOGENEITY_DIGEST_KEY = "orbit_homogeneity_digest"


def compute_orbit_homogeneity_digest(
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Any],
) -> Optional[str]:
    """Return the P-HOM digest, or None when the premise fails (fail-closed).

    Three merged checks (design v2 §4 ①):
    1. mandatory homogeneity — within each (facility_type, operation_type)
       group, every instance record is identical once instance_id is removed;
    2. pose pools carry no per-instance dimension (a pose belongs to a
       template, never to one instance);
    3. operation port profiles are operation-level constants (snapshotted
       into the digest so a per-op change re-scopes every F5 cut).
    """
    groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for inst in instances or ():
        if not isinstance(inst, Mapping):
            return None
        key = (
            str(inst.get("facility_type", "")),
            str(inst.get("operation_type", "")),
        )
        stripped = {k: v for k, v in inst.items() if k != "instance_id"}
        try:
            canon = json.dumps(stripped, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            return None
        groups[key].append(canon)
    if not groups:
        return None
    group_snapshot: Dict[str, Any] = {}
    for (tpl, op), members in sorted(groups.items()):
        first = members[0]
        for other in members[1:]:
            if other != first:
                # Non-homogeneous group: lifting a pattern across its members
                # would generalise a verdict past what the oracle refuted.
                return None
        group_snapshot[f"{tpl}::{op}"] = {"count": len(members), "record": first}

    for tpl, pool in sorted((facility_pools or {}).items()):
        if not isinstance(pool, list):
            return None
        for pose in pool:
            if not isinstance(pose, Mapping):
                return None
            if "instance_id" in pose or "instance" in pose:
                # A pose bound to one instance breaks slot anonymity.
                return None

    profile_snapshot: Dict[str, Any] = {}
    for op, profile in sorted(OPERATION_PORT_PROFILES.items()):
        profile_snapshot[str(op)] = {
            "generic_input_slots": int(profile.generic_input_slots),
            "generic_output_slots": int(profile.generic_output_slots),
            "input_slots": sorted(
                (str(k), int(v)) for k, v in profile.input_slots.items()
            ),
            "output_slots": sorted(
                (str(k), int(v)) for k, v in profile.output_slots.items()
            ),
        }

    payload = json.dumps(
        {
            "schema": "orbit_homogeneity_v1",
            "groups": group_snapshot,
            "pools_have_no_instance_dimension": True,
            "operation_port_profiles": profile_snapshot,
        },
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
