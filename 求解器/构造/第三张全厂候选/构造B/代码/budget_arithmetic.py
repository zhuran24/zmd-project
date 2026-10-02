import json
from fractions import Fraction as F
from pathlib import Path
B=Path(__file__).resolve().parents[1]
# Encoding A: rational direction-budget formulas from S2B section 9.
area=134*9+57*25+39*24;omega=F(379-8*32,2)+(22-2*6)+24+6
cases=[]
for p in range(1,101):
 for j in range(p+1):
  if 23*p-10*j>=230 and 54*p-25*j>=556:
   loose=(4751-16*p+2*j-4*(area-3291)-omega)/4
   exact=(4*(4900-area-81-138)-(650+90+8+omega+88+4)-16*p+2*j)/4
   cases.append((exact,loose,p,j))
best=max(cases);rect=max((w*h,min(w,h),w,h) for w in range(6,69) for h in range(6,69) if w*h<=best[0])
# Encoding B: integer-only exhaustive feasibility over candidate rectangle dimensions and pole bounds.
possible=[]
for w in range(6,69):
 for h in range(6,69):
  for p in range(1,71):
   for j in range(p+1):
    if 23*p-10*j<230 or 54*p-25*j<556:continue
    if 8*w*h+32*p-4*j<=7029:possible.append((w*h,min(w,h),w,h));break
   else:continue
   break
second=max(possible)
assert rect==second and best[0]==F(6681,8)
z=dict(machine_area=area,omega=str(omega),best_rational_upper=str(best[0]),wide_rational_upper=str(best[1]),best_budget_P=best[2],best_budget_J=best[3],dimension_upper_A=list(rect),dimension_upper_B=list(second),scope='两种编码核对 S2B 候选第9节的算术和整数尺寸枚举；不重新证明方向计数，不认证可实现性，不替换正式全局 U=1110。')
(B/'证据/面积算术双核.json').write_text(json.dumps(z,ensure_ascii=False,indent=2));print(json.dumps(z,ensure_ascii=False))
