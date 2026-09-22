import sys, json
from toy import *
from fulllp import FullLP
inst = make_inst('D1')
M = Master(inst, subsets=True)
s, st, dt = M.solve(60, 4)
print(s.StatusName(st), dt)
sol = M.extract(s)
print(draw(inst, sol))
for i in sol['y']:
    print(i, inst.pl[i]['type'], inst.pl[i]['fp'], 'ins', inst.pl[i]['ins'], 'outs', inst.pl[i]['outs'])
print('chQT', sol['chQT']); print('chTS', sol['chTS']); print('chTU', sol['chTU']); print('chUT', sol['chUT'])
print('nTT', len(sol['chTT']))
res = LPSub(M).solve(sol)
print('reduced LP shortfall', res['value'], res['nvars'], res['ncons'])
print({k: round(v,3) for k, v in res['flows'].items()})
F = FullLP(M)
r2 = F.solve(on_set(sol))
print('full LP shortfall', r2['value'])
