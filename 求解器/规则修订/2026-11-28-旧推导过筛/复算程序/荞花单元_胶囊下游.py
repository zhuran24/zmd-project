# 各行从西向东布置。路径穿越只许正交直穿。全机用单独电桩。
from collections import deque,Counter,defaultdict
import random
box={}; spec={}; edges=[]; solid=set(); poles=[]
def put(u,x,y,w,h,di,ins,k=1,d=1):
    box[u]=(x,y,w,h,di)
    spec[u]=(ins,k,d*8)
    for i in range(x,x+w):
        for j in range(y,y+h):
            assert (i,j) not in solid
            solid.add((i,j))
def edge(a,b,i=0):
    edges.append((a,b,i))
for off,p in ((4,'q'),(21,'s')):
    put(p+'C',20,off,5,5,1,[1],2)
    put(p+'A',20,off+7,5,5,-1,[1])
    put(p+'B',31,off,5,5,1,[1])
    put(p+'K',41,off,3,3,1,[1],2 if p=='q' else 3)
    for a,b in [('C','A'),('C','B'),('A','C'),('B','K')]: edge(p+a,p+b)
put('G',49,8,4,6,1,[2,1])
edge('qK','G');edge('qK','G');edge('sK','G',1)
for j in range(4):
    u=str(j); y=36+7*j
    put('O'+u,0,y,1,3,1,[])
    put('R'+u,9,y,3,3,1,[1]);put('P'+u,19,y,3,3,1,[1])
    edge('O'+u,'R'+u);edge('R'+u,'P'+u)
for j in range(2):
    u=str(j); y=38+13*j
    put('M'+u,30,y,4,6,1,[2,1]);put('T'+u,41,y,3,3,1,[1])
    edge('P'+str(2*j),'M'+u);edge('P'+str(2*j+1),'M'+u)
    edge('sK','M'+u,1);edge('M'+u,'T'+u)
put('V',48,34,3,3,1,[2]);edge('T0','V');edge('T1','V')
put('F',57,18,4,6,1,[10,10],1,5);edge('V','F');edge('G','F',1)
put('W',54,0,9,9,1,[]);edge('F','W')
for u,(x,y,w,h,d) in box.items():
    if u.startswith('O') or u=='W': continue
    opts=[(i,j) for i in range(x,x+w) for j in (y-3,y+h+1)]
    for i,j in opts:
        sq={(i+di,j+dj) for di in (0,1) for dj in (0,1)}
        if all(0<=v<70 for pos in sq for v in pos) and not sq&solid:
            solid.update(sq);poles.append((i,j));break
    else: raise ValueError(u)
D=((1,0),(0,1),(-1,0),(0,-1))
def ports(u,send):
    x,y,w,h,di=box[u]
    if u=='W': return [((i,y+h),3) for i in range(x+1,x+8)]
    ds=di if send else -di
    return [((x+w if ds==1 else x-1,j),0 if di==1 else 2)
            for j in ([y+1] if u.startswith('O') else range(y,y+h))]
def route(seed):
    rng=random.Random(seed); used={}; paths={}; order=list(range(len(edges))); rng.shuffle(order)
    for e in order:
        a,b,_=edges[e]; prev={}; q=deque()
        for pos,heading in ports(a,True):
            if pos not in solid and pos not in used:
                st=(pos,heading);prev[st]=None;q.append(st)
        dest=set(ports(b,False)); end=None
        while q:
            st=q.popleft();(x,y),d=st
            if st in dest and (x,y) not in used:
                end=st;break
            for n,(dx,dy) in enumerate(D):
                if (n-d)%4==2 or ((x,y) in used and n!=d):continue
                pos=(x+dx,y+dy)
                if not (0<=pos[0]<70 and 0<=pos[1]<70) or pos in solid:continue
                if pos in used and used[pos]!=1-n%2:continue
                ns=(pos,n)
                if ns not in prev:
                    prev[ns]=st;q.append(ns)
        if end is None:return
        chain=[]
        while end is not None:
            chain.append(end);end=prev[end]
        chain.reverse()
        if len(set(pos for pos,d in chain))!=len(chain): return
        for n,(pos,d) in enumerate(chain):
            out=chain[n+1][1] if n+1<len(chain) else d
            used[pos]=d%2 if 0<n<len(chain)-1 and pos not in used and d==out else -1
        paths[e]=[pos for pos,d in chain]
    return [paths[i] for i in range(len(edges))]
