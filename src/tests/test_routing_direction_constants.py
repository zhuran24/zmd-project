"""Anti-drift pin for routing direction constants.
Status: ACCEPTED_DRAFT

routing_subproblem 的方向常量是路由编码的坐标系语义锚（N = +y）。
src/cuts/ helpers 存在已知的 N/S 方向反转雷（文件自注，未接入生产）；这组测试
把 certified 路由侧的方向语义钉死为精确值，防止将来任何"顺手统一"把反转语义
渗透进来。若确需改动，必须是有意的语义决策并同步更新本测试。
"""

from src.models.routing_subproblem import DIR_DELTA, DIR_OPP, DIRECTIONS


def test_directions_exact_values_and_order() -> None:
    """方向列表精确钉死（含顺序——顺序参与模型构建的确定性）。"""
    assert DIRECTIONS == ["N", "S", "E", "W"]


def test_dir_delta_exact_values() -> None:
    """N=+y / S=-y / E=+x / W=-x 的 y-up 坐标语义精确钉死。"""
    assert DIR_DELTA == {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def test_dir_opp_exact_values() -> None:
    assert DIR_OPP == {"N": "S", "S": "N", "E": "W", "W": "E"}


def test_direction_tables_share_exact_key_set() -> None:
    assert set(DIR_DELTA) == set(DIRECTIONS)
    assert set(DIR_OPP) == set(DIRECTIONS)


def test_dir_opp_is_involution_and_negates_delta() -> None:
    """结构一致性：opp 是对合，且 delta(opp(d)) == -delta(d)。"""
    for direction in DIRECTIONS:
        assert DIR_OPP[DIR_OPP[direction]] == direction
        dx, dy = DIR_DELTA[direction]
        assert DIR_DELTA[DIR_OPP[direction]] == (-dx, -dy)


def test_dir_delta_unit_steps_are_distinct() -> None:
    deltas = [DIR_DELTA[direction] for direction in DIRECTIONS]
    assert len(set(deltas)) == 4
    for dx, dy in deltas:
        assert abs(dx) + abs(dy) == 1
