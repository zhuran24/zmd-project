"""四机六阶段的局部投影。末端始终能收荞花粉，不模拟实现该边界的整厂。"""
lengths=(7,5,7,5,1,1)  # CA,CB,AC,BK,两路粉末
lanes=[[0]*m for m in lengths] # 0 空，1..9 占用，到9成熟
raw=[sum((lengths[0],lengths[2]))+2,0,50,0] # C,A,B,K
out=[0]*4
work=[0]*4 # 0 空，1..8 制造，9 已到期
batch=[2,1,1,2]
# 调试时B关机、CB已灌满。C预存L+2株。其余机开机。
lanes[1]=[9]*lengths[1]
orders=[[0,1],[2],[3],[4,5]]
seen={}
history=[]
for step in range(100000):
    active=[True,True,step>=9,True]
    for j,dst in enumerate((1,2,0,3,-1,-1)):
        lane=lanes[j]
        if lane[-1]==9 and (dst<0 or raw[dst]<50):
            lane[-1]=0
            if dst>=0: raw[dst]+=1
        for i in range(len(lane)-1,0,-1):
            if not lane[i] and lane[i-1]==9:
                lane[i],lane[i-1]=1,0
    for src,order in enumerate(orders):
        for j in order.copy():
            if not lanes[j][0] and out[src]:
                out[src]-=1
                lanes[j][0]=1
                order.remove(j)
                order.append(j)
    for i,k in enumerate(batch):
        if work[i]==9 and out[i]+k<=50:
            out[i]+=k
            work[i]=0
        if not work[i] and raw[i] and active[i]:
            raw[i]-=1
            work[i]=1
    phi2=2*(sum(bool(x) for j in (0,2) for x in lanes[j])+raw[1]+out[1]+raw[0]+bool(work[0])+bool(work[1]))+out[0]
    if step==9: print('s、2Φ、门槛的两倍',step,phi2,2*(lengths[0]+lengths[2])+5)
    state=(tuple(raw),tuple(out),tuple(work),*(tuple(o) for o in orders),*(tuple(l) for l in lanes))
    if step>9 and state in seen:
        cycle=history[seen[state]:step]
        print('周期起始、步数、各机空缓存步数',seen[state],len(cycle),[sum(not row[i] for row in cycle) for i in range(4)])
        break
    seen[state]=step
    history.append(work.copy())
    for lane in lanes:
        for i,x in enumerate(lane):
            if x: lane[i]=min(9,x+1)
    for i,x in enumerate(work):
        if x and active[i]: work[i]=min(9,x+1)
else:
    raise ValueError('没有找到周期')
