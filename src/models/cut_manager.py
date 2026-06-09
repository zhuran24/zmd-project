"""
Benders 切平面与反馈管理器 (Benders Cut Manager)
Status: ACCEPTED_DRAFT

目标：负责在 LBBD 架构下，接收子问题（宏观流/微观路由）发回的 Benders Cuts（切平面），
进行持久化存储、去重、以及在主问题每次求解前的热启动注入。
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RUN_STATUS_CERTIFIED = "CERTIFIED"
RUN_STATUS_INFEASIBLE = "INFEASIBLE"
RUN_STATUS_UNKNOWN = "UNKNOWN"
RUN_STATUS_UNPROVEN = "UNPROVEN"

CONDITION_REQUIRED_CERTIFIED_CUT_TYPES = frozenset({"power_subproblem_infeasible_nogood"})
CONDITION_REQUIRED_CERTIFIED_METADATA_KINDS = frozenset(
    {"power_subproblem_ghost_conditioned_nogood"}
)


def _optional_float(value: Any) -> Optional[float]:
    return None if value is None else float(value)


def _reject_duplicate_json_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _loads_strict_json_object(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )


def _strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return bool(value)


def _optional_bool(value: Any, field: str) -> Optional[bool]:
    if value is None:
        return None
    return _strict_bool(value, field)


def _strict_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _strict_int_mapping(value: Any, field: str) -> Dict[str, int]:
    mapping = _strict_mapping(value, field)
    return {str(k): _strict_int(v, f"{field}.{k}") for k, v in mapping.items()}


def _strict_dict(value: Any, field: str) -> Dict[str, Any]:
    mapping = _strict_mapping(value, field)
    return {str(k): v for k, v in mapping.items()}


def _strict_str_dict(value: Any, field: str) -> Dict[str, str]:
    mapping = _strict_mapping(value, field)
    return {str(k): str(v) for k, v in mapping.items()}


def _cut_requires_condition_set(cut_type: str, metadata: Mapping[str, Any]) -> bool:
    metadata_kind = metadata.get("kind")
    return (
        cut_type in CONDITION_REQUIRED_CERTIFIED_CUT_TYPES
        or str(metadata_kind) in CONDITION_REQUIRED_CERTIFIED_METADATA_KINDS
    )


def _validate_certified_condition_requirement(
    *,
    cut_type: str,
    source_mode: str,
    exact_safe: bool,
    metadata: Mapping[str, Any],
    condition_set: Mapping[str, Any],
) -> None:
    if (
        source_mode == "certified_exact"
        and exact_safe is True
        and _cut_requires_condition_set(cut_type, metadata)
        and not condition_set
    ):
        raise ValueError(f"condition_set is required for certified exact cut_type={cut_type}")


@dataclass
class BendersCut:
    """Structured cut record for exact-contract compatibility."""

    cut_type: str
    conflict_set: Dict[str, Any]
    iteration: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    source_mode: str = "exploratory"
    exact_safe: bool = False
    artifact_hashes: Dict[str, str] = field(default_factory=dict)
    proof_stage: Optional[str] = None
    binding_exhausted: Optional[bool] = None
    routing_exhausted: Optional[bool] = None
    proof_summary: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    epsilon_stage: Optional[float] = None
    # condition_set: cut 只在这些 literal 全为 1 时生效. {"ghost_anchor": rect_idx}
    # 用于 ghost-conditioned power cut, replay 时按 key 类型 lookup u_vars.
    condition_set: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        source_mode = str(self.source_mode)
        cut_type = str(self.cut_type)
        exact_safe = _strict_bool(self.exact_safe, "exact_safe")
        metadata = _strict_dict(self.metadata, "metadata")
        if source_mode == "certified_exact":
            conflict_set = _strict_int_mapping(self.conflict_set, "conflict_set")
            condition_set = _strict_int_mapping(self.condition_set, "condition_set")
        else:
            conflict_set = _strict_dict(self.conflict_set, "conflict_set")
            condition_set = _strict_dict(self.condition_set, "condition_set")
        _validate_certified_condition_requirement(
            cut_type=cut_type,
            source_mode=source_mode,
            exact_safe=exact_safe,
            metadata=metadata,
            condition_set=condition_set,
        )
        payload: Dict[str, Any] = {
            "schema_version": _strict_int(self.schema_version, "schema_version"),
            "cut_type": cut_type,
            "conflict_set": conflict_set,
            "iteration": _strict_int(self.iteration, "iteration"),
            "metadata": metadata,
            "source_mode": source_mode,
            "exact_safe": exact_safe,
            "artifact_hashes": _strict_str_dict(self.artifact_hashes, "artifact_hashes"),
            "proof_stage": self.proof_stage,
            "binding_exhausted": _optional_bool(self.binding_exhausted, "binding_exhausted"),
            "routing_exhausted": _optional_bool(self.routing_exhausted, "routing_exhausted"),
            "proof_summary": _strict_dict(self.proof_summary, "proof_summary"),
            "created_at": self.created_at,
            "epsilon_stage": self.epsilon_stage,
            "condition_set": condition_set,
        }
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BendersCut":
        source_mode = str(payload.get("source_mode", "exploratory"))
        cut_type = str(payload["cut_type"])
        exact_safe = _strict_bool(payload.get("exact_safe", False), "exact_safe")
        metadata = _strict_dict(payload.get("metadata", {}), "metadata")
        if source_mode == "certified_exact":
            conflict_set = _strict_int_mapping(payload.get("conflict_set", {}), "conflict_set")
            condition_set = _strict_int_mapping(payload.get("condition_set", {}), "condition_set")
        else:
            conflict_set = _strict_dict(payload.get("conflict_set", {}), "conflict_set")
            condition_set = _strict_dict(payload.get("condition_set", {}), "condition_set")
        _validate_certified_condition_requirement(
            cut_type=cut_type,
            source_mode=source_mode,
            exact_safe=exact_safe,
            metadata=metadata,
            condition_set=condition_set,
        )
        return cls(
            schema_version=_strict_int(payload.get("schema_version", 1), "schema_version"),
            cut_type=cut_type,
            conflict_set=conflict_set,
            iteration=_strict_int(payload.get("iteration", 0), "iteration"),
            metadata=metadata,
            source_mode=source_mode,
            exact_safe=exact_safe,
            artifact_hashes=_strict_str_dict(
                payload.get("artifact_hashes", {}), "artifact_hashes"
            ),
            proof_stage=(
                None if payload.get("proof_stage") is None else str(payload.get("proof_stage"))
            ),
            binding_exhausted=_optional_bool(payload.get("binding_exhausted"), "binding_exhausted"),
            routing_exhausted=_optional_bool(payload.get("routing_exhausted"), "routing_exhausted"),
            proof_summary=_strict_dict(payload.get("proof_summary", {}), "proof_summary"),
            created_at=(
                None if payload.get("created_at") is None else str(payload.get("created_at"))
            ),
            epsilon_stage=_optional_float(payload.get("epsilon_stage")),
            condition_set=condition_set,
        )


def summarize_port_balance(
    port_specs: Iterable[Mapping[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Count discrete in/out endpoints per commodity for the current routing model."""

    balance: Dict[str, Dict[str, int]] = defaultdict(lambda: {"in": 0, "out": 0})
    for spec in port_specs:
        commodity = str(spec.get("commodity", ""))
        port_type = str(spec.get("type", ""))
        if not commodity or port_type not in {"in", "out"}:
            continue
        balance[commodity][port_type] += 1
    return dict(balance)


