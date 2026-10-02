#!/usr/bin/env python3
"""互核编码一、编码二的关键量。用法：python3 compare.py 编码一结果.json 编码一结果-进路.json 编码二结果.json 输出.json"""
import json, sys, collections
a = json.load(open(sys.argv[1])); ar = json.load(open(sys.argv[2])); b = json.load(open(sys.argv[3]))
A = collections.Counter((tuple(r['起点']), tuple(r['终点']), r['运输物品格数']) for r in ar)
B = collections.Counter((tuple(x[0]), tuple(x[1]), x[2]) for x in b['进路明细'])
# 缺路：编码一按（来源身份->终点），编码二按（来源身份,终点）；身份名不同，统一成终点+条数与总数比较
amiss = collections.Counter()
for k, v in a['缺路'].items():
    s, t = k.split('->'); amiss[t] += v
bmiss = collections.Counter()
for s, t, n in b['缺路']: bmiss[t] += n
items = {
 '通道数': (a['重建通道数'], b['重建通道数']),
 '完整进路数': (a['到达非运输单位存货端口的进路'], b['倒追得到的完整进路']),
 '进路逐条(起点端口,终点端口,格数)一致': (A == B, A == B),
 '相邻桥逆向通道': (a['相邻桥逆向通道数'], b['相邻桥逆向通道']),
 '多余通道': (len(a['多余通道']), len(b['多余通道'])),
 '共用物品格': (len(a['被多路共用的物品格']), len(b['共用物品格'])),
 '不在进路上的传送带': (len(a['不在进路上的传送带']), len(b['不在进路上的传送带'])),
 '缺路条数': (a['缺路条数'], b['缺路条数']),
 '缺路按终点逐台一致': (amiss == bmiss, amiss == bmiss),
 '接法外或超额': (len(a['接法外或超额进路']), len(b['接法外或超额'])),
 'H6->F4': (a['H6->F4格数'], b['H6_F4']),
 'Q6->F4': (a['Q6->F4格数'], b['Q6_F4']),
 '无供电': (a['无供电制造单位'], b['无供电']),
 '最大空矩形面积/短边': ([a['最大空矩形']['面积'], a['最大空矩形']['短边']], [b['最大空矩形']['面积'], b['最大空矩形']['短边']]),
 '最大空矩形位置': ([list(x) for x in a['最大空矩形']['位置(x0,y0,x1,y1)']], [list(x) for x in b['最大空矩形']['位置']]),
}
out = {k: {'编码一': v[0], '编码二': v[1], '一致': v[0] == v[1]} for k, v in items.items()}
json.dump(out, open(sys.argv[4], 'w'), ensure_ascii=False, indent=1)
for k, v in out.items(): print(k, v)
print('全部一致' if all(v['一致'] for v in out.values()) else '有不一致')
