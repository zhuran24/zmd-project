"""Campaign-local conditional owner extension with an explicit pose-mode axis.

E039 introduced native conditional operation owners before PortBindingModel.build().
E041 keeps that exact domain-construction path and changes only the activation
surface: one body destination may expose several same-footprint pose modes, and
one operation is selected jointly with one mode.  It is research-only and retains
E039's fail-closed restriction against conditional generic-slot owners.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
BASE_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E039_native_conditional_owner_binding/conditional_owner_binding.py"
)

spec = importlib.util.spec_from_file_location("zmd_e041_e039_conditional", BASE_HELPER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot import {BASE_HELPER}")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)


class ConditionalModeOwnerPortBindingModel(
    base.ConditionalOwnerPortBindingModel
):
    """Expose native conditional owners as (body, mode, operation) choices."""

    def attach_mode_activation_variables(
        self,
        *,
        prefix: str,
    ) -> tuple[
        dict[tuple[str, int, int, str], Any],
        dict[tuple[str, int, int, str, int], Any],
        list[dict[str, Any]],
    ]:
        y_vars: dict[tuple[str, int, int, str], Any] = {}
        z_vars: dict[tuple[str, int, int, str, int], Any] = {}
        stats: list[dict[str, Any]] = []
        for owner_instance_id in sorted(self._conditional_owner_metadata):
            metadata = self._conditional_owner_metadata[owner_instance_id]
            domain = self.binding_domains.get(owner_instance_id)
            vars_by_idx = self.binding_vars.get(owner_instance_id)
            if not domain or vars_by_idx is None:
                raise RuntimeError(
                    f"conditional mode owner native domain missing: {owner_instance_id}"
                )
            if not bool(domain[0].get("joint_inactive")):
                raise RuntimeError(
                    f"conditional mode owner inactive-pattern drift: {owner_instance_id}"
                )
            inactive = vars_by_idx.get(0)
            if inactive is None:
                raise RuntimeError(
                    f"conditional mode owner inactive literal missing: {owner_instance_id}"
                )
            block_id = str(metadata["block_id"])
            destination = int(metadata["destination"])
            mode_index = int(metadata["mode_index"])
            operation = str(metadata["operation"])
            key = (block_id, destination, mode_index, operation)
            if key in y_vars:
                raise RuntimeError(f"duplicate conditional mode key: {key}")
            y = self.model.NewBoolVar(
                f"{prefix}_active_{block_id}_{destination}_{mode_index}_{operation}"
            )
            self.model.Add(y + inactive == 1)
            y_vars[key] = y
            for domain_index in range(1, len(domain)):
                variable = vars_by_idx.get(domain_index)
                if variable is None:
                    raise RuntimeError(
                        "conditional mode owner active literal missing: "
                        f"{owner_instance_id}/{domain_index}"
                    )
                z_vars[(*key, domain_index - 1)] = variable
            stats.append(
                {
                    **metadata,
                    "virtual_owner": owner_instance_id,
                    "domain_count_including_inactive": len(domain),
                    "active_pattern_count": len(domain) - 1,
                    "inactive_only": len(domain) == 1,
                }
            )
        return y_vars, z_vars, stats
