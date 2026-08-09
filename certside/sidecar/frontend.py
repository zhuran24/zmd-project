"""binding PB sidecar — 冻结工件解析前端（零 import 生产代码）.

从五个冻结工件独立重建 emitter 的 model_input（binding_sidecar_model_input_v1）：
- canonical_rules.json     → recipes/production_targets/commodity_metadata/globals
- preprocess_plan.json     → utility_operations（additive-only 检查）
- generic_io_requirements.json → required_generic_outputs/inputs
- candidate_placements.json    → facility_pools（pose 池，含 port cells）
- mandatory_exact_instances.json → instances（source_instances）

operation profile 独立重推（semantics_v1 §2）：
  recipe 型: input_rate(c) = inputs[c]/ticks_per_cycle（Fraction 精确，Decimal 输入）
             slots(c) = ceil(rate/belt_capacity)（(num+den-1)//den，无浮点）
  utility 型: generic_input/output_slots 直传（strict 非负 int）

placement_solution 由调用者提供（真实布局候选）。
与生产 OPERATION_PORT_PROFILES 的对拍见 parity_check.py。
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Mapping

from emitter import EmitterReject

PLAN_CANONICAL_OVERRIDE_KEYS = ("recipes", "production_targets", "commodity_roles")


# ---------------------------------------------------------------- strict JSON（exact-decimal 变体）
def strict_json_loads_exact(text: str) -> Any:
    """semantics_v1 §1 + float token → Decimal（精确词素，无二进制近似）."""

    def _pairs(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate JSON key: {k}")
            out[k] = v
        return out

    def _const(v):
        raise ValueError(f"invalid JSON constant: {v}")

    def _dec(v):
        d = Decimal(v)
        if not d.is_finite() or not math.isfinite(float(d)):
            raise ValueError(f"non-finite JSON number: {v}")
        return d

    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_const, parse_float=_dec)


def load_artifact(path: Path) -> tuple[Any, str]:
    """→ (payload, 全长 sha256)。字节级读取，hash 先于解析（对账键）."""
    raw = path.read_bytes()
    return strict_json_loads_exact(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- Fraction（semantics_v1 §2）
def to_fraction(value: Any, field: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise EmitterReject("INPUT_INVALID", "BAD_RATE_TYPE", field)
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise EmitterReject("INPUT_INVALID", "BAD_RATE_TYPE", f"{field}={type(value).__name__}")


def rate_to_slots(rate: Fraction, belt_capacity: Fraction) -> int:
    """精确 ceil(rate/capacity)；rate<=0 → 0（semantics_v1 §2 _rate_to_slots）."""
    if rate <= 0:
        return 0
    if belt_capacity <= 0:
        raise EmitterReject("INPUT_INVALID", "BAD_BELT_CAPACITY", str(belt_capacity))
    required = rate / belt_capacity
    return int((required.numerator + required.denominator - 1) // required.denominator)


def _strict_nonneg_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EmitterReject("INPUT_INVALID", "NON_INT_FIELD", field)
    if value < 0:
        raise EmitterReject("INPUT_INVALID", "NEGATIVE_FIELD", field)
    return int(value)


def _strict_pos_int(value: Any, field: str) -> int:
    v = _strict_nonneg_int(value, field)
    if v <= 0:
        raise EmitterReject("INPUT_INVALID", "NON_POSITIVE_FIELD", field)
    return v


# ---------------------------------------------------------------- profile 独立重推
def derive_operation_profiles(
    rules: Mapping[str, Any], plan: Mapping[str, Any]
) -> Dict[str, Dict[str, Any]]:
    for key in PLAN_CANONICAL_OVERRIDE_KEYS:
        if key in plan:
            raise EmitterReject("INPUT_INVALID", "PLAN_NOT_ADDITIVE", key)
    globals_ = dict(rules.get("globals") or {})
    logistics = dict(globals_.get("logistics") or {})
    belt = to_fraction(logistics.get("belt_capacity_per_tick", 1), "belt_capacity_per_tick")
    if belt <= 0:
        raise EmitterReject("INPUT_INVALID", "BAD_BELT_CAPACITY", str(belt))

    profiles: Dict[str, Dict[str, Any]] = {}
    for recipe_id, raw in sorted(dict(rules.get("recipes") or {}).items()):
        recipe = dict(raw or {})
        ticks = _strict_pos_int(recipe.get("ticks_per_cycle", 0), f"recipes.{recipe_id}.ticks_per_cycle")
        inputs = dict(recipe.get("inputs") or {})
        outputs = dict(recipe.get("outputs") or {})
        if not outputs:
            raise EmitterReject("INPUT_INVALID", "RECIPE_NO_OUTPUT", recipe_id)
        profiles[str(recipe_id)] = {
            "facility_type": str(recipe.get("template", "")).strip(),
            "input_slot_counts": {
                str(c): rate_to_slots(
                    to_fraction(v, f"recipes.{recipe_id}.inputs.{c}") / ticks, belt
                )
                for c, v in sorted(inputs.items())
            },
            "output_slot_counts": {
                str(c): rate_to_slots(
                    to_fraction(v, f"recipes.{recipe_id}.outputs.{c}") / ticks, belt
                )
                for c, v in sorted(outputs.items())
            },
            "generic_input_slots": 0,
            "generic_output_slots": 0,
        }
    for op, raw in sorted(dict(plan.get("utility_operations") or {}).items()):
        utility = dict(raw or {})
        profiles[str(op)] = {
            "facility_type": str(utility.get("facility_type", "")).strip(),
            "input_slot_counts": {},
            "output_slot_counts": {},
            "generic_input_slots": _strict_nonneg_int(
                utility.get("generic_input_slots", 0), f"utility.{op}.generic_input_slots"
            ),
            "generic_output_slots": _strict_nonneg_int(
                utility.get("generic_output_slots", 0), f"utility.{op}.generic_output_slots"
            ),
        }
    return profiles


# ---------------------------------------------------------------- model_input 组装
def build_model_input(
    project_root: Path,
    placement_solution: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """五工件 + 布局候选 → emitter 输入。附 artifact_hashes（全长 sha256，对账键）."""
    root = Path(project_root)
    rules, h_rules = load_artifact(root / "rules" / "canonical_rules.json")
    plan, h_plan = load_artifact(root / "rules" / "preprocess_plan.json")
    gio, h_gio = load_artifact(root / "data" / "preprocessed" / "generic_io_requirements.json")
    cand, h_cand = load_artifact(root / "data" / "preprocessed" / "candidate_placements.json")
    mand, h_mand = load_artifact(root / "data" / "preprocessed" / "mandatory_exact_instances.json")

    profiles = derive_operation_profiles(rules, plan)

    generic_input_slots_by_operation = {
        operation_type: int(profile["generic_input_slots"])
        for operation_type, profile in sorted(profiles.items())
        if int(profile["generic_input_slots"]) > 0
    }

    facility_pools = dict(cand.get("facility_pools") or {})
    if not facility_pools:
        raise EmitterReject("INPUT_INVALID", "MISSING_FACILITY_POOLS", "candidate_placements")
    if not isinstance(mand, list):
        raise EmitterReject("INPUT_INVALID", "BAD_INSTANCES_ARTIFACT", "mandatory_exact_instances")

    def _int_requirements(section: Any, name: str) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for c, v in dict(section or {}).items():
            out[str(c)] = _strict_nonneg_int(v, f"{name}.{c}")
        return out

    return {
        "schema": "binding_sidecar_model_input_v1",
        "placement_solution": {str(k): dict(v) for k, v in dict(placement_solution).items()},
        "facility_pools": facility_pools,
        "instances": [dict(i) for i in mand],
        "required_generic_outputs": _int_requirements(
            gio.get("required_generic_outputs"), "required_generic_outputs"
        ),
        "required_generic_inputs": _int_requirements(
            gio.get("required_generic_inputs"), "required_generic_inputs"
        ),
        "generic_input_slots_by_operation": generic_input_slots_by_operation,
        "commodity_metadata": dict(rules.get("commodity_metadata") or {}),
        "operation_profiles": profiles,
        "artifact_hashes": {
            "canonical_rules.json": h_rules,
            "preprocess_plan.json": h_plan,
            "generic_io_requirements.json": h_gio,
            "candidate_placements.json": h_cand,
            "mandatory_exact_instances.json": h_mand,
        },
    }
