# 独立复核「接通先后」再修正版：按规则第22、25-28行逐个建成，记录通道形成次序
from itertools import permutations
D={'N':(0,-1),'E':(1,0),'S':(0,1),'W':(-1,0)}
OPP={'N':'S','S':'N','E':'W','W':'E'}
CW=['N','E','S','W']
def cw_from(d):  # 从 d 起顺时针的其余三边
    i=CW.index(d); return [CW[(i+k)%4] for k in (1,2,3)]
def ports(kind,arg):
    # 返回有序端口表 [(类型,边)]：先存后取；分流/汇流按顺时针
    if kind=='split':  s=arg; return [('in',s)]+[('out',d) for d in cw_from(s)]
    if kind=='merge':  o=arg; return [('in',d) for d in cw_from(o)]+[('out',o)]
    if kind=='belt':   s,o=arg; return [('in',s),('out',o)]
def run(units,order,rejoin=False):
    # units: name->(kind,arg,pos)
    built=set(); chans=[]   # 有序通道表
    def partner(u,pt,side):
        x,y=units[u][2]; dx,dy=D[side]; q=(x+dx,y+dy)
        for v in built:
            if v!=u and units[v][2]==q:
                for pt2,s2 in ports(units[v][0],units[v][1]):
                    if s2==OPP[side] and pt2!=pt:
                        return v
        return None
    for u in order:
        built.add(u)
        new=[]
        for pt,side in ports(units[u][0],units[u][1]):
            v=partner(u,pt,side)
            if v: new.append((u,v) if pt=='out' else (v,u))
        chans+=new
        if rejoin and units[u][0]=='belt':
            # 找出 u 所在连续带段，把两头通到非带单位、且早已存在的通道排到最后
            seg={u}; stack=[u]
            while stack:
                a=stack.pop()
                for c in chans:
                    if a in c:
                        b=c[0] if c[1]==a else c[1]
                        if units[b][0]=='belt' and b not in seg: seg.add(b); stack.append(b)
            ends=[c for c in chans if c not in new and ((c[0] in seg)!=(c[1] in seg))]
            for c in ends: chans.remove(c); chans.append(c)
    return chans
def predict(units,order):
    # 再修正版第一句：接通时刻＝两端中较晚那次建成；同次按新单位端口顺序
    idx={u:i for i,u in enumerate(order)}
    final=run(units,order)  # 只取通道集合
    def key(c):
        late=max(c,key=lambda w:idx[w]); other=c[0] if c[1]==late else c[1]
        po=ports(units[late][0],units[late][1])
        x,y=units[late][2]; ox,oy=units[other][2]
        side=[s for s,(dx,dy) in D.items() if (x+dx,y+dy)==(ox,oy)][0]
        pt='out' if c[0]==late else 'in'
        return (idx[late],po.index((pt,side)))
    return sorted(final,key=key)
# 例一：三出口分流器
U1={'P':('split','N',(0,0)),'E':('split','W',(1,0)),'S':('belt',('N','S'),(0,1)),'W':('belt',('E','W'),(-1,0))}
def exits(ch): return ''.join(c[1] for c in ch if c[0]=='P')
bp=[o for o in permutations(U1) if all(o.index(a)<o.index(b) for a in 'PE' for b in 'SW')]
from collections import Counter
ok=all(run(U1,o)==predict(U1,o) for o in permutations(U1))
print('例一 判据与逐建一致:',ok)
print('同图初建',len(bp),Counter(exits(run(U1,o)) for o in bp))
print('离线',Counter(exits(run(U1,o)) for o in permutations(U1)))
print('P最后',Counter(exits(run(U1,o)) for o in permutations(U1) if o[-1]=='P'))
# 例二：方形
U2={'A':('split','N',(0,0)),'B':('split','W',(1,0)),'D':('split','N',(0,1)),'C':('merge','E',(1,1))}
seqs=set(); allok=True
for o in permutations(U2):
    r=run(U2,o); allok&=(r==predict(U2,o)); seqs.add(tuple(a+b for a,b in r))
print('例二 判据一致:',allok,'不同序数',len(seqs))
names=['AB','AD','BC','DC']
from itertools import combinations
for a,b in combinations(names,2):
    print(a,b,'正',any(s.index(a)<s.index(b) for s in seqs),'反',any(s.index(a)>s.index(b) for s in seqs))
print('AB,DC同占末两位',sum(set(s[2:])=={'AB','DC'} for s in seqs))
# 例三：b1->b2->M 带端重接
U3={'b1':('belt',('W','E'),(0,0)),'b2':('belt',('W','E'),(1,0)),'M':('merge','E',(2,0))}
for o in permutations(U3):
    a=run(U3,o); b=run(U3,o,rejoin=True)
    print(o,a,b,'反转' if a!=b else '')
