import itertools, random
# (1) 每口相邻两件至少隔 8 步，40 步连续窗（传输后第 1..40 步的阶段 2）最多几件
def maxin(win,gap=8):
    best=0
    for start in range(gap):
        best=max(best,len(range(start,win,gap)))
    return best
print("40步窗每口最多",maxin(40),"三口",3*maxin(40),"; 41步窗",maxin(41))
# (2) 模拟：6格每格50，存放最小可放格，取货最小非空格；传输每40步(阶段4)；
#     仓库对成品 accept(t)= 全收 / 全拒 / 部分收；x 永远拒收
def run(seed,mode):
    R=random.Random(seed)
    cells=[['x',R.randint(1,50)]]+[[None,0] for _ in range(5)]
    # 初始后格随机放成品
    for i in range(1,6):
        if R.random()<0.5: cells[i]=[R.choice('AB'),R.randint(1,50)]
    stopped_since_clear=True; ref=cells[0][1]; viol=0; blocked_after_clear=0; twocell=0; cleared=False
    last=[-99]*3; cd=R.randint(0,40); T=4000
    wh_room={'A':10**9,'B':10**9}
    for t in range(T):
        # 阶段2 到货
        for p in range(3):
            if t-last[p]>=8 and R.random()<0.6:
                it=R.choice('AAB') if R.random()<0.7 else 'x'
                if it=='x' and ref>=50: continue   # 来路保证逐事件界
                placed=False
                for c in cells:
                    if (c[0]==it and c[1]<50) or c[0] is None:
                        c[0]=it;c[1]+=1;placed=True;break
                if placed:
                    last[p]=t
                    if it=='x': ref+=1
                elif it!='x' and cleared and stopped_since_clear==False: blocked_after_clear+=1
        # 阶段4 取货 x（下游取，保证 ref>=2 才取）与传输
        for _ in range(3):
            if ref>=2 and R.random()<0.3:
                c=next(c for c in cells if c[1]>0)
                if c[0]!='x': viol+=1
                c[1]-=1; ref-=1
                if c[1]==0: c[0]=None
        if cd==0:
            # 仓库状态
            if mode=='full': room={'A':10**9,'B':10**9}
            elif mode=='partial': room={'A':R.randint(0,8),'B':R.randint(0,8)}
            full_accept=True
            for c in cells:
                if c[0] in ('A','B'):
                    k=min(c[1],room[c[0]]); room[c[0]]-=k; c[1]-=k
                    if c[1]>0: full_accept=False
                    if c[1]==0: c[0]=None
            if full_accept: cleared=True; stopped_since_clear=False
            else: stopped_since_clear=True
            cd=40
        cd-=1
        # x 只在第1格
        for i,c in enumerate(cells):
            if c[0]=='x' and i!=0: viol+=1
        kinds=[c[0] for c in cells if c[0] in ('A','B')]
        if cleared and not stopped_since_clear and len(kinds)!=len(set(kinds)): twocell+=1
    return viol,blocked_after_clear,twocell,cells
stopped_since_clear=True
tot=[0,0,0]
for s in range(2000):
    stopped_since_clear=True
    v,b,tw,_=run(s,'full'); tot[0]+=v; tot[1]+=b; tot[2]+=tw
print("全收：x越格/取到非x",tot[0],"全清后被挡",tot[1],"同种两格",tot[2])
# (3) 部分收（每次传输收一些但收不完，不是一件不收）时后格会不会被挡
cnt=0
for s in range(200):
    _,_,_,cells=run(s,'partial')
    if all(c[0] is not None and (c[0]=='x' or c[1]==50) for c in cells): cnt+=1
print("部分收200条里末态后五格全满（会挡成品）",cnt)
