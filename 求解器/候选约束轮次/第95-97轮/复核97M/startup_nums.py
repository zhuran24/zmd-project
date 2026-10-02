"""复核97M：§10 调试办法的数字（两种写法）。只写 startup_nums.json。"""
import json
from fractions import Fraction as F
from pathlib import Path
OUT = Path(__file__).resolve().parent
# 写法 A：按位置分项相乘
capA = 52*50 + 18*(50+3) + 9*(2*50+50+3) + 3*(2*50) + 2*70*70
# 写法 B：逐台逐格累加
capB = 0
for _ in range(34): capB += 50            # 蓝铁矿精炼炉存货
for _ in range(18): capB += 50 + 50 + 3   # 源矿粉碎机存货、取货、缓存
for _ in range(9):  capB += 50 + 50 + 50 + 3
for _ in range(3):  capB += 50 + 50
for x in range(70):
    for y in range(70): capB += 2
assert capA == capB == 15031
need = 11*50 + 2*70*70
assert need == 10350 and 80000 - capA >= need
# Φ 终点：A 存货 50 种子 + C 存货 50 株 (+ CA、AC 满 L)；条件 Φ >= L + 5/2
ok = {}
for L in range(2, 400):
    phi = 100 if L <= 97 else 100 + L
    ok[L] = phi >= F(2*L + 5, 2)
assert all(ok.values()) and max(L for L in range(2, 400) if 100 >= F(2*L+5, 2)) == 97
# 植物当量：每件可达派生物至多 1 株当量
eq_buck = {'荞花': F(1), '荞花粉末': F(1, 2), '细磨荞花粉末': F(1)}
eq_sand = {'砂叶': F(1), '砂叶粉末': F(1, 3), '细磨荞花粉末': F(1, 3), '致密源石粉末': F(1, 3)}
assert max(eq_buck.values()) <= 1 and max(eq_sand.values()) <= 1
# 研磨守恒：2 荞花粉末(=1 株) + 1 砂叶粉末(=1/3 砂叶) -> 1 细磨（1 株荞花 + 1/3 砂叶）
assert 2*eq_buck['荞花粉末'] == eq_buck['细磨荞花粉末'] and eq_sand['砂叶粉末'] == eq_sand['细磨荞花粉末']
res = dict(取出上界=capA, 余量下界=80000-capA, 补装上界=need, Φ条件L上界=97)
(OUT/'startup_nums.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)+'\n')
print(res)
