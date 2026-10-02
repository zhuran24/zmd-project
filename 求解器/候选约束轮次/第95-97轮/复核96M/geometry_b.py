"""Independent exact interval algorithm: no solver and no A imports.

All left normals have x interval [2,4], bottom normals y interval [2,4].
Cross-side conflicts therefore require both varying intervals to meet [2,4].
It suffices to forbid that event on one of the two sides. Each remaining side
is unweighted interval scheduling, solved by the earliest-finish theorem.
"""
from pathlib import Path
import json,time
OUT=Path(__file__).resolve().parent

def ports(g):
    return [3*k+1 if 3*k<g else 3*k+2 for k in range(23)]
def overlap(a,b):
    return a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3]
def inside(r,p):return r[0]<=p[0]<=r[2] and r[1]<=p[1]<=r[3]

def exact(left,bottom,kind,b=None,h=None):
    lp,bp=ports(left),ports(bottom)
    cut=(2,b,7,b+h-1) if b is not None else None
    gap=left or bottom
    fixed=None; bonus=0; witness_options=[None]
    if kind:
        # g is the single missing boundary coordinate; nearest ore positions
        # are g-2 and g+2, hence the 3-cell gap is g-1 ... g+1.
        fixed=(1,gap-1,3,gap+1) if left else (gap-1,1,gap+1,3)
        if cut and overlap(fixed,cut):return None
        bonus=2+(kind==2 and gap!=3)
        if kind==2:
            witness_options=[]
            for edge in (gap-2,gap+2):
                if edge==1:continue
                for inner in (2,3):
                    p=(inner,edge) if left else (edge,inner)
                    if cut is None or not inside(cut,p):witness_options.append(p)
    best=-1;chosen_best=None
    for witness in witness_options:
        axes=[[],[]]
        for axis,ps in enumerate((lp,bp)):
            for p in ps:
                for begin in range(p-2,p+1):
                    if begin<1 or begin+2>69:continue
                    r=(2,begin,4,begin+2) if axis==0 else (begin,2,begin+2,4)
                    if any(inside(r,q) for q in [(1,y) for y in lp]+[(x,1) for x in bp]):continue
                    if fixed and overlap(fixed,r):continue
                    if cut and overlap(cut,r):continue
                    if witness is not None and inside(r,witness):continue
                    axes[axis].append((begin,begin+2))
        for barred in (0,1):
            chosen=[[],[]]
            for axis in (0,1):
                end=0
                intervals=sorted(set(axes[axis]),key=lambda q:q[1])
                for lo,hi in intervals:
                    if axis==barred and lo<=4 and hi>=2:continue
                    if lo>end:chosen[axis].append((lo,hi));end=hi
                if (axis==1 and left==3) or (axis==0 and bottom==3):chosen[axis]=chosen[axis][:22]
            value=sum(map(len,chosen))
            if value>best:best=value;chosen_best=chosen
    if best<0:return 'infeasible'
    return {'value':46+bonus+best,'selected_intervals':chosen_best}

def main():
    start=time.monotonic();corners=[];scopes=[];conflicts=0
    layouts=[(0,0)]+[(q,0) for q in range(3,70,3)]+[(0,q) for q in range(3,70,3)]
    for left,bottom in layouts:
        for mode in ((0,1,2) if 0<(left or bottom)<69 else (0,)):
            result=exact(left,bottom,mode)
            corners.append({'key':[left,bottom,mode],'d':0,**result})
            for h in (6,7,8,9):
                for b in range(3,70-h):
                    d=sum(b<=p<b+h for p in ports(left))
                    if d>2:continue
                    result=exact(left,bottom,mode,b,h)
                    if result is None:conflicts+=1;continue
                    if result=='infeasible':scopes.append({'key':[left,bottom,mode,b,h],'d':d,'status':'INFEASIBLE'});continue
                    scopes.append({'key':[left,bottom,mode,b,h],'d':d,**result})
    for name,rows,ex in [('corner_b',corners,0),('scope_b',scopes,conflicts)]:
        ans={'encoding':'interval_greedy','rows':rows,'fixed_conflicts':ex,'count':len(rows),
             'max':max(r['value']+r['d'] for r in rows if 'value' in r),'seconds':time.monotonic()-start}
        (OUT/(name+'.json')).write_text(json.dumps(ans,separators=(',',':'))+'\n')
        print({k:v for k,v in ans.items() if k!='rows'},flush=True)
if __name__=='__main__':main()
