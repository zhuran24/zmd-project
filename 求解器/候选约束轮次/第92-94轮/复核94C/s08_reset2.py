#!/usr/bin/env python3
"""依赖核对续：近饱和随机起态 + 随机时刻清空 C 的成功记录（同 s08_reset.py 的读法），看 Φ 下界。"""
import json, random
import s08_s09
from stepsim import Machine

_orig = Machine.judge
STATE = {'rng': None, 'p': 0.0}

def judge_with_reset(self, t):
    if self.name == 'C' and STATE['rng'].random() < STATE['p']:
        self.last_succ = {}
    return _orig(self, t)

Machine.judge = judge_with_reset
out = {}
for p in (0.02, 0.2, 0.6):
    STATE['rng'] = random.Random(int(p * 1000))
    STATE['p'] = p
    out[str(p)] = s08_s09.s08_random(3000, 300, 51, 'near')
    print(p, out[str(p)], flush=True)
json.dump(out, open('s08_reset2.json', 'w'), ensure_ascii=False, indent=1)
