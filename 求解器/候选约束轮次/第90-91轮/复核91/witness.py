# -*- coding: utf-8 -*-
"""第 91 轮复核的具体见证（自写引擎 engine.py，逐判定复算）。

W1  关机源头：第 89 轮修正版（清单第 4 项）字面前提全满足、结论不成立。
    协议核心取货端口（设为蓝铁矿）→ 1 格传送带 → 精炼炉 Y（1 蓝铁矿→1 蓝铁块，1 tick）
    → 1 格传送带 → 粉碎机 X（1 蓝铁块→1 蓝铁粉末，1 tick）→ 2 格传送带 → 协议核心存货端口。
    调试期里两机正常运行，在任意时刻（这里取 11 tick，Y 的一批正做到一半）关掉 Y 的开关，留下进行中的一批；
    等下游排空后结束调试。此后 X 一直有供电状态、开着，却永远空手。
W2  相位：两条独立链的相位不同（开机差 1/2 tick、仓库恢复接收的时刻任意），
    循环态里 X 的来料落在两个相位上；X 的结论照样成立——共同相位前提既不必要，
    对这样的循环态也不成立。
W3  出口量词：Y 的另一条取货通道首格是每 5 tick 限 1 件的物品准入口，此刻接通的取货
    通道在每个闭合时刻都 ≤1=每批件数，X 仍周期性空手（四份都已把会重新接上的算进去，
    这是对照，说明这一前提不能省）。
"""
import json

from engine import Net


def run_to_cycle(net, t_trans, t_max, order_seed_list=None):
    import random
    rng = random.Random(0)
    order = net.build_order(rng) if order_seed_list is None else order_seed_list
    return net.run(rng, t_trans, t_max, adversarial=False, fixed_order=order), order


def w1():
    Q = 2
    net = Net(Q)
    ORE, BLOCK, POWDER = 'ore', 'block', 'powder'
    Y = net.add_machine({ORE: 1}, BLOCK, 1, 1, 1, tag='Y')
    X = net.add_machine({BLOCK: 1}, POWDER, 1, 1, 1, tag='X')
    cin = net.line(1, ('m', Y), item=ORE)
    net.sources.append((ORE, cin[0]))
    cyx = net.line(1, ('m', X), item=BLOCK)
    net.m_outch[Y].append(cyx[0])
    k = net.add_sink(lambda t: True, None)
    cxo = net.line(2, ('k', k), item=POWDER)
    # 核心端口在 t=1/2 tick 给出第一件，Y 于是在半 tick 相位上开批（步 3、5、7…）
    net.m_outch[X].append(cxo[0])
    t_off = 22  # 11 tick: Y 的批次在半 tick 相位上开始，这一刻它正做到一半
    net.power_events.append((t_off, Y, False))
    res, order = run_to_cycle(net, 200 * Q, 400 * Q)
    obs = res['obs']
    nm_Y = all(o[0][Y] for o in obs)
    nm_X = [o[0][X] for o in obs]
    out = {
        'period_steps': res['period'], 'Q': Q, 't_off_tick': t_off / Q,
        'Y_cache_state': net.m_cache[Y], 'Y_remaining_tick': net.m_rem[Y] / Q,
        'Y_inventory': net.m_inv[Y], 'Y_output_slot': net.m_out[Y],
        'Y_channels': len(net.m_outch[Y]), 'Y_k': net.m_k[Y],
        'line_Y_to_X': [net.c_item[c] for c in cyx],
        'X_inventory': net.m_inv[X], 'X_cache': net.m_cache[X], 'X_output_slot': net.m_out[X],
        'X_powered': net.m_pow[X],
        'Y_nonempty_every_closure': nm_Y, 'X_empty_every_closure': not any(nm_X),
        'delivered_to_core_before_static': net.k_count[k],
        # literal premises of the 89 revision (list item 4)
        'premise_X_single_recipe_legal': True,
        'premise_X_powered_on': all(o[6][X] for o in obs),
        'premise_dc_ge_a': 1 * 1 >= 1,
        'premise_source_single_1tick_recipe_product_i': True,
        'premise_source_never_empty_handed': nm_Y,
        'premise_source_output_slot_only_i': net.m_out[Y] == 0,
        'premise_source_all_channels_le_k': len(net.m_outch[Y]) <= net.m_k[Y],
        'premise_source_powered': all(o[6][Y] for o in obs),
    }
    return out


