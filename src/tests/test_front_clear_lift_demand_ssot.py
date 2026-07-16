"""front-clear 上收批：demand SSOT 哨兵（doc 04 v2 §3.4，任务 4）。

钉死三件事：
1. routing_visible_port_demands 的逐 op 数值 == 对抗审查席独立实算表
   （wf_d123bca7 encoding-codex F5——由 OPERATION_PORT_PROFILES 与
   generic_io_requirements 手推，非源码自证）；
2. demand 是 demand(op, snapshot) 非纯 op 常量（RFSC snapshot 依赖）；
3. 排除规则单一真相源反漂移——filter 与 extract_port_specs 两个消费点
   必须经 is_routing_visible_output_commodity，禁止回退内联
   `not in self.routing_free_sink_commodities`（口径漂移 = lift 超杀方向）。
"""

from __future__ import annotations

import inspect

import pytest

from src.models.binding_subproblem import PortBindingModel
from src.models.port_binding import (
    is_routing_visible_output_commodity,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

# 生产 RFSC 集（generic_io_requirements.json required_generic_inputs>0 派生）
_PROD_RFSC = frozenset({"qiaoyu_capsule", "valley_battery"})

# 对抗审查席独立实算表（req_in, vis_out）@ _PROD_RFSC——外部对照，别改成
# 从 helper 生成（那样测试退化为自证）。
_EXPECTED_DEMANDS = {
    "crusher_blue_iron": (1, 1),
    "crusher_buckwheat": (1, 2),
    "crusher_sandleaf": (1, 3),
    "crusher_source": (1, 1),
    "molding_bottle": (2, 1),
    "parts_maker": (1, 1),
    "refinery_blue_iron": (1, 1),
    "refinery_steel": (1, 1),
    "planter_buckwheat": (1, 1),
    "planter_sandleaf": (1, 1),
    "seed_collector_buckwheat": (1, 2),
    "seed_collector_sandleaf": (1, 2),
    "filling_capsule": (4, 0),
    "packaging_battery": (5, 0),
    "grinder_dense_blue_iron": (3, 1),
    "grinder_dense_source": (3, 1),
    "grinder_fine_buckwheat": (3, 1),
    # 零端口 op：in-scope 但零需求 → lift 不生成约束（doc 04 v2 §3.5）
    "power_supply": (0, 0),
}


def test_in_scope_op_set_is_exactly_the_expected_table() -> None:
    in_scope = {
        op
        for op in OPERATION_PORT_PROFILES
        if supports_exact_pose_level_binding(op)
    }
    assert in_scope == set(_EXPECTED_DEMANDS)


@pytest.mark.parametrize("op", sorted(_EXPECTED_DEMANDS))
def test_demand_matches_independent_recount(op: str) -> None:
    assert routing_visible_port_demands(op, _PROD_RFSC) == _EXPECTED_DEMANDS[op]


def test_demand_depends_on_rfsc_snapshot_not_op_alone() -> None:
    # RFSC 空 ⟹ filling_capsule 的 qiaoyu_capsule 输出变 routing-visible
    assert routing_visible_port_demands("filling_capsule", _PROD_RFSC) == (4, 0)
    assert routing_visible_port_demands("filling_capsule", frozenset()) == (4, 1)
    assert routing_visible_port_demands("packaging_battery", frozenset()) == (5, 1)


@pytest.mark.parametrize("op", ["boundary_io", "protocol_core", "wireless_sink"])
def test_generic_slot_op_raises_fail_closed(op: str) -> None:
    assert not supports_exact_pose_level_binding(op)
    with pytest.raises(ValueError, match="generic hub slots"):
        routing_visible_port_demands(op, _PROD_RFSC)


def test_visibility_predicate_is_str_strict() -> None:
    # 镜像 filter/extract_port_specs 的 str(port["commodity"]) 取值口径
    assert not is_routing_visible_output_commodity("qiaoyu_capsule", _PROD_RFSC)
    assert is_routing_visible_output_commodity("blue_iron_ingot", _PROD_RFSC)
    # 非 str 输入按 str() 归一后判定（与消费点行为一致）
    assert not is_routing_visible_output_commodity(5, frozenset({"5"}))


@pytest.mark.parametrize(
    "consumer_name",
    ["_filter_pose_binding_domain", "extract_port_specs"],
)
def test_consumers_route_through_ssot_predicate(consumer_name: str) -> None:
    """反漂移：两个消费点必须引用 SSOT 谓词，且不得回退内联排除规则。"""
    source = inspect.getsource(getattr(PortBindingModel, consumer_name))
    assert "is_routing_visible_output_commodity" in source
    # 任何 `... in self.routing_free_sink_commodities` 成员测试（含 not in）
    # 都是内联回退；SSOT 集合只允许作为谓词实参出现。
    for line in source.splitlines():
        assert " in self.routing_free_sink_commodities" not in line, line
