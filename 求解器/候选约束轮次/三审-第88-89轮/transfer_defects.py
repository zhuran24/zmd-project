#!/usr/bin/env python3
"""已采纳的「专用进路下缓存格不空的传递」两处漏洞的小例子（三审自写，整数 tick，全部事件在同一相位上）。

甲：起点制造单位只做一个 1 tick 配方，但产物不是原料 i。粉碎机 Y 只收源矿（做源矿→源石粉末），
    唯一取货通道的首运输单位是只放行蓝铁粉末、不设上限的物品准入口，其后一格传送带进精炼炉 X
    （X 只做蓝铁粉末→蓝铁块，d=1、a=1、c=1）。准入口按身份阻断，Y 的取货物品格装满 50 件源石粉末后，
    做好的一批留在缓存格里，Y 每刻缓存格都不空；进路只可能运蓝铁粉末（实际什么也不运），X 永远空手。
乙：起点的取货通道数只数此刻接通的。精炼炉 Y（蓝铁矿→蓝铁块）有两条取货通道：一条首运输单位是放行蓝铁块、
    每 5 tick 收下上限 1 的物品准入口 G（其后一直能收），一条经一格传送带进粉碎机 X（蓝铁块→蓝铁粉末）。
    G 收下一件后断开存货端口通道 5 tick，每个时刻判定做完后 Y 接通的取货通道都只有 1 条；
    G 窗口走完、重新接上的那一刻，Y 新一批进格，按接通先后 G 先取（判定先后与轮询次序允许的一种），
    X 那一格落空，X 每 5 tick 空手一次。
每个时刻按下面写死的先后逐个做判定，做到没有可动为止。输出每个 tick 判定做完后 X 缓存格是否为空。
"""
import json


def run_a(T=60):
    # Y: 存货 50 源矿（矿线一直补），取货格 0，缓存空；G 放行蓝铁粉末；b1 传送带；X 精炼炉
    y_store, y_cache, y_pk = 50, None, 0      # y_cache: 完成时刻
    g, b1 = None, None                        # (物品, 进格时刻)
    x_store, x_cache, x_pk = 0, None, 0
    empty = []
    y_nonempty = []
    for t in range(T):
        changed = True
        while changed:
            changed = False
            # 矿线补 Y（Y 存货未满 50 就补 1 件，矿线一直有货）
            if y_store < 50:
                y_store += 1
                changed = True
            if y_cache is not None and t >= y_cache and y_pk + 1 <= 50:
                y_cache, y_pk = None, y_pk + 1      # 源石粉末整批进取货物品格
                changed = True
            if y_cache is None and y_store >= 1:
                y_store -= 1
                y_cache = t + 1
                changed = True
            # G 只放行蓝铁粉末：源石粉末永远进不去（阻断，存货端口通道断开）
            # b1、X：没有来料
            if x_cache is not None and t >= x_cache:
                x_cache, x_pk = None, x_pk + 1
                changed = True
        empty.append(x_cache is None)
        y_nonempty.append(y_cache is not None)
    return dict(ticks=T, y_pk=y_pk, y_cache_nonempty_ticks=sum(y_nonempty), x_empty_ticks=sum(empty))


def run_b(T=100, warm=20):
    y_cache, y_pk = None, 0
    g = None            # G 格里的物品进格时刻
    g_win = None        # 当前 5 tick 窗口起点
    b1 = None
    x_store, x_cache, x_pk = 0, None, 0
    y_conn = []
    x_empty = []
    y_empty = []
    for t in range(T):
        changed = True
        while changed:
            changed = False
            # G 的窗口到期即重新接上
            if g_win is not None and t >= g_win + 5:
                g_win = None
                changed = True
            # G 格里的物品放满 1 tick 后送走（下游一直能收）
            if g is not None and t >= g + 1:
                g = None
                changed = True
            # b1 → X
            if b1 is not None and t >= b1 + 1 and x_store < 50:
                b1 = None
                x_store += 1
                changed = True
            # X
            if x_cache is not None and t >= x_cache and x_pk + 1 <= 50:
                x_cache, x_pk = None, x_pk + 1
                changed = True
            if x_cache is None and x_store >= 1:
                x_store -= 1
                x_cache = t + 1
                changed = True
            if x_pk > 0:
                x_pk -= 1        # X 的出货路一直通
                changed = True
            # Y（矿线一直有货，存货够）
            if y_cache is not None and t >= y_cache and y_pk + 1 <= 50:
                y_cache, y_pk = None, y_pk + 1
                changed = True
            if y_cache is None:
                y_cache = t + 1
                changed = True
            # Y 的两条取货通道：G 接通且空着时 G 先取（按接通先后），然后 b1
            if y_pk > 0 and g is None and g_win is None:
                y_pk -= 1
                g = t
                g_win = t          # 收下第一件，窗口起算；上限 1 用尽，断开
                changed = True
            if y_pk > 0 and b1 is None:
                y_pk -= 1
                b1 = t
                changed = True
        if t >= warm:
            y_conn.append(1 + (1 if g_win is None else 0))
            x_empty.append(x_cache is None)
            y_empty.append(y_cache is None)
    return dict(ticks=T - warm, y_connected_channels_after_closure=sorted(set(y_conn)),
                y_empty_ticks=sum(y_empty), x_empty_ticks=sum(x_empty))


if __name__ == '__main__':
    print(json.dumps(dict(甲=run_a(), 乙=run_b()), ensure_ascii=False))
