"""三审自写：1113 空矩形位于 (49,b) 时，逐个桩位求它至多能为几台在产制造单位供电（局部放宽的精确最大值或已证上界）。

放宽：只保留该桩实际覆盖的在产制造单位——机身与供电范围相交、落在可用格（列行 1..69、不在空矩形）、
不碰桩身、互不重叠，两条端口边外各至少一个可用、非桩身、未被所选机身占用的邻格；台数至多 23。
第 0 行、列不可作机身或端口邻格：那里是仓库取货口，唯一空格只接一个单位，不能承载循环正流量。
真实布局中该桩覆盖的在产机器满足这些条件，故真实台数不超过本模型的最大值（或求解器给出的上界）。

输出 out/site_power_b{b}.json：{"px,py": {"c": 上界, "status": ..., "lb": 可行台数}}。
"""
import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool

from ortools.sat.python import cp_model

from local_pole import enumerate_options, build
import field as S


OBJ = 'count'


def window_clear(b, px, py):
    """机身与端口邻格可能到达的窗口全可用时，局部模型就是普通单桩模型的平移。"""
    return all(S.usable((x, y), b) for x in range(px - 11, px + 13) for y in range(py - 11, py + 13))


def solve_one(args):
    b, px, py, seconds, obj = args
    global OBJ
    OBJ = obj
    if OBJ == 'weight' and window_clear(b, px, py):
        return (px, py, dict(c=54, lb=None, status='GENERAL', n=1240))
    opts = enumerate_options(px, py, lambda c: S.usable(c, b))
    if not opts:
        return (px, py, dict(c=0, lb=0, status='NO_OPTIONS', n=0))
    m, u, expr = build(opts, OBJ, 23)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = 1
    st = s.Solve(m)
    name = s.StatusName(st)
    if st == cp_model.OPTIMAL:
        v = int(round(s.ObjectiveValue()))
        return (px, py, dict(c=v, lb=v, status=name, n=len(opts)))
    ub = int(math.floor(s.BestObjectiveBound() + 1e-9))
    lb = int(round(s.ObjectiveValue())) if st == cp_model.FEASIBLE else None
    return (px, py, dict(c=(min(23, ub) if OBJ == 'count' else min(54, ub)), lb=lb, status=name, n=len(opts)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('b', type=int)
    ap.add_argument('--procs', type=int, default=8)
    ap.add_argument('--seconds', type=float, default=120)
    ap.add_argument('--only', default=None, help='逗号分隔的 px:py 列表，只算这些')
    ap.add_argument('--obj', choices=['count', 'weight'], default='count')
    a = ap.parse_args()
    global OBJ
    OBJ = a.obj
    poles = S.pole_positions(a.b)
    if a.only:
        poles = [tuple(map(int, t.split(':'))) for t in a.only.split(',')]
    path = f'out/site_power_b{a.b}.json' if a.obj == 'count' else f'out/site_weight_b{a.b}.json'
    done = {}
    if os.path.exists(path) and not a.only:
        done = json.load(open(path))
    todo = [(a.b, px, py, a.seconds, a.obj) for (px, py) in poles if f'{px},{py}' not in done]
    t = time.time()
    with Pool(a.procs) as pool:
        for k, (px, py, r) in enumerate(pool.imap_unordered(solve_one, todo, chunksize=4)):
            done[f'{px},{py}'] = r
            if a.only:
                print(px, py, r)
            if (k + 1) % 200 == 0 and not a.only:
                json.dump(done, open(path, 'w'))
                print(f'{k+1}/{len(todo)} {time.time()-t:.0f}s', flush=True)
    if not a.only:
        json.dump(done, open(path, 'w'))
    print('done', len(done), f'{time.time()-t:.0f}s')


if __name__ == '__main__':
    main()
