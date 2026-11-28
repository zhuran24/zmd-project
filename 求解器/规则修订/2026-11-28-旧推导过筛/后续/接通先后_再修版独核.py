from collections import Counter
from itertools import combinations, permutations
from fractions import Fraction

def newly_formed(order, ports):
    # Each link is named by its source and destination.
    def key(link):
        later = max(link, key=order.index)
        return order.index(later), ports[later].index(link)
    return tuple(sorted({link for row in ports.values() for link in row}, key=key))

fan = dict(P=['PE', 'PS', 'PW'], E=['PE'], S=['PS'], W=['PW'])
orders = list(permutations(fan))
for cases in ( [o for o in orders if set(o[:2]) == {'P', 'E'}],
               orders, [o for o in orders if o[-1] == 'P'] ):
    print(len(cases), Counter(newly_formed(o, fan) for o in cases))

square = dict(A=['AB', 'AD'], B=['AB','BC'], D=['AD','DC'], C=['DC','BC'])
rankings = {newly_formed(o, square) for o in permutations(square)}
pairs = list(combinations(sorted(next(iter(rankings))), 2))
print(len(rankings), sum(len({r.index(a) < r.index(b) for r in rankings}) == 2 for a,b in pairs),
      sum(set(r[-2:]) == {'AB','DC'} for r in rankings))

# X -> Y -> M. For each build, replay the existing belt-end renewal
# specified by the grid model if the newly added cell extends Y upstream.
line = dict(X=['XY'], Y=['XY','YM'], M=['YM'])
for o in permutations(line):
    initial = newly_formed(o, line)
    model = list(initial)
    if o[-1] == 'X':
        model.remove('YM')
        model.append('YM')
    if tuple(model) != initial:
        print(o, initial, tuple(model))
print(Fraction(18,30), Fraction('16.5')/30)