def check(paths):
    uses=Counter(p for chain in paths for p in chain)
    # 外接端口全部核对。桥按方向分格，避免反向格平白接上机器端口。
    tx={};rx={};planned=set()
    for u,(x,y,w,h,di) in box.items():
        if u=='W':
            for i in range(x+1,x+8):
                rx[(i,y+h-1),1]=u
                rx[(i,y),3]=u
            for delta in (1,4,7):
                tx[(x,y+delta),2]=u;tx[(x+w-1,y+delta),0]=u
            continue
        for send in (True,False):
            if u.startswith('O') and not send:continue
            for (ox,oy),hd in ports(u,send):
                if not send:hd=(hd+2)%4
                dx,dy=D[hd]
                (tx if send else rx)[(ox-dx,oy-dy),hd]=u
    for e,(a,b,_) in enumerate(edges):
        chain=paths[e]
        x,y,w,h,di=box[a]; before=(chain[0][0]-di,chain[0][1])
        x,y,w,h,di=box[b]; after=(chain[-1][0]+di,chain[-1][1]) if b!='W' else (chain[-1][0],chain[-1][1]-1)
        seq=[a]
        for j,p in enumerate(chain):
            v=chain[j-1] if j else before
            z=chain[j+1] if j+1<len(chain) else after
            f=D.index((p[0]-v[0],p[1]-v[1]));g=D.index((z[0]-p[0],z[1]-p[1]))
            name=(p,f) if uses[p]>1 else p
            rx[p,(f+2)%4]=name;tx[p,g]=name
            if uses[p]>1:
                assert f==g
                rx[p,f]=(p,(f+2)%4);tx[p,(f+2)%4]=(p,(f+2)%4)
            seq.append(name)
        seq.append(b);planned.update(zip(seq,seq[1:]))
    actual=set()
    for ((x,y),hd),src in tx.items():
        dx,dy=D[hd]; dst=rx.get(((x+dx,y+dy),(hd+2)%4))
        if dst is not None:actual.add((src,dst))
    return actual==planned
for seed in range(1000):
    paths=route(seed)
    if paths and len(paths[0])+len(paths[2])==12 and check(paths):break
else: raise ValueError('route')
print('布线种子、各路格数',seed,[len(p) for p in paths],flush=True)
# 一条独占单行路只须记录下一件可出的步号；满路与空位传播按末端到首端。
def run():
    ins={u:[0]*len(s[0]) for u,s in spec.items()}
    work=Counter();out=Counter(); orders=defaultdict(list)
    for e,(u,v,i) in enumerate(edges):orders[u].append(e)
    lengths=list(map(len,paths))
    # 用逐格进入时间计算成熟与堵塞。
    lanes=[[None]*l for l in lengths]; L=lengths[0]+lengths[2]
    ins['qC'][0]=L+2;ins['qB'][0]=50
    lanes[1]=[-8]*lengths[1]
    # 辅助单元只预装50株砂叶。
    ins['sC'][0]=50
    seen={}; log=[]; warehouse=0
    incoming=defaultdict(list)
    for e,(_,v,_) in enumerate(edges): incoming[v].append(e)
    cursors={v:1%len(g) for v,g in incoming.items()}
    for t in range(500000):
        for v,g in incoming.items():
            z=cursors[v]
            for e in g[z:]+g[:z]:
                u,v,i=edges[e]
                a=lanes[e];last=a[-1]
                if last is not None and t-last>=8 and (v=='W' or ins[v][i]<50):
                    if v=='W':warehouse+=1
                    else:ins[v][i]+=1
                    a[-1]=None
                    cursors[v]=(g.index(e)+1)%len(g)
        for a in lanes:
            for j in range(len(a)-1,0,-1):
                if a[j] is None and a[j-1] is not None and t-a[j-1]>=8:
                    a[j],a[j-1]=t,None
        for u,order in orders.items():
            for e in order.copy():
                if lanes[e][0] is None and (u.startswith('O') or out[u]):
                    lanes[e][0]=t
                    if not u.startswith('O'):out[u]-=1
                    order.remove(e);order.append(e)
        for u,(req,k,d) in spec.items():
            if not req or (u=='qB' and t<9):continue
            if work[u] and work[u]<=t and out[u]+k<=50:
                out[u]+=k;work[u]=0
            if not work[u] and all(a>=b for a,b in zip(ins[u],req)):
                for j,b in enumerate(req):ins[u][j]-=b
                work[u]=t+d
        # 玩家每114步取走全部成品。为周期判据保留取货相位。
        if t%114==0: warehouse=0
        if t==9:
            phi2=2*(sum(x is not None for e in (0,2) for x in lanes[e])+ins['qA'][0]+out['qA']+ins['qC'][0]+bool(work['qA'])+bool(work['qC']))+out['qC']
            print('s、2Φ、门槛的两倍',t,phi2,2*L+5,flush=True)
        log.append(tuple(not work['q'+n] for n in 'CABK')+(work['qK']==t+8, bool(work['qK'] and work['qK']<=t),))
        if t>=10 and t%114==0:
            state=(warehouse,tuple(cursors.values()),tuple((tuple(ins[u]),out[u],max(-1,work[u]-t) if work[u] else None) for u in spec),
                   tuple(tuple(o) for o in orders.values()),tuple(bytes(0 if x is None else 1+min(8,t-x) for x in a) for a in lanes))
            if state in seen:
                z=seen[state];print('完整状态重复',z,t,'四机空缓存步数、K开批数、K等取货空间步数',[sum(row[i] for row in log[z+1:]) for i in range(6)],flush=True);return
            seen[state]=t
    print("末段空缓存", [sum(row[i] for row in log[-11400:]) for i in range(4)])
run()
