"""FlowSubproblem smoke tests (audit B 给的技术债, 0 字节空文件 → 加 6 条 smoke).

FlowSubproblem 是 continuous multi-commodity LP (GLOP), exact 模式只 diagnostic
不参与 cut 决策, 所以 audit B 标"非 168h blocker". 但加 smoke test 防回归
(import 挂 / 类签名漂移 / diagnostic warning 字段消失).
"""

from __future__ import annotations

from src.models.flow_subproblem import (
    FlowNetwork,
    FlowSubproblem,
    cell_id,
)


def test_flow_network_basic_add():
    """FlowNetwork add_node / add_edge / get_capacity 基础 API."""
    network = FlowNetwork()
    network.add_node("a")
    network.add_node("b")
    network.add_edge("a", "b", capacity=10.0)
    assert "a" in network.nodes
    assert "b" in network.nodes
    assert network.get_capacity("a", "b") == 10.0


def test_flow_subproblem_diagnostic_warning_exact():
    """exact 模式下 diagnostic.warning 应明示 'not a pruning oracle'.

    audit B finding: flow 在 exact 模式严格只 diagnostic, 不参与 INFEASIBLE 判定,
    不直接生 cut. warning 字符串是 contract 一部分, 不能改坏.
    """
    network = FlowNetwork()
    network.add_node("S_a")
    network.add_node("T_a")
    network.add_edge("S_a", "T_a", capacity=1.0)

    sub = FlowSubproblem(network, {"a": 1.0}, solve_mode="certified_exact")
    assert sub.solve_mode == "certified_exact"
    assert "diagnostic" in sub.diagnostics["warning"].lower()
    assert "not a pruning oracle" in sub.diagnostics["warning"]


def test_flow_subproblem_diagnostic_warning_exploratory():
    """exploratory 模式下 warning 不同 (Exploratory accelerator only)."""
    network = FlowNetwork()
    network.add_node("S_x")
    network.add_node("T_x")
    network.add_edge("S_x", "T_x", capacity=1.0)

    sub = FlowSubproblem(network, {"x": 1.0}, solve_mode="exploratory")
    assert "exploratory" in sub.diagnostics["warning"].lower()


def test_flow_trivial_feasible_returns_optimal():
    """1 source → 1 sink, demand 1, capacity 1 → OPTIMAL."""
    network = FlowNetwork()
    network.add_node("S_c")
    network.add_node("T_c")
    network.add_edge("S_c", "T_c", capacity=1.0)
    sub = FlowSubproblem(network, {"c": 1.0}, solve_mode="certified_exact")
    status = sub.build_and_solve(time_limit_ms=5000)
    assert status in ("OPTIMAL", "FEASIBLE"), f"trivial feasible → unexpected {status}"


def test_flow_missing_sink_edge_early_infeasible():
    """commodity 有 demand 但无 T_<c> 入边 → early INFEASIBLE + early_infeasible 字段."""
    network = FlowNetwork()
    network.add_node("S_d")
    network.add_node("T_d")
    network.add_node("middle")
    # 只有 S_d 出边到 middle, 没 T_d 入边
    network.add_edge("S_d", "middle", capacity=1.0)

    sub = FlowSubproblem(network, {"d": 1.0}, solve_mode="certified_exact")
    status = sub.build_and_solve(time_limit_ms=5000)
    assert status == "INFEASIBLE"
    assert "early_infeasible" in sub.diagnostics
    assert "missing_sink_edges" in sub.diagnostics["early_infeasible"]


def test_cell_id_format_stable():
    """cell_id(x, y) 返回字符串格式稳定 (其他模块依赖此约定)."""
    assert isinstance(cell_id(0, 0), str)
    assert cell_id(3, 5) != cell_id(5, 3)  # 顺序敏感
