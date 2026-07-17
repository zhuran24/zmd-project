"""Path 17 D2 — Commodity cell-flow core (production integration).

GPT v7 Candidate D 完整版数学描述. D2 在给定 master OPTIMAL layout + binding selected
port_specs 下, 跑 full-grid commodity-cell flow CP-SAT 子问题:

- `u[k, c]` BoolVar: commodity k 是否用 cell c
- `e[k, arc]` BoolVar: commodity k 是否走 directed arc (c1 → c2)
- capacity: sum_k u[k, c] ≤ 1 per cell (each cell at most 1 commodity in ground layer)
- channeling: e[k, (c1, c2)] => u[k, c1] AND u[k, c2]
- flow conservation: out_flow(k, c) - in_flow(k, c) == terminal_balance(k, c)
  - output port front cell: +1 per port (source)
  - input port front cell: -1 per port (sink)
- per-owner assumption literals control port adherence (force u[k, front_cell] = 1)
  → INFEASIBLE 抽 SufficientAssumptionsForInfeasibility 拿 minimal owner core
  → 反馈 master no-good cut

soundness: given binding-selected port_specs, if D2 model INFEASIBLE under assumption
subset S, any master layout that triggers same (instance_id, pose_idx) ∈ S subset will
also be C2-INFEASIBLE — sound combinatorial Benders cut.

Phase 0b 实测: 7/7 eligible anchor INFEASIBLE in 0.05-0.15s. Phase 1 task: production
class with assumption literals + extract_core for master cut.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model

from src.models.cp_sat_worker_config import (
    DEFAULT_ROUTING_CP_SAT_WORKERS,
    apply_subproblem_memory_cap,
    resolve_cp_sat_worker_count,
)

GRID_W = 70
GRID_H = 70
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


@dataclass(frozen=True)
class D2PoseAssumption:
    """Per-owner assumption literal for D2 model.

    instance_id: master owner.
    pose_idx: which pose master picked.
    assumption_name: CP-SAT BoolVar name for UNSAT-core extraction.
    """
    instance_id: str
    pose_idx: int
    assumption_name: str


@dataclass
class D2CoreResult:
    """Outcome of D2 solve."""
    status: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    wall_s: float
    u_vars_count: int
    e_vars_count: int
    constraints_count: int
    blocked_port_count: int
    forced_port_count: int
    core: List[D2PoseAssumption] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class D2CommodityFlowCore:
    """D2 model: full-grid commodity-cell flow CP-SAT with assumption-keyed port adherence."""

    def __init__(
        self,
        *,
        occupied_cells: Iterable[Tuple[int, int]],
        port_specs: Sequence[Mapping[str, Any]],
        pose_assumptions: Sequence[D2PoseAssumption],
    ):
        self.occupied_cells: Set[Tuple[int, int]] = {
            (int(x), int(y)) for x, y in occupied_cells
        }
        self.port_specs: List[Dict[str, Any]] = [dict(ps) for ps in port_specs]
        self.pose_assumptions: List[D2PoseAssumption] = list(pose_assumptions)

        self.model = cp_model.CpModel()
        self._u_vars: Dict[Tuple[str, int, int], Any] = {}
        self._e_vars: Dict[Tuple[str, int, int, int, int], Any] = {}
        self._assumption_vars: Dict[str, Any] = {}
        self._free_cells: Set[Tuple[int, int]] = set()
        self._commodities: List[str] = []
        self._blocked_port_count = 0
        self._forced_port_count = 0
        self._build_stats: Dict[str, Any] = {}

        self._solver: Optional[cp_model.CpSolver] = None
        self._status: Optional[int] = None

    def build(self) -> None:
        t0 = time.perf_counter()

        # free cells = grid - occupied
        self._free_cells = {
            (x, y)
            for x in range(GRID_W)
            for y in range(GRID_H)
            if (x, y) not in self.occupied_cells
        }
        self._commodities = sorted({str(ps["commodity"]) for ps in self.port_specs})

        # u[k, c] BoolVar
        for k in self._commodities:
            for (x, y) in self._free_cells:
                self._u_vars[(k, x, y)] = self.model.NewBoolVar(f"d2_u_{k}_{x}_{y}")

        # e[k, (c1, c2)] BoolVar — directed arc within free cells
        for k in self._commodities:
            for (x, y) in self._free_cells:
                for _d, (dx, dy) in DIR_DELTA.items():
                    nx, ny = x + dx, y + dy
                    if (nx, ny) not in self._free_cells:
                        continue
                    self._e_vars[(k, x, y, nx, ny)] = self.model.NewBoolVar(
                        f"d2_e_{k}_{x}_{y}_{nx}_{ny}"
                    )

        # capacity: sum_k u[k, c] ≤ 1 per cell
        # 生产 routing 已允许混流,本模型语义滞后,仅作 precheck 确证后的 core 缩小器
        for (x, y) in self._free_cells:
            cell_u_vars = [self._u_vars[(k, x, y)] for k in self._commodities]
            if cell_u_vars:
                self.model.AddAtMostOne(cell_u_vars)

        # channeling: e[k, (c1, c2)] => u[k, c1] AND u[k, c2]
        for (k, x1, y1, x2, y2), e_var in self._e_vars.items():
            self.model.AddImplication(e_var, self._u_vars[(k, x1, y1)])
            self.model.AddImplication(e_var, self._u_vars[(k, x2, y2)])

        # assumption literals per-owner
        for pa in self.pose_assumptions:
            self._assumption_vars[pa.assumption_name] = self.model.NewBoolVar(pa.assumption_name)

        # Map instance_id → assumption literals
        assumption_by_instance: Dict[str, List[Any]] = defaultdict(list)
        for pa in self.pose_assumptions:
            v = self._assumption_vars.get(pa.assumption_name)
            if v is not None:
                assumption_by_instance[pa.instance_id].append(v)

        # Compute conditional terminal contributions per (commodity, cell):
        # - output port at c contributes +1 net out_flow IFF owner assumption True
        # - input port at c contributes -1 net out_flow (=+1 net in) IFF owner assumption True
        # Also force u[k, front_cell] = 1 conditional on owner assumption.
        output_av_by_kc: Dict[Tuple[str, int, int], List[Any]] = defaultdict(list)
        input_av_by_kc: Dict[Tuple[str, int, int], List[Any]] = defaultdict(list)
        unconditional_balance: Dict[Tuple[str, int, int], int] = defaultdict(int)
        for ps in self.port_specs:
            px, py = int(ps["x"]), int(ps["y"])
            commodity = str(ps.get("commodity", ""))
            port_type = str(ps.get("type", ""))
            owner_id = str(ps.get("instance_id", ""))
            if commodity not in self._commodities:
                continue
            # identity 语义: stored 口坐标即带子格(front), 不 +delta
            # (front 错位事故批 2; DIR_DELTA 仅保留 :121 的带邻格步进用途).
            fx, fy = px, py
            if (fx, fy) not in self._free_cells:
                self._blocked_port_count += 1
                continue
            owner_assumptions = assumption_by_instance.get(owner_id, [])
            u_var = self._u_vars.get((commodity, fx, fy))
            if owner_assumptions:
                av = owner_assumptions[0]
                if port_type == "out":
                    output_av_by_kc[(commodity, fx, fy)].append(av)
                elif port_type == "in":
                    input_av_by_kc[(commodity, fx, fy)].append(av)
                else:
                    continue
                if u_var is not None:
                    self.model.Add(u_var == 1).OnlyEnforceIf(av)
            else:
                # Owner without assumption — unconditional contribution (rare; here for safety)
                if port_type == "out":
                    unconditional_balance[(commodity, fx, fy)] += 1
                elif port_type == "in":
                    unconditional_balance[(commodity, fx, fy)] -= 1
                else:
                    continue
                if u_var is not None:
                    self.model.Add(u_var == 1)
            self._forced_port_count += 1

        # flow conservation per (commodity, cell): out_flow - in_flow == terminal_balance
        # where terminal_balance = sum(+output_av) - sum(+input_av) + unconditional_balance
        out_arcs_by_kc: Dict[Tuple[str, int, int], List[Any]] = defaultdict(list)
        in_arcs_by_kc: Dict[Tuple[str, int, int], List[Any]] = defaultdict(list)
        for (k, x1, y1, x2, y2), e_var in self._e_vars.items():
            out_arcs_by_kc[(k, x1, y1)].append(e_var)
            in_arcs_by_kc[(k, x2, y2)].append(e_var)

        for k in self._commodities:
            for (x, y) in self._free_cells:
                out_flow = sum(out_arcs_by_kc[(k, x, y)])
                in_flow = sum(in_arcs_by_kc[(k, x, y)])
                output_avs = output_av_by_kc.get((k, x, y), [])
                input_avs = input_av_by_kc.get((k, x, y), [])
                unconditional = unconditional_balance.get((k, x, y), 0)
                # out_flow - in_flow == sum(output_av) - sum(input_av) + unconditional
                # Move to LHS: out_flow - in_flow - sum(output_av) + sum(input_av) == unconditional
                lhs_terms: List[Any] = [out_flow, -in_flow]
                lhs_terms.extend([-av for av in output_avs])
                lhs_terms.extend([av for av in input_avs])
                self.model.Add(sum(lhs_terms) == unconditional)

        elapsed = time.perf_counter() - t0
        try:
            constraints_count = len(self.model.Proto().constraints)
        except Exception:
            constraints_count = -1
        self._build_stats = {
            "wall_build_s": round(elapsed, 3),
            "u_vars_count": len(self._u_vars),
            "e_vars_count": len(self._e_vars),
            "total_vars_count": len(self._u_vars) + len(self._e_vars),
            "constraints_count": constraints_count,
            "free_cells_count": len(self._free_cells),
            "commodities_count": len(self._commodities),
            "blocked_port_count": self._blocked_port_count,
            "forced_port_count": self._forced_port_count,
        }

    def solve(self, time_limit: float = 30.0) -> str:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_D2_CP_SAT_WORKERS",
            default=DEFAULT_ROUTING_CP_SAT_WORKERS,
        )
        apply_subproblem_memory_cap(solver)

        # mark assumption literals
        for _name, var in self._assumption_vars.items():
            self.model.AddAssumption(var)

        t0 = time.perf_counter()
        status = solver.Solve(self.model)
        elapsed = time.perf_counter() - t0
        self._solver = solver
        self._status = status
        self._build_stats["wall_solve_s"] = round(elapsed, 3)
        self._build_stats["solver_status"] = solver.StatusName(status)
        self._build_stats["branches"] = solver.NumBranches()
        self._build_stats["conflicts"] = solver.NumConflicts()

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return "FEASIBLE"
        if status == cp_model.INFEASIBLE:
            return "INFEASIBLE"
        return "UNKNOWN"

    def extract_core(self) -> List[D2PoseAssumption]:
        """On INFEASIBLE, return subset of pose_assumptions whose conjunction is sufficient."""
        if self._solver is None or self._status != cp_model.INFEASIBLE:
            return []
        try:
            core_var_indices = self._solver.SufficientAssumptionsForInfeasibility()
        except AttributeError:
            return list(self.pose_assumptions)
        if not core_var_indices:
            return []
        proto = self.model.Proto()
        index_to_name = {i: var.name for i, var in enumerate(proto.variables)}
        core_names = {index_to_name.get(abs(int(i))) for i in core_var_indices}
        result: List[D2PoseAssumption] = []
        for pa in self.pose_assumptions:
            if pa.assumption_name in core_names:
                result.append(pa)
        return result

    def build_result(self) -> D2CoreResult:
        status_str: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
        if self._status is None:
            status_str = "MODEL_INVALID"
        elif self._status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            status_str = "FEASIBLE"
        elif self._status == cp_model.INFEASIBLE:
            status_str = "INFEASIBLE"
        else:
            status_str = "UNKNOWN"
        core = self.extract_core() if status_str == "INFEASIBLE" else []
        return D2CoreResult(
            status=status_str,
            wall_s=float(self._build_stats.get("wall_solve_s", 0.0)),
            u_vars_count=int(self._build_stats.get("u_vars_count", 0)),
            e_vars_count=int(self._build_stats.get("e_vars_count", 0)),
            constraints_count=int(self._build_stats.get("constraints_count", 0)),
            blocked_port_count=int(self._build_stats.get("blocked_port_count", 0)),
            forced_port_count=int(self._build_stats.get("forced_port_count", 0)),
            core=core,
            stats=dict(self._build_stats),
        )


def solve_d2_commodity_flow(
    *,
    occupied_cells: Iterable[Tuple[int, int]],
    port_specs: Sequence[Mapping[str, Any]],
    pose_assumptions: Sequence[D2PoseAssumption],
    time_limit: float = 30.0,
) -> D2CoreResult:
    """Convenience wrapper: build + solve + return result."""
    core = D2CommodityFlowCore(
        occupied_cells=occupied_cells,
        port_specs=port_specs,
        pose_assumptions=pose_assumptions,
    )
    core.build()
    core.solve(time_limit=time_limit)
    return core.build_result()
