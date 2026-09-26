# -*- coding: utf-8 -*-
"""从前提快照的规则文件现读配方，列出：每个配方的时长 d、每种原料每批用量 a、
满足 d·c≥a 的最小专线条数 c，以及 1 tick 配方每批产物件数 k（作源头时全部取货通道的上限）。"""
import json
import math
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, '..', '前提快照', '《明日方舟：终末地》游戏规则.txt')

text = open(RULES, encoding='utf-8').read()
sec = text[text.index('\n配方\n'):]
machine = None
rows = []
for line in sec.splitlines():
    line = line.strip()
    if not line or line == '配方':
        continue
    if '→' not in line:
        machine = line
        continue
    lhs, rhs = line.split('→')
    rhs, dur = rhs.rsplit('，', 1)
    d = int(re.match(r'\s*(\d+)\s*tick', dur).group(1))
    ins = []
    for part in re.split(r'＋', lhs):
        m = re.match(r'\s*(\d+)\s*(\S+)\s*', part)
        ins.append((m.group(2), int(m.group(1))))
    m = re.match(r'\s*(\d+)\s*(\S+)\s*', rhs)
    prod, k = m.group(2), int(m.group(1))
    rows.append({'machine': machine, 'inputs': {n: a for n, a in ins}, 'product': prod, 'k': k, 'd': d,
                 'min_lines': {n: math.ceil(a / d) for n, a in ins}})
assert len(rows) == 18, len(rows)
print(json.dumps(rows, ensure_ascii=False, indent=1))
