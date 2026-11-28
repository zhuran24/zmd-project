from itertools import permutations, combinations
from collections import Counter
from fractions import Fraction

def channels(history, ports):
    # 移除最后建成者。其当时接上的通道必为末段。
    if not history:
        return ()
    last = history[-1]
    prefix = history[:-1]
    suffix = tuple(edge for other, edge in ports[last] if other in prefix)
    return channels(prefix, ports) + suffix

star = {'P': [('E','东'),('S','南'),('W','西')],
        **{n:[('P',e)] for n,e in zip('ESW','东南西')}}
square = {'A':[('B','AB'),('D','AD')], 'B':[('A','AB'),('C','BC')],
          'D':[('A','AD'),('C','DC')], 'C':[('D','DC'),('B','BC')]}
for label, cond in [('同图',lambda p:set(p[:2])==set('PE')),('离线',lambda p:True),
                    ('中央最后',lambda p:p[-1]=='P')]:
    counts = Counter(channels(p,star) for p in permutations(star) if cond(p))
    print(label, sum(counts.values()),counts)
square_orders = Counter(channels(p,square) for p in permutations(square))
print(square_orders)
print({(x,y):{s.index(x)<s.index(y) for s in square_orders} for x,y in combinations(('AB','BC','AD','DC'),2)})
print(Fraction(18,30),Fraction('16.5')/30)
