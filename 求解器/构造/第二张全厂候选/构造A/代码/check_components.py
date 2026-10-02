#!/usr/bin/env python3
"""静态检查器关键几何函数的对照，不冒充整厂候选复查。"""
import json
import random
from pathlib import Path
from static_check import rebuild_channels,maximum_rectangle

BASE=Path(__file__).resolve().parents[1]


def brute(occ,w,h,minimum):
    best=(-1,-1)
    for x0 in range(w):
        for x1 in range(x0+minimum-1,w):
            for y0 in range(h):
                for y1 in range(y0+minimum-1,h):
                    if all((x,y) not in occ for x in range(x0,x1+1) for y in range(y0,y1+1)):
                        a,b=x1-x0+1,y1-y0+1
                        best=max(best,(a*b,min(a,b)))
    return best


def main():
    results=[]
    ports={('M',0,0):((0,0),'out'),('N',2,0):((1,0),'in')}
    results.append(dict(test='非运输单位相邻不形成通道',pass_test=rebuild_channels(ports,set())==set()))
    ports={('M',0,0):((0,0),'out'),('T',2,0):((1,0),'in'),
           ('T',1,0):((1,0),'out'),('N',3,0):((1,1),'in')}
    got=rebuild_channels(ports,{'T'})
    want={(('M',0,0),('T',2,0)),(('T',1,0),('N',3,0))}
    results.append(dict(test='转弯传送带的两条自动通道',pass_test=got==want))
    incomplete={(('M',0,0),('T',2,0))}
    results.append(dict(test='独立重建发现漏报的自动通道',pass_test=got-incomplete=={(('T',1,0),('N',3,0))}))
    ports[('N',3,0)]=((1,1),'out')
    results.append(dict(test='取货对取货不形成通道',pass_test=rebuild_channels(ports,{'T'})==incomplete))
    rng=random.Random(98100)
    trials=[]
    for n in range(80):
        occ={(x,y) for x in range(8) for y in range(7) if rng.random()<0.22}
        actual=maximum_rectangle(occ,8,7,2)
        score=(-1,-1) if actual is None else (actual['area'],actual['short_side'])
        expected=brute(occ,8,7,2)
        trials.append(score==expected)
    results.append(dict(test='80张小图最大空矩形与四边界穷举对照',pass_test=all(trials),cases=len(trials)))
    answer=maximum_rectangle(set())
    results.append(dict(test='空70×70图最大矩形',pass_test=answer['area']==4900 and answer['short_side']==70))
    results.append(dict(test='满70×70图无合格矩形',pass_test=maximum_rectangle({(x,y) for x in range(70) for y in range(70)}) is None))
    assert all(r['pass_test'] for r in results)
    out=dict(all_pass=True,checks=results,
             scope='仅几何组件对照；未运行任何完整S2坐标候选，未完成逐格布局验证')
    (BASE/'证据/静态程序组件对照.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False))


if __name__=='__main__':main()
