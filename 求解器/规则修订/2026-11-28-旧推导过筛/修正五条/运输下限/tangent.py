"""独立：47 种边带排布下，46 个矿石格的 92 个切向方向中，对面格能被一个不压矿石格、不出第1..69行列的 3x3 块覆盖的个数（上界：切向可接非运输端口的方向数）。"""
def layouts():
    # 左边 x=0 的取货口覆盖 y 段，下边 y=0 覆盖 x 段；空格位置 0-index 3k (k=0..23)，至少一个在角(0)
    res=[]
    for gl in range(0,70,3):
        for gb in range(0,70,3):
            if gl!=0 and gb!=0: continue
            # 左边：空格 gl，其余 69 格从 y=0..69 去掉 gl 后按 3 分段
            def segs(gap):
                cells=[i for i in range(70) if i!=gap]
                return [cells[3*k:3*k+3] for k in range(23)]
            L=segs(gl); B=segs(gb)
            # 角格 (0,0) 只能属于一边：两边都占角格时冲突
            lc=any(0 in s for s in L); bc=any(0 in s for s in B)
            if lc and bc: continue
            # 段必须连续
            if not all(s[2]-s[0]==2 for s in L+B): continue
            res.append((gl,gb,[s[1] for s in L],[s[1] for s in B]))
    return res
lay=layouts(); print('排布数',len(lay))
out=[]
for gl,gb,lm,bm in lay:
    ore={(1,y) for y in lm}|{(x,1) for x in bm}
    assert len(ore)==46
    def ok(x0,y0): return x0>=1 and y0>=1 and x0+2<=69 and y0+2<=69 and not any((x0+i,y0+j) in ore for i in range(3) for j in range(3))
    cov=lambda c:any(ok(c[0]-i,c[1]-j) for i in range(3) for j in range(3))
    good=[]
    for y in lm:
        for d in (1,-1):
            if cov((1,y+d)): good.append(((1,y),(0,d)))
    for x in bm:
        for d in (1,-1):
            if cov((x+d,1)): good.append(((x,1),(d,0)))
    out.append((92-len(good),gl,gb,good))
print('最少不能贴的切向方向数',min(o[0] for o in out))
print('可贴方向最多的几种',[(o[1],o[2],o[3]) for o in out if o[0]==min(x[0] for x in out)][:3])
