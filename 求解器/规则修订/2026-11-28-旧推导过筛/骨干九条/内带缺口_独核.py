# 独立复核：按 q 位置直接构造两带，算 t、|B|、g、K 单桩上限、合计
from collections import Counter
N=70
res=Counter()
for lg in range(0,70,3):      # 左带空格行
  for bg in range(0,70,3):    # 下带空格列
    # 左带占 col0 行 0..69 除 lg；下带占 row0 列 0..69 除 bg；角格 (0,0) 不能两带都占
    lrows=[r for r in range(70) if r!=lg]; bcols=[c for c in range(70) if c!=bg]
    if lg!=0 and bg!=0: continue          # 两带都占角
    if lg==0 and bg==0: q=(0,0)
    elif lg==0: q=(bg,0); bcols=[c for c in bcols]; 
    else: q=(0,lg)
    # 若某带空格在角而另一带占角，则该带实际从 1 起
    L=[r for r in lrows if not (r==0 and bg==0 and lg!=0 and False)]
    # 切三格口
    def cut(cells):
        cells=sorted(cells); runs=[];cur=[]
        for x in cells:
            if cur and x!=cur[-1]+1: runs.append(cur);cur=[]
            cur.append(x)
        runs.append(cur); centers=[]
        for r in runs:
            if len(r)%3: return None
            centers+= [r[i+1] for i in range(0,len(r),3)]
        return centers
    lc=cut([r for r in range(70) if (0,r)!=q and not (r==0 and lg==0)])
    bc=cut([c for c in range(70) if (c,0)!=q and not (c==0 and lg!=0)])
    if lc is None or bc is None: continue
    if len(lc)+len(bc)!=46: continue
    ore={(1,r) for r in lc}|{(c,1) for c in bc}
    I={(1,r) for r in range(1,70)}|{(c,1) for c in range(1,70)}
    B=set()
    for y in range(1,68):
        blk={(x,yy) for x in (1,2,3) for yy in (y,y+1,y+2)}
        if not blk&ore: B|=blk&I
        blk={(yy,x) for x in (1,2,3) for yy in (y,y+1,y+2)}
        if not blk&ore: B|=blk&I
    t=sum(((1,r+e) in B) for r in lc for e in(-1,1))+sum(((c+e,1) in B) for c in bc for e in(-1,1))
    g=sum(1 for r in lc if r-3 in lc and r+3 in lc)+sum(1 for c in bc if c-3 in bc and c+3 in bc)
    d=q[0]+q[1]
    tot=(92-t)+(91-len(B))+2*g+3+8+4
    res[(d,t,len(B),g,tot)]+=1
for k,v in sorted(res.items()): print(k,v)
print(sum(res.values()))