def w2(stop):
    """two chains from two ore ports feed one X that needs 2 of item A per batch over
    2 lines (塑形机的形状 2 钢块→1 钢质瓶，只看时刻，料名抽象)。
    stop=False：Y2 在 25.5 tick 才开机，两条来料相位不同；
    stop=True：另让 X 的收货端在 15—37.3 tick 停收，恢复时刻任意。"""
    Q = 10
    net = Net(Q)
    A = 'A'
    X = net.add_machine({A: 2}, 'P', 1, 1, 1, tag='X')
    Y1 = net.add_machine({'ore1': 1}, A, 1, 1, 1, tag='Y1')
    Y2 = net.add_machine({'ore2': 1}, A, 1, 1, 1, tag='Y2')
    for y, o in ((Y1, 'ore1'), (Y2, 'ore2')):
        c = net.line(2, ('m', y), item=o)
        net.sources.append((o, c[0]))
    l1 = net.line(3, ('m', X), item=A)
    net.m_outch[Y1].append(l1[0])
    l2 = net.line(2, ('m', X), item=A)
    net.m_outch[Y2].append(l2[0])
    T_stop, T_res = 150, 373

    def sched(t):
        return (not stop) or not (T_stop <= t < T_res)
    k = net.add_sink(sched, None)
    lo = net.line(2, ('k', k), item='P')
    net.m_outch[X].append(lo[0])
    net.m_pow[Y2] = False
    net.power_events.append((255, Y2, True))
    res, order = run_to_cycle(net, 60 * Q, 600 * Q)
    obs = res['obs']
    t1 = res['t1']
    ph_l1 = sorted({(t1 + 1 + i) % Q for i, o in enumerate(obs) if o[2][l1[-1]]})
    ph_l2 = sorted({(t1 + 1 + i) % Q for i, o in enumerate(obs) if o[2][l2[-1]]})
    ph_x = sorted({(t1 + 1 + i) % Q for i, o in enumerate(obs) if o[7][X]})
    ph_out = sorted({(t1 + 1 + i) % Q for i, o in enumerate(obs) if o[2][lo[0]]})
    return {
        'Q': Q, 'period_steps': res['period'], 'cycle_start_step': t1,
        'phases_line1_last_cell_receipts(1/Q)': ph_l1,
        'phases_line2_last_cell_receipts(1/Q)': ph_l2,
        'phases_X_batch_starts(1/Q)': ph_x,
        'phases_X_first_out_cell_receipts(1/Q)': ph_out,
        'X_nonempty_every_closure': all(o[0][X] for o in obs),
        'Y1_nonempty_every_closure': all(o[0][Y1] for o in obs),
        'Y2_nonempty_every_closure': all(o[0][Y2] for o in obs),
        'X_batches_per_period': sum(1 for o in obs if o[7][X]),
        'X_input_reached_50': any(o[5][X] for o in obs),
    }


def w3():
    """控制：Y 两条取货通道，一条首格是放行本产物、每 5 tick 限 1 件的准入口 G（经 1 格
    传送带进一直收货的收货端），一条经 3 格传送带进 X。G 排在轮询的前面。"""
    Q = 1
    net = Net(Q)
    Y = net.add_machine({'ore': 1}, 'B', 1, 1, 1, tag='Y')
    X = net.add_machine({'B': 1}, 'P', 1, 1, 1, tag='X')
    c = net.line(1, ('m', Y), item='ore')
    net.sources.append(('ore', c[0]))
    kG = net.add_sink(lambda t: True, None)
    g = net.line(2, ('k', kG), item='B')
    net.c_allow[g[0]] = 'B'
    net.c_k5[g[0]] = 1
    net.m_outch[Y].append(g[0])
    lx = net.line(3, ('m', X), item='B')
    net.m_outch[Y].append(lx[0])
    k = net.add_sink(lambda t: True, None)
    lo = net.line(1, ('k', k), item='P')
    net.m_outch[X].append(lo[0])
    # fixed order where Y's output determination comes before the gate's upstream moves
    res, order = run_to_cycle(net, 100, 2000)
    obs = res['obs']
    t1 = res['t1']
    # connected channels at closure: G connected iff not blocked (window active and full)
    # recompute from a replay: count receipts of G per 5 ticks
    empties = [i for i, o in enumerate(obs) if not o[0][X]]
    # 再走一个周期，逐个闭合时刻记 G 的存货端口通道是否接通（未因上限用尽而阻断）
    connected = []
    t = res['t2']
    for _ in range(res['period']):
        t += 1
        net.ev_phase = set()
        net.step(t, order)
        ws = net.c_wstart[g[0]]
        blocked = ws is not None and t < ws + 5 * Q and net.c_wcnt[g[0]] >= 1
        connected.append((0 if blocked else 1) + 1)
    return {
        'Y_connected_channels_at_each_closure': connected,
        'period_steps': res['period'],
        'Y_nonempty_every_closure': all(o[0][Y] for o in obs),
        'X_empty_closures_per_period': len(empties),
        'G_receipts_per_period': sum(o[2][g[0]] for o in obs),
        'X_line_first_cell_receipts_per_period': sum(o[2][lx[0]] for o in obs),
    }


if __name__ == '__main__':
    print(json.dumps({'W1': w1(), 'W2a': w2(False), 'W2b': w2(True), 'W3': w3()}, ensure_ascii=False, indent=1, default=str))
