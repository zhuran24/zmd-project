"""Campaign-local native conditional-owner extension for PortBindingModel.

This module keeps ordinary fixed owners on the unchanged native path. Registered
conditional owners are present before ``PortBindingModel.build()`` and receive an
explicit inactive pattern plus every native front-filtered active pattern.  It is
research-only and deliberately rejects conditional owners with generic slots.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.binding_subproblem import PortBindingModel  # noqa: E402
from src.models.port_binding import (  # noqa: E402
    enumerate_pose_level_port_bindings_with_cache_info,
    supports_exact_pose_level_binding,
)


class ConditionalOwnerPortBindingModel(PortBindingModel):
    """PortBindingModel with pre-registered conditional exact-binding owners."""

    def __init__(
        self,
        *,
        conditional_owner_metadata: Mapping[str, Mapping[str, Any]],
        **kwargs: Any,
    ) -> None:
        self._conditional_owner_metadata = {
            str(owner): dict(metadata)
            for owner, metadata in conditional_owner_metadata.items()
        }
        if not self._conditional_owner_metadata:
            raise ValueError("conditional_owner_metadata must not be empty")
        super().__init__(**kwargs)
        missing_placements = sorted(
            set(self._conditional_owner_metadata) - set(self.placement_solution)
        )
        missing_instances = sorted(
            set(self._conditional_owner_metadata) - set(self.instances_by_id)
        )
        if missing_placements or missing_instances:
            raise ValueError(
                "conditional owner registration drift: "
                f"missing_placements={missing_placements} "
                f"missing_instances={missing_instances}"
            )
        self.conditional_owner_domain_stats: list[dict[str, Any]] = []

    def _build_fixed_operation_domains(self) -> None:
        """Build ordinary owners natively, then conditional owners with inactive domains.

        The inactive pattern is created even when the active native domain is
        empty.  Consequently a statically impossible operation/footprint pair is
        represented as an inactive-only owner instead of disappearing from the
        assignment surface or making the whole binding model infeasible.
        """

        full_placement_solution = self.placement_solution
        outside_solution = {
            instance_id: row
            for instance_id, row in full_placement_solution.items()
            if instance_id not in self._conditional_owner_metadata
        }
        self.placement_solution = outside_solution
        try:
            super()._build_fixed_operation_domains()
        finally:
            self.placement_solution = full_placement_solution

        for owner_instance_id in sorted(self._conditional_owner_metadata):
            sol = self.placement_solution[owner_instance_id]
            inst = self._resolve_instance(owner_instance_id)
            if inst is None:
                raise RuntimeError(
                    f"conditional owner instance metadata missing: {owner_instance_id}"
                )
            operation_type = str(inst.get("operation_type", ""))
            if not operation_type or not supports_exact_pose_level_binding(
                operation_type
            ):
                raise RuntimeError(
                    "conditional owner lacks native exact pose binding: "
                    f"{owner_instance_id} operation={operation_type!r}"
                )
            facility_type = str(sol["facility_type"])
            pose_idx = int(sol["pose_idx"])
            pose = self._resolve_pose(facility_type, pose_idx)
            raw_domains, cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
                operation_type,
                pose,
            )
            if cache_hit:
                self.binding_domain_cache_hits += 1
                self.binding_domain_reused_instances.append(owner_instance_id)
            else:
                self.binding_domain_cache_misses += 1

            active_domains = list(raw_domains)
            raw_count = len(active_domains)
            if self.routing_context is not None and active_domains:
                active_domains = self._filter_pose_binding_domain(
                    active_domains,
                    owner_instance_id,
                )
                self.routing_aware_filter_stats["raw_patterns_total"] += raw_count
                self.routing_aware_filter_stats["filtered_patterns_total"] += len(
                    active_domains
                )
                self.routing_aware_filter_stats[
                    "front_blocked_patterns_pruned"
                ] += raw_count - len(active_domains)

            inactive_pattern = {
                "input_ports": [],
                "output_ports": [],
                "joint_inactive": True,
            }
            domains = [inactive_pattern, *active_domains]
            self.binding_domains[owner_instance_id] = domains
            self._conflict_summary["binding_domains"][owner_instance_id] = len(
                domains
            )
            vars_by_idx: dict[int, Any] = {}
            for domain_index in range(len(domains)):
                vars_by_idx[domain_index] = self.model.NewBoolVar(
                    f"bind_{owner_instance_id}_{domain_index}"
                )
            self.binding_vars[owner_instance_id] = vars_by_idx
            self.model.AddExactlyOne(list(vars_by_idx.values()))
            metadata = self._conditional_owner_metadata[owner_instance_id]
            self.conditional_owner_domain_stats.append(
                {
                    **metadata,
                    "virtual_owner": owner_instance_id,
                    "facility_type": facility_type,
                    "operation": operation_type,
                    "pose_idx": pose_idx,
                    "pose_id": str(pose.get("pose_id", "")),
                    "raw_pattern_count": raw_count,
                    "active_pattern_count": len(active_domains),
                    "domain_count_including_inactive": len(domains),
                    "inactive_only": not active_domains,
                }
            )

        self._conflict_summary["binding_domain_cache_hits"] = int(
            self.binding_domain_cache_hits
        )
        self._conflict_summary["binding_domain_cache_misses"] = int(
            self.binding_domain_cache_misses
        )
        self._conflict_summary["binding_domain_reused_instances"] = list(
            self.binding_domain_reused_instances
        )
        self._conflict_summary["conditional_owner_domain_stats"] = list(
            self.conditional_owner_domain_stats
        )

    def attach_activation_variables(
        self,
        *,
        prefix: str,
    ) -> tuple[
        dict[tuple[str, int, str], Any],
        dict[tuple[str, int, str, int], Any],
        list[dict[str, Any]],
    ]:
        """Expose assignment and active-pattern variables after native build."""

        y_vars: dict[tuple[str, int, str], Any] = {}
        z_vars: dict[tuple[str, int, str, int], Any] = {}
        stats: list[dict[str, Any]] = []
        for owner_instance_id in sorted(self._conditional_owner_metadata):
            metadata = self._conditional_owner_metadata[owner_instance_id]
            domain = self.binding_domains.get(owner_instance_id)
            vars_by_idx = self.binding_vars.get(owner_instance_id)
            if not domain or vars_by_idx is None:
                raise RuntimeError(
                    f"conditional owner native domain missing: {owner_instance_id}"
                )
            if not bool(domain[0].get("joint_inactive")):
                raise RuntimeError(
                    f"conditional owner inactive-pattern drift: {owner_instance_id}"
                )
            inactive = vars_by_idx.get(0)
            if inactive is None:
                raise RuntimeError(
                    f"conditional owner inactive literal missing: {owner_instance_id}"
                )
            block_id = str(metadata["block_id"])
            destination = int(metadata["destination"])
            operation = str(metadata["operation"])
            key = (block_id, destination, operation)
            y = self.model.NewBoolVar(f"{prefix}_active_{block_id}_{destination}_{operation}")
            self.model.Add(y + inactive == 1)
            y_vars[key] = y
            for domain_index in range(1, len(domain)):
                variable = vars_by_idx.get(domain_index)
                if variable is None:
                    raise RuntimeError(
                        "conditional owner active literal missing: "
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
