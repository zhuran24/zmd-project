"""母图上的完整线性规划（左边系数固定，右端＝主问题字面量），第一阶段对偶 → Farkas 割，有理数逐列核。"""
import time, math
from fractions import Fraction as Fr
from ortools.linear_solver import pywraplp
from toy import RECIPES, ITEMS, PRODUCTS, AX, OPP, nb


class FullLP:
    def __init__(self, M):
        self.M = M
        I = self.I = M.inst
        rows = {}   # key -> dict(kind='eq'|'cap'|'tgt', lit=key-for-literal or None, const)
        cols = []   # list of dict(coefs={rowkey:coef})

        def slot(c, kind, d):
            return ('S', c, '0') if kind == '0' else ('S', c, AX[d])
        for (c, d, kt, kh) in M.chTT:
            t = slot(c, kt, d); h = slot(nb(c, d), kh, OPP[d])
            for it in ITEMS:
                cols.append({('eq', t, it): -1, ('eq', h, it): 1, ('cap', 'TT', c, d, kt, kh): 1,
                             ('cap', 'slot', t): 1})
        for (c, d, kt) in M.chTU:
            t = slot(c, kt, d)
            for i in M.minp[(c, d)]:
                for it in sorted(set(x for (a, b, tt) in RECIPES[I.pl[i]['type']] for x in a)):
                    cols.append({('eq', t, it): -1, ('eq', ('Min', i), it): 1, ('cap', 'TU', c, d, kt): 1,
                                 ('cap', 'slot', t): 1})
        for (c, d, kh) in M.chUT:
            h = slot(c, kh, d)
            for i in M.moutp[(c, d)]:
                for it in sorted(set(x for (a, b, tt) in RECIPES[I.pl[i]['type']] for x in b)):
                    cols.append({('eq', ('Mout', i), it): -1, ('eq', h, it): 1, ('cap', 'UT', c, d, kh): 1})
        for (qi, kh) in M.chQT:
            c, d, item = I.outlets[qi]
            h = slot(c, kh, d)
            cols.append({('eq', h, item): 1, ('cap', 'QT', qi, kh): 1, ('cap', 'outlet', qi): 1})
        for (c, d, kt) in M.chTS:
            t = slot(c, kt, d)
            for it in PRODUCTS:
                cols.append({('eq', t, it): -1, ('tgt', it): 1, ('cap', 'TS', c, d, kt): 1, ('cap', 'slot', t): 1})
        for i, p in enumerate(I.pl):
            for (a, b, tt) in RECIPES[p['type']]:
                cf = {('cap', 'mach', i): tt}
                for it, q in a.items():
                    cf[('eq', ('Min', i), it)] = -q
                for it, q in b.items():
                    cf[('eq', ('Mout', i), it)] = q
                cols.append(cf)
        self.cols = cols
        rk = set()
        for cf in cols:
            rk.update(cf.keys())
        self.rowkeys = sorted(rk, key=repr)

    def rhs_of(self, key, sol_on):
        """capacity row right-hand side at a master point given as a set of 'on' literal keys."""
        tag = key[1]
        if tag == 'outlet':
            return 1
        if tag == 'slot':
            c, kind = key[2][1], key[2][2]
            return 1 if (('e0', c) if kind == '0' else ('eB', c)) in sol_on else 0
        if tag == 'mach':
            return 1 if ('y', key[2]) in sol_on else 0
        return 1 if key[1:] in sol_on else 0

    def lit_key(self, key):
        tag = key[1]
        if tag == 'outlet':
            return None
        if tag == 'slot':
            c, kind = key[2][1], key[2][2]
            return ('e0', c) if kind == '0' else ('eB', c)
        if tag == 'mach':
            return ('y', key[2])
        return key[1:]

    def solve(self, sol_on):
        lp = pywraplp.Solver.CreateSolver('GLOP')
        inf = lp.infinity()
        xs = [lp.NumVar(0, inf, '') for _ in self.cols]
        sl = {it: lp.NumVar(0, inf, '') for it in PRODUCTS}
        byrow = {k: [] for k in self.rowkeys}
        for j, cf in enumerate(self.cols):
            for k, v in cf.items():
                byrow[k].append((xs[j], v))
        cons = {}
        for k, terms in byrow.items():
            e = sum(v * q for v, q in terms)
            if k[0] == 'eq':
                cons[k] = lp.Add(e == 0)
            elif k[0] == 'cap':
                cons[k] = lp.Add(e <= self.rhs_of(k, sol_on))
            else:
                cons[k] = lp.Add(e + sl[k[1]] >= float(self.I.target[k[1]]))
        lp.Minimize(sum(sl.values()))
        t0 = time.time()
        st = lp.Solve()
        dt = time.time() - t0
        assert st == pywraplp.Solver.OPTIMAL
        return dict(value=lp.Objective().Value(), duals={k: c.dual_value() for k, c in cons.items()},
                    lp_time=dt, ncols=len(xs), nrows=len(cons))

    def cut(self, res, sol_on, denom=10 ** 6):
        D = res['duals']

        def q(x):
            return Fr(round(x * denom), denom)
        y = {}
        for k, v in D.items():
            if k[0] == 'eq':
                y[k] = q(v)
            elif k[0] == 'tgt':
                y[k] = max(Fr(0), q(v))
            else:
                y[k] = min(Fr(0), q(v))   # = -mu, mu >= 0
        # exact column check and repair (mu only increases)
        repaired = 0
        for cf in self.cols:
            s = sum(coef * y[k] for k, coef in cf.items())
            if s > 0:
                capk = next(k for k, coef in cf.items() if k[0] == 'cap' and coef > 0)
                y[capk] -= s / cf[capk]
                repaired += 1
        # final exact verification (independent pass)
        for cf in self.cols:
            assert sum(coef * y[k] for k, coef in cf.items()) <= 0
        rho_t = sum(y[('tgt', it)] * self.I.target[it] for it in PRODUCTS if ('tgt', it) in y)
        terms = {}
        const = Fr(0)
        for k, v in y.items():
            if k[0] != 'cap' or v == 0:
                continue
            mu = -v
            lk = self.lit_key(k)
            if lk is None:
                const += mu * 1
            else:
                terms[lk] = terms.get(lk, Fr(0)) + mu
        rhs = rho_t - const
        cur = sum((v for k, v in terms.items() if k in sol_on), Fr(0))
        return terms, rhs, cur, repaired
