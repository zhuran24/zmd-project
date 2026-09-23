import json
import edge_dp as e
from power_bound import OUT,legal_poles
r=(49,9,21,53);answers=[]
for forbidden in ('lower','upper'):
 def pole_allowed(p):return not(p[0]>=49 and (p[1]<9 if forbidden=='lower' else p[1]>=62))
 poles=[(x,y,2,2) for x,y in legal_poles(9) if pole_allowed((x,y)) and e.pole_loss((x,y,2,2),r)<=13]
 def allowed(kind,rr,axis,r):
  if kind=='P':return pole_allowed(rr)
  if kind!='M':return True
  x,y,w,h=rr
  return any(x-6<=p<=x+w+4 and y-6<=q<=y+h+4 for p,q,_,_ in poles)
 e.EXTRA_ALLOWED=allowed;e.line_table.cache_clear();e.solve_line.cache_clear()
 xs=[e.line_table(r,s,True,False) for s in ('E','N')]
 ys=[e.line_table(r,s,False,False) for s in ('W','S','N')]
 X=e.combine(xs,10,13);Y=e.combine(ys,10,13)
 out=dict(forbidden_right_arm_poles=forbidden,P=10,X=X,Y=Y,allowed=29,deficit=X+Y-29)
 answers.append(out);print(out,flush=True)
(OUT/'branch_power_dp_results.json').write_text(json.dumps(answers,indent=2))
