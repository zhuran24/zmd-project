"""导出一条玩具实测割的完整证书，供 codex-1 独立复核。
内容：母图全部列（每列的行系数）、每行的类型与当前右端、有理化后的全部乘子 y（y=π 守恒行、y=ρ≥0 目标行、y=−μ≤0 容量行）、
主问题当前取值（为真的字面量）、原始割（有理系数）和取整后割（K=10^4），以及本脚本自己算的逐列残差最大值与两份割的当前违反量。"""
import json, sys
from fractions import Fraction as Fr
from toy import make_inst, Master, on_set, draw
from fulllp import FullLP
import math

inst = make_inst('D1')
M = Master(inst)
s, st, dt = M.solve(60, 4)
sol = M.extract(s)
on = on_set(sol)
F = FullLP(M)
res = F.solve(on)
assert res['value'] > 1e-9
terms, rhs, cur, rep = F.cut(res, on)
# recompute y exactly as in cut() to export
denom = 10 ** 6
def q(x): return Fr(round(x * denom), denom)
y = {}
for k, v in res['duals'].items():
    if k[0] == 'eq': y[k] = q(v)
    elif k[0] == 'tgt': y[k] = max(Fr(0), q(v))
    else: y[k] = min(Fr(0), q(v))
for cf in F.cols:
    sres = sum(coef * y[k] for k, coef in cf.items())
    if sres > 0:
        capk = next(k for k, coef in cf.items() if k[0] == 'cap' and coef > 0)
        y[capk] -= sres / cf[capk]
maxres = max(sum(coef * y[k] for k, coef in cf.items()) for cf in F.cols)
K = 10 ** 4
rt = {k: math.ceil(v * K) for k, v in terms.items()}
rr = math.ceil(rhs * K)
cur_r = sum(v for k, v in rt.items() if k in on)
def ks(k): return repr(k)
cert = dict(
    note='列条件：对每列 Σ_行 系数×y ≤ 0；y 守恒行任意、目标行 ≥0、容量行 ≤0。割：Σ_容量行 (−y)·u_行(x) ≥ Σ_目标行 y·t。'
         '容量行右端 u 的字面量：见 row_literal；outlet 行右端恒为 1。',
    rows={ks(k): dict(kind=k[0], rhs_now=(F.rhs_of(k, on) if k[0] == 'cap' else (0 if k[0] == 'eq' else str(inst.target[k[1]]))),
                      literal=(ks(F.lit_key(k)) if k[0] == 'cap' else None), y=str(y[k])) for k in F.rowkeys},
    cols=[{ks(k): c for k, c in cf.items()} for cf in F.cols],
    master_true_literals=sorted(ks(k) for k in on),
    cut_raw=dict(terms={ks(k): str(v) for k, v in terms.items()}, rhs=str(rhs), lhs_now=str(cur)),
    cut_rounded=dict(K=K, terms={ks(k): v for k, v in rt.items()}, rhs=rr, lhs_now=cur_r),
    self_check=dict(max_column_residual=str(maxres), raw_violated=bool(cur < rhs), rounded_violated=bool(cur_r < rr),
                    lp_shortfall=res['value']),
    layout=draw(inst, sol))
json.dump(cert, open('cert_D1_iter0.json', 'w'), ensure_ascii=False, indent=0)
print(json.dumps(cert['self_check']), len(cert['cols']), len(cert['rows']), len(terms))
