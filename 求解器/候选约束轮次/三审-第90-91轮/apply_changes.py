#!/usr/bin/env python3
"""第 90—91 轮修正版三审：写正式文件、候选状态行与进度段。只能跑一次（每处断言原文恰出现一次）。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
S = json.loads((HERE / 'out' / 'summary.json').read_text(encoding='utf-8'))

NEW_FORMAL = (
    '专用进路下缓存格不空的传递：专用进路指只运一种物品、由传送带、桥接器的一轴或不设收下上限的物品准入口'
    '（放行种类不设或就是这种物品）首尾相接、每个运输物品格只从前一格（或起点单位）收货只往后一格（或终点单位）送货、'
    '路上没有协议储存箱、分流器、汇流器的一串运输单位。在一个可到达循环态中，设制造单位 X 只做一个配方，一直有供电状态、开着，'
    '存货物品格、取货物品格和缓存格里只有这个配方的物品；配方时长 d tick，每批用原料 i 共 a_i 件（a_i≤50），'
    '原料 i 经 c_i 条专用进路进 X，d·c_i≥a_i；每条进路的起点是设为原料 i 的仓库取货口或协议核心取货端口'
    '（原料 i 是源矿或蓝铁矿时），或是一台一直有供电状态、开着、只做一个产物就是原料 i 的 1 tick 配方、'
    '取货物品格里只有原料 i、全部取货通道（含因物品准入口每 5 tick 收下上限用尽而断开、到期会重新接上的）'
    '不多于每批产物件数、在这个循环态中每个时刻的判定全部完成后缓存格都不空的制造单位。'
    '则 X 在这个循环态中每个时刻的判定全部完成后缓存格都不空。若还有 d=1、X 的全部取货通道不多于每批产物件数、'
    '各首运输物品格只从 X 收货且空着时总收下 X 的产物，则每条取货通道的首运输物品格一空，就在同一时刻取到 1 件；'
    '取任一时刻 θ，把 [θ+n, θ+n+1) 叫一刻，一条取货通道的首运输物品格在一刻里某个时点空着，叫它这一刻就绪，'
    '每条取货通道在它就绪的每一刻都恰好取到 1 件。这对各单位事件时刻的任意相位成立，与轮询次序、离线改变接通先后、'
    '判定先后以及 X 下游怎样运行（包括仓库停收与恢复）都无关')
NEW_JU = ('    据：物品格、存货/取货物品格、缓存格、制造、配方、需电功能、开关、移动、滞留、判定、轮询、取货优先级、'
          '存货优先级、传送带、桥接器、物品准入口、仓库取货口、协议核心、外部过程、零干预运行、离线、判定次序、'
          '接通先后、判定先后、端口速率、循环态')


def replace_once(text, old, new, what):
    assert text.count(old) == 1, (what, text.count(old))
    return text.replace(old, new)


def formal():
    p = ROOT / '求解充分条件.txt'
    lines = p.read_text(encoding='utf-8').split('\n')
    idx = [i for i, l in enumerate(lines) if l.startswith('专用进路下缓存格不空的传递：')]
    assert len(idx) == 1
    i = idx[0]
    assert '同一个相位 θ 加整数 tick' in lines[i]
    assert lines[i + 1].startswith('    据：')
    lines[i], lines[i + 1] = NEW_FORMAL, NEW_JU
    p.write_text('\n'.join(lines), encoding='utf-8')
    n = sum(1 for l in lines if l and not l.startswith(' ') and '：' in l and l != '由规则推出的充分条件')
    return n


ADOPT = ('    状态：第 90 轮 codex、第 91 轮 opus 复核未否证；主会话三审（2026-09-26）：通过，已采纳（两份逐字相同，合写一条）：'
         '求解充分条件「专用进路下缓存格不空的传递」换成任意相位版，去掉「事件都在同一相位 θ 加整数 tick」前提，'
         '「每个 θ 加整数的时刻」改为每个时刻。任意相位证明逐步核过，只用到停留至少 1 tick、配方时长是整数、'
         '同一时刻做到没有可动为止与循环态的周期（三审报告第 3 节）；三审补过的起点一直有供电状态且开着、'
         '产物就是原料 i、取货通道数含会重新接上的都在。按第 91 轮建议给「就绪」写出定义'
         '（首运输物品格在一刻里某个时点空着），「相应」照正式条文写作产物就是原料 i、设为原料 i；'
         '专用进路的定义与「全厂专用进路接法达标」取齐，X 的取货通道写明是全部取货通道。')

NOT_AGAIN = {
    '专线制造单位不空手的传递（第 90 轮修正版，改自第 88 轮修正版）':
        '本份多要求起点的存货物品格只放这个配方的原料、缓存格是这个配方的一批，证明用不到',
    '专线制造单位不空手的传递（第 91 轮修正版，改自第 88 轮修正版）':
        '本份多要求起点的存货物品格、取货物品格与缓存格都只有这个配方的物品，证明只用到取货物品格',
    '专线制造单位不空手的传递（第 90 轮修正版，改自第 89 轮修正版）':
        '条文与第 90 轮改自第 88 轮修正版的一份逐字相同，多要求起点的存货物品格只放这个配方的原料、缓存格是这个配方的一批，证明用不到',
    '专线制造单位不空手的传递（第 91 轮修正版，改自第 89 轮修正版）':
        '本份对 X 的取货首运输单位多排除设了放行种类的物品准入口，采纳条文只要它空着时总收下 X 的产物',
}


def candidates():
    p = ROOT / '候选充分条件.txt'
    lines = p.read_text(encoding='utf-8').split('\n')
    old_adopt = '    状态：第 90 轮 codex、第 91 轮 opus 复核未否证，待主会话三审。'
    hits = [i for i, l in enumerate(lines) if l == old_adopt]
    assert len(hits) == 2
    for i in hits:
        # 往上找条目名
        j = i - 1
        while not lines[j].startswith('专线制造单位不空手的传递（第 88 轮修正版，改自第 86 轮修正版'):
            j -= 1
        lines[i] = ADOPT
    old_wait = '    状态：待审（修正版，从零起算，需两轮有结论的复核）。'
    head = lines.index('第 90、91 轮修正版（待审）')
    done = set()
    for i in range(head, len(lines)):
        if lines[i] == old_wait:
            j = i - 1
            while not lines[j].startswith('专线制造单位不空手的传递（'):
                j -= 1
            name = lines[j].split('：', 1)[0]
            why = NOT_AGAIN[name]
            lines[i] = ('    状态：主会话三审（2026-09-26，第 90—91 轮修正版三审）判定不再复核：与同时采纳的'
                        '「专用进路下缓存格不空的传递」是同一件事（去掉共同相位前提、起点补一直有供电状态且开着），'
                        f'逐项对过没有多出有用的内容：{why}；结论相同。')
            done.add(name)
    assert done == set(NOT_AGAIN), done
    p.write_text('\n'.join(lines), encoding='utf-8')


def progress(n_formal):
    ex = S['exhaust']
    main = {k: v for k, v in ex.items() if k.startswith('C')}
    ctrl = {k: v for k, v in ex.items() if k.startswith('K')}
    ph = S['phase_normal']
    assert S['exhaust_main_all_zero'] and S['exhaust_controls_all_caught']
    assert ph['x_empty_cycles'] == ph['line_empty_cycles'] == ph['yfirst_empty_cycles'] == 0
    assert ph['xfirst_empty_cycles'] == 0 and ph['window_viol'] == 0
    cyc = sum(v['前提子图中在环上的状态'] for v in main.values())
    text = (
        '进度（2026-09-26，第 90—91 轮修正版三审）：主会话三审第 90 轮 codex、第 91 轮 opus 两轮都未否证的 2 份修正版'
        '（「专线制造单位不空手的传递」第 88 轮修正版，改自第 86 轮修正版，分别源于第 84、85 轮修正版；两份逐字相同，'
        '都在 候选充分条件.txt），否证 0 份，通过：求解充分条件「专用进路下缓存格不空的传递」换成任意相位版，'
        '去掉「事件都在同一相位 θ 加整数 tick」前提。任意相位证明三审逐步核过：相邻格倒推只减 1 tick 的停留，'
        '起点一空即补只比较一段不足 1 tick 的时间，X 不空手只在「(s, p] 里每条进路至少送 ⌊p−e⌋≥d 件」处取整，'
        '用的是配方时长 d 为整数；没有一步用整数时刻、共同相位、轮询次序、判定先后或下游何时收货。三审补过的起点一直有供电状态且开着、'
        '产物就是原料 i、取货通道数含会重新接上的都在条文里。按第 91 轮建议给「就绪」写出定义，专用进路的定义与'
        '「全厂专用进路接法达标」取齐，X 的取货通道写明是全部取货通道。三审自写程序核对：小容量穷举'
        f'（1/2、1/3 tick 格点，判定先后与下游收货任意，{len(main)} 组主接法前提成立的环上状态共 {cyc} 个，违反 0；'
        f'去掉起点开着、起点取货通道数、进路条数、进路不限量、X 取货通道数任一前提的 {len(ctrl)} 组对照都查出违反）；'
        f'有理数精确的随机相位模拟 {ph["runs"]} 次，前提成立的循环 {ph["premise_cycles"]} 个'
        f'（事件跨多个相位的 {ph["multi_phase"]} 个、X 原料格到过 50 的 {ph["input_full"]} 个），'
        f'X、进路、起点首格空 0 次，末句 {ph["windows"]} 个一刻违例 0。第 90、91 轮给出的 4 份新修正版'
        '与采纳条文是同一件事，没有多出有用的内容，不再复核；「专线制造单位不空手的传递」这一支至此收口。'
        f'求解充分条件仍 {n_formal} 条，求解约束未改（77 条），内核不用同步。三审报告、自写复算程序与输出在 '
        '求解器/候选约束轮次/三审-第90-91轮/。')
    p = ROOT / '候选约束.txt'
    lines = p.read_text(encoding='utf-8').split('\n')
    idx = [i for i, l in enumerate(lines) if l.startswith('进度（2026-09-26，第 90—91 轮）：')]
    assert len(idx) == 1
    i = idx[0]
    assert not any(l.startswith('进度（2026-09-26，第 90—91 轮修正版三审）') for l in lines)
    lines[i + 1:i + 1] = ['', text]
    p.write_text('\n'.join(lines), encoding='utf-8')
    return text


if __name__ == '__main__':
    n = formal()
    candidates()
    t = progress(n)
    print('求解充分条件条数', n)
    print(t)
