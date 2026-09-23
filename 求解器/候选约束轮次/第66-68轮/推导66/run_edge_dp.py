from edge_dp import *
results=[]
for b in (9,17):
 r=(49,b,21,53)
 ts=[line_table(r,s,False,False) for s in ('W','S','N') if s!='N' or b==9]
 xs=[line_table(r,s,True,False) for s in ('E','N')]
 xc=[line_table(r,s,True,True) for s in ('E','N')] if b==9 else None
 for P in (10,11,12):
  budget=23*P-217;J=budget//9
  X=combine(xs,P,budget)
  if xc:
   corner_loss=pole_loss((68,68,2,2),r)
   if budget>=corner_loss:X=min(X,combine(xc,P-1,budget-corner_loss))
  Y=combine(ts,P,budget)
  allowed=187-16*P+2*J
  row=dict(b=b,P=P,budget=budget,X=X,Y=Y,allowed=allowed,deficit=X+Y-allowed)
  results.append(row);print(json.dumps(row),flush=True)
(ROOT/'edge_dp_results.json').write_text(json.dumps(results,indent=2))
