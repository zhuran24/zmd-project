"""只读几何探针：B 组单桩输入的格组数、格 LP 和已有综合上限。

输出只写入本脚本所在目录。不导入项目模块，不运行项目求解器。
浮点 LP 只用于筛查，不充当正式证书。
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

SOURCE = Path('/home/zhuran24/zmd-research-fresh/求解器/候选约束轮次/第78-80轮/推导78B')


def cells(x, y, w, h):
    return {(i, j) for i in range(x, x+w) for j in range(y, y+h)}


def solve(p, hole, forbidden=()):
    px, py = p
    excluded = cells(px, py, 2, 2) | set(forbidden)
    supply = cells(px-5, py-5, 12, 12)
    hole_cells = cells(*hole)
    placements = []
    centers = []
    for cx in range(max(2, px-6), min(68, px+7)+1):
        for cy in range(max(2, py-6), min(68, py+7)+1):
            block = cells(cx-1, cy-1, 3, 3)
            if block & (excluded | hole_cells) or not block & supply:
                continue
            centers.append((cx, cy))
            placements.append(block)
    grid = {(a,b):len({((x+a)//3,(y+b)//3) for x,y in centers})
            for a in range(3) for b in range(3)}
    all_cells = sorted(set().union(*placements)) if placements else []
    index = {c:i for i,c in enumerate(all_cells)}
    A = lil_matrix((len(all_cells),len(placements)),dtype=float)
    for j, block in enumerate(placements):
        for c in block:
            A[index[c],j]=1
    r=linprog(-np.ones(len(placements)),A_ub=A.tocsr(),
              b_ub=np.ones(len(all_cells)),bounds=(0,None),method='highs')
    assert r.success, r.message
    return dict(p=p,hole=hole,placements=len(placements),cells=len(all_cells),
                min_grid=min(grid.values()),grid={str(k):v for k,v in grid.items()},
                lp=-r.fun,price_sum=float(-sum(r.ineqlin.marginals)))


def main():
    certs=json.loads((SOURCE/'power_certificates.json').read_text())['17']
    caps={tuple(c['p']):c['cap'] for c in json.loads((SOURCE/'capacities.json').read_text())}
    result=[]
    for p in [(20,20),(43,20),(68,8),(47,16),(1,1)]:
        r=solve(p,(49,17,21,53))
        c=next(c for c in certs if (c['x'],c['y'])==p)
        r.update(old_tiles=len(c['tiles']),old_tile_cap=c['cap'],old_combined_cap=caps[p])
        result.append(r)
    # 当前 1110 档的一种允许位置；离该空矩形较远的单桩。
    current=solve((20,20),(40,30,30,37))
    # 整数上下证书给出精确值 24，独立于浮点 LP 的误差。
    selected=[(x,y) for x in (14,17,20,23,26) for y in (14,17,20,23,26)
              if (x,y)!=(20,20)]
    occupied=set()
    for x,y in selected:
        block=cells(x-1,y-1,3,3)
        assert not block & occupied and not block & cells(20,20,2,2)
        assert block & cells(15,15,12,12)
        assert not block & cells(40,30,30,37)
        occupied |= block
    prices={(x,y) for x in (15,18,21,24,27) for y in (15,18,21,24,27)
            if (x,y)!=(21,21)}
    count=0
    for x in range(14,28):
        for y in range(14,28):
            block=cells(x-1,y-1,3,3)
            if block & cells(20,20,2,2):continue
            assert len(block & prices)>=1
            count+=1
    assert len(selected)==len(prices)==24 and count==current['placements']==180
    current.update(exact_value=24,exact_primal_centers=selected,
                   exact_dual_price_one_cells=sorted(prices),exact_checks_passed=True)
    result.append(current)
    target=Path(__file__).with_suffix('.json')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for r in result:
        print(json.dumps({k:v for k,v in r.items() if k!='grid'},ensure_ascii=False))


if __name__=='__main__':
    main()
