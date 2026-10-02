import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
D=[(1,0),(0,1),(-1,0),(0,-1)]
m=[dict(id='B',x0=0,y0=4,x1=4,y1=8,Din=1),dict(id='A',x0=6,y0=0,x1=10,y1=4,Din=2),dict(id='C',x0=6,y0=5,x1=10,y1=9,Din=0)]
t=[(5,9,0,2),(4,9,0,3),(5,5,0,3),(5,4,1,0),(11,4,2,1),(11,5,3,2)]
def transform(mx,tr,r,flip):
 def xy(x,y):
  if flip:x=-x
  for _ in range(r):x,y=-y,x
  return x,y
 def sd(d):return D.index(xy(*D[d]))
 out=[];tt=[]
 for u in mx:
  ps=[xy(u[x],u[y]) for x in ['x0','x1'] for y in ['y0','y1']];xx=[p[0] for p in ps];yy=[p[1] for p in ps]
  out.append(dict(id=u['id'],x0=min(xx),x1=max(xx),y0=min(yy),y1=max(yy),Din=sd(u['Din'])))
 for x,y,a,b in tr:tt.append((*xy(x,y),sd(a),sd(b)))
 xmin=min(u['x0'] for u in out);ymin=min(u['y0'] for u in out)
 xmin=min(xmin,min(a[0] for a in tt));ymin=min(ymin,min(a[1] for a in tt))
 return move(out,tt,-xmin,-ymin)
def move(mx,tr,x,y):
 return [dict(u,**{k:u[k]+(x if k[0]=='x' else y) for k in ['x0','x1','y0','y1']}) for u in mx],[(a+x,b+y,c,d) for a,b,c,d in tr]
def cells(mx,tr):return {(x,y) for u in mx for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)}|{(x,y) for x,y,*_ in tr}
def freeout(u,occ):
 d=(u['Din']+2)%4
 if d%2==0:p=[(u['x1'] if d==0 else u['x0'],y) for y in range(u['y0'],u['y1']+1)]
 else:p=[(x,u['y1'] if d==1 else u['y0']) for x in range(u['x0'],u['x1']+1)]
 return [(x+D[d][0],y+D[d][1]) for x,y in p if (x+D[d][0],y+D[d][1]) not in occ]
if __name__=='__main__':
 occ1=cells(m,t);best=[]
 for r in range(4):
  for flip in [False,True]:
   mm,tt=transform(m,t,r,flip)
   for dx in range(-16,17):
    for dy in range(-16,17):
     m2,t2=move(mm,tt,dx,dy);o=cells(m2,t2)
     if occ1&o:continue
     allc=occ1|o;xs=[p[0] for p in allc];ys=[p[1] for p in allc];w=max(xs)-min(xs)+1;h=max(ys)-min(ys)+1
     if not freeout(m[0],allc) or not freeout(m2[0],allc):continue
     allm=[dict(u,id='S1'+u['id']) for u in m]+[dict(u,id='S2'+u['id']) for u in m2]
     allm,allt=move(allm,t+t2,-min(xs),-min(ys))
     best.append((w*h,max(w,h),dict(W=w,H=h,machines=allm,transport=allt)))
 best.sort(key=lambda a:a[:2]);out=[];seen=set()
 for a,h,z in best:
  if (z['W'],z['H']) in seen:continue
  seen.add((z['W'],z['H']));out.append(dict(area=a,**z))
  if len(out)==20:break
 (BASE/'模块/plant-pairs.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print([(q['W'],q['H'],q['area']) for q in out])