def analyze_port_balance(
    port_specs: Iterable[Mapping[str, Any]],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Summarize dead-end commodities and split/merge pressure for one binding."""

    balance = summarize_port_balance(port_specs)
    dead_end: Dict[str, Dict[str, int]] = {}
    needs_splitter: Dict[str, Dict[str, int]] = {}
    needs_merger: Dict[str, Dict[str, int]] = {}

    for commodity, counts in balance.items():
        in_count = int(counts.get("in", 0))
        out_count = int(counts.get("out", 0))

        if (in_count == 0 and out_count > 0) or (out_count == 0 and in_count > 0):
            dead_end[commodity] = {"in": in_count, "out": out_count}
            continue
        if in_count > out_count:
            needs_splitter[commodity] = {
                "in": in_count,
                "out": out_count,
                "delta": in_count - out_count,
            }
        elif out_count > in_count:
            needs_merger[commodity] = {
                "in": in_count,
                "out": out_count,
                "delta": out_count - in_count,
            }

    return {
        "balance": balance,
        "dead_end": dead_end,
        "needs_splitter": needs_splitter,
        "needs_merger": needs_merger,
    }


class CutManager:
    """Compatibility manager for both runtime JSONL cuts and structured exact cuts."""

    def __init__(
        self,
        checkpoint_dir: Optional[Path] = None,
        *,
        solve_mode: str = "exploratory",
        current_hashes: Optional[Mapping[str, str]] = None,
    ):
        self.checkpoint_dir = checkpoint_dir or (PROJECT_ROOT / "data" / "checkpoints")
        self.solve_mode = str(solve_mode)
        self.current_hashes = (
            {str(k): str(v) for k, v in current_hashes.items()}
            if current_hashes is not None
            else {}
        )
        self.cuts_file = self.checkpoint_dir / "benders_cuts.jsonl"
        self.cuts: List[BendersCut] = []
        # (conflict_signature, condition_signature) — condition 也进 key 让
        # 同 conflict / 不同 condition 的 cut 不互相 dedup.
        self._cut_signatures: Set[Tuple[frozenset[Tuple[str, Any]], frozenset[Tuple[str, Any]]]] = set()
        self.active_cuts: Set[frozenset[Tuple[str, str]]] = set()

        self._ensure_dir()
        self.load_cuts()

    def _ensure_dir(self) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        if not self.cuts_file.exists():
            self.cuts_file.touch()

    def _clear_structured_registry(self) -> None:
        self.cuts.clear()
        self._cut_signatures.clear()
        self.active_cuts.clear()

    def _runtime_signature(
        self,
        conflict_set: Iterable[Mapping[str, Any]],
    ) -> frozenset[Tuple[str, str]]:
        return frozenset(
            sorted(
                (
                    str(item["instance_id"]),
                    str(item["pose_id"]),
                )
                for item in conflict_set
            )
        )

    def _structured_signature(
        self, cut: BendersCut
    ) -> Tuple[frozenset[Tuple[str, Any]], frozenset[Tuple[str, Any]]]:
        conflict = frozenset(sorted((str(k), v) for k, v in cut.conflict_set.items()))
        # condition 进 dedup key — 否则 "ghost A 下禁 X" 跟 "ghost B 下禁 X"
        # 被当同一条吞掉, 失去 conditioned 表达力.
        condition = frozenset(
            sorted((str(k), v) for k, v in cut.condition_set.items())
        )
        return (conflict, condition)

    def load_cuts(self) -> None:
        """Load runtime JSONL cuts accumulated by the flow-based loop."""

        self.active_cuts.clear()
        if not self.cuts_file.exists():
            return

        with self.cuts_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = _loads_strict_json_object(line)
                    conflict_set = payload.get("conflict_set", [])
                    if not isinstance(conflict_set, list):
                        continue
                    self.active_cuts.add(self._runtime_signature(conflict_set))
                except Exception as exc:
                    print(f"[WARN] 加载 Benders Cut 失败: {exc}")

    def load(self, path: Path) -> Dict[str, int]:
        """Load structured cut artifacts with exact-contract filtering."""

        stats: Dict[str, int] = {
            "loaded": 0,
            "rejected_legacy": 0,
            "rejected_hash": 0,
            "rejected_not_exact_safe": 0,
            "rejected_mode": 0,
            "deduped": 0,
        }
        self._clear_structured_registry()

        if not path.exists():
            return stats

        payload = _loads_strict_json_object(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            stats["rejected_legacy"] = len(payload)
            return stats
        if not isinstance(payload, Mapping):
            stats["rejected_legacy"] = 1
            return stats

        raw_cuts = payload.get("cuts", [])
        if not isinstance(raw_cuts, list):
            stats["rejected_legacy"] = 1
            return stats

        for raw_cut in raw_cuts:
            if not isinstance(raw_cut, Mapping):
                stats["rejected_legacy"] += 1
                continue

            try:
                cut = BendersCut.from_dict(raw_cut)
            except Exception:
                stats["rejected_legacy"] += 1
                continue

            if self.solve_mode == "certified_exact":
                if cut.source_mode != "certified_exact":
                    stats["rejected_mode"] += 1
                    continue
                if cut.exact_safe is not True:
                    stats["rejected_not_exact_safe"] += 1
                    continue
                if self.current_hashes and cut.artifact_hashes != self.current_hashes:
                    stats["rejected_hash"] += 1
                    continue

            signature = self._structured_signature(cut)
            if signature in self._cut_signatures:
                stats["deduped"] += 1
                continue

            self._cut_signatures.add(signature)
            self.cuts.append(cut)
            self.active_cuts.add(
                frozenset((str(instance_id), str(pose_idx)) for instance_id, pose_idx in cut.conflict_set.items())
            )
            stats["loaded"] += 1

        return stats

    def register_structured_cut(self, cut: BendersCut) -> bool:
        """Register one structured exact/exploratory cut in memory with deduplication."""

        signature = self._structured_signature(cut)
        if signature in self._cut_signatures:
            return False

        self._cut_signatures.add(signature)
        self.cuts.append(cut)
        return True

    def has_structured_cut(self, cut: BendersCut) -> bool:
        """Return whether an equivalent structured cut is already registered."""

        return self._structured_signature(cut) in self._cut_signatures

    def add_cut(self, conflict_set: List[Dict[str, str]], reason: str, source: str) -> bool:
        """Add one runtime cut record while preserving existing JSONL compatibility."""

        frozen_conflict = self._runtime_signature(conflict_set)
        if frozen_conflict in self.active_cuts:
            return False

        self.active_cuts.add(frozen_conflict)
        cut_record = {
            "source": source,
            "reason": reason,
            "conflict_set": conflict_set,
        }
        with self.cuts_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(cut_record, ensure_ascii=False) + "\n")
        return True

    def get_all_cuts(self) -> List[List[Tuple[str, str]]]:
        """Return all runtime cuts in a stable tuple-list format for the master model."""

        return [sorted(list(cut)) for cut in self.active_cuts]

    def cuts_for_stage(self, target_epsilon: float) -> List[BendersCut]:
        """P1 #7b prep: 返回 ε-阶段 reuse 兼容的 cuts.

        规则: 更松 ε 推出的 cut 在更紧 ε 阶段仍合法 (ε=0.05 cut 在 ε=0.01
        和 ε=0.0 都可用; 反向不行, ε=0.0 的 cut 不能 reuse 在更松阶段).

        target_epsilon: 当前 wave 的 ε 目标 (0.05 / 0.01 / 0.0).
        epsilon_stage=None 的 cut 视为"任何阶段都安全" (legacy/pre-ε 的
        hard nogood, 因为它们不依赖 ε bound 推出).

        集成到 master build 是 P1 #7 主体阶段; 这里只 prep helper.
        """
        target = float(target_epsilon)
        return [
            cut for cut in self.cuts
            if cut.epsilon_stage is None or float(cut.epsilon_stage) >= target
        ]

    def clear_all(self) -> None:
        """Dangerous helper used only when all historical cuts must be invalidated."""

        self._clear_structured_registry()
        if self.cuts_file.exists():
            self.cuts_file.unlink()
        self.cuts_file.touch()
