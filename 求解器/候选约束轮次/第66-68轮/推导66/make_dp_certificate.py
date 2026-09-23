import json
import edge_dp as e
from power_bound import OUT,legal_poles
cases=[]
for b,branch in [(9,'all'),(17,'all'),(9,'no_lower_pole'),(9,'no_upper_pole')]:
 r=(49,b,21,53)
 def pole_allowed(p):
  if branch=='all':return True
  return not(p[0]>=49 and (p[1]<9 if branch=='no_lower_pole' else p[1]>=62))
 poles=[(x,y,2,2) for x,y in legal_poles(b) if pole_allowed((x,y)) and e.pole_loss((x,y,2,2),r)<=13]
 def allowed(kind,rr,axis,r):
  if branch=='all':return True
  if kind=='P':return pole_allowed(rr)
  if kind!='M':return True
  x,y,w,h=rr
  return any(x-6<=p<=x+w+4 and y-6<=q<=y+h+4 for p,q,_,_ in poles)
 e.EXTRA_ALLOWED=allowed;e.line_table.cache_clear();e.solve_line.cache_clear()
 lines=[]
 for side,outer,corner in [('E',True,False),('N',True,False)]+([('E',True,True),('N',True,True)] if b==9 and branch=='all' else [])+[(s,False,False) for s in ('W','S','N') if s!='N' or b==9]:
  opts,gaps=e._options(r,side,outer,corner);table=e.line_table(r,side,outer,corner)
  lines.append(dict(side=side,outer=outer,corner=corner,options=[sorted(v) for v in opts],gaps=gaps,frontier=[[list(k),v] for k,v in sorted(table.items())]))
 cases.append(dict(b=b,branch=branch,lines=lines))
(OUT/'edge_integer_certificate.json').write_text(json.dumps(cases,separators=(',',':')))
print('certificate cases',len(cases),'lines',sum(len(c['lines']) for c in cases))
