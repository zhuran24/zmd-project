#!/usr/bin/env python3
"""依赖核对续（存档版，与 s08_reset3.json 对应）：随机清空 C 的成功记录（概率 P/次判定），
统计“两条首格同时空且清记录改变了队首”的次数，并检查 S08 下界。"""
import random, s08_s09, json
from stepsim import Machine
_orig = Machine.judge
cnt = {'reset': 0, 'both_empty': 0, 'changed': 0}
rng = random.Random(5)
P = 0.0

def jd(self, t):
    if self.name == 'C':
        before = self.out_order()
        empt = [e for e in self.out_routes if e.first_empty()]
        if rng.random() < P:
            self.last_succ = {}
            cnt['reset'] += 1
        after = self.out_order()
        if len(empt) == 2 and self.out and self.out[1] > 0:
            cnt['both_empty'] += 1
            if before[0] is not after[0]:
                cnt['changed'] += 1
    return _orig(self, t)

Machine.judge = jd
if __name__ == '__main__':
    res = {}
    for P in (0.01, 0.05):
        for mode, seed in (('near', 61), ('wide', 62)):
            cnt.update(reset=0, both_empty=0, changed=0)
            r = s08_s09.s08_random(3000, 300, seed, mode)
            res[f'{P}_{mode}'] = dict(nviol=r['nviol'], viol=r['viol'][:2], min_slack=r['min_slack'], **cnt)
            print(P, mode, res[f'{P}_{mode}'], flush=True)
    json.dump(res, open('s08_reset3.json', 'w'), ensure_ascii=False, indent=1)
