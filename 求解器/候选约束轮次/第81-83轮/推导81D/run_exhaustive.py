#!/usr/bin/env python3
"""并行跑编码二的一组参数（至多 3 进程），结果写 exhaustive_results.json。"""
import json, sys
from multiprocessing import Pool
sys.path.insert(0, '.')
import cell_exhaustive as ce

PARAMS = [(2, 1, 1), (2, 2, 1), (2, 1, 2), (3, 1, 1), (3, 2, 2), (3, 1, 3), (3, 3, 1), (3, 3, 3),
          (4, 1, 1), (4, 2, 1), (4, 1, 2), (4, 2, 2), (5, 1, 1), (5, 2, 2), (5, 3, 1), (6, 2, 2), (5, 3, 3), (7, 2, 2), (8, 1, 2), (6, 3, 2)]


def one(p):
    r = ce.run(*p)
    r.pop('cycles', None) if False else None
    return r


if __name__ == '__main__':
    with Pool(3) as pool:
        res = pool.map(one, PARAMS, chunksize=1)
    tot = {}
    for r in res:
        for k, v in r['violations'].items():
            tot[k] = tot.get(k, 0) + v
    json.dump(dict(params=PARAMS, total_violations=tot, results=res), open('exhaustive_results.json', 'w'),
              ensure_ascii=False, indent=1)
    print(json.dumps(dict(total_violations=tot,
                          summary=[(r['m'], r['L1'], r['L2'], r['states'], r['violations'],
                                    {k: (v['cycles'], v['low_rate_cycles'], v['low_rate_cycles_phi_ge_S'])
                                     for k, v in r['cycles'].items()}, r['seconds']) for r in res]),
                     ensure_ascii=False))
