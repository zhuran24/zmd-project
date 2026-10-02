"""Timestamp packets and named objects. Pure belts and fixed 1-tick recipes."""
class Plant:
    def __init__(self,lengths=(7,13,31,5,5,5),k=2):
        self.t=-1
        self.spec={'C':('plant','seed',2),'A':('seed','plant',1),
                   'B':('seed','plant',1),'K':('plant','powder',k)}
        self.stock={m:0 for m in self.spec};self.out=self.stock.copy()
        self.cache={m:None for m in self.spec};self.on={m:True for m in self.spec}
        self.sink=0
        ends=[('C','A'),('C','B'),('A','C'),('B','K'),('K','sink'),('K','sink')]
        self.routes={n:{'src':s,'dst':d,'cells':[None]*l} for n,l,(s,d) in zip(['CA','CB','AC','BK','K0','K1'],lengths,ends)}
        self.last={r:None for r in self.routes};self.recv={m:None for m in [*self.spec,'sink']}
        self.sent={r:0 for r in self.routes};self.arr=self.sent.copy()
        self.machine_order=['C','A','B','K'];self.route_order=list(self.routes)
    def flush(self,m):
        c=self.cache[m]
        if c is not None and c<=self.t and self.out[m]+self.spec[m][2]<=50:
            self.out[m]+=self.spec[m][2];self.cache[m]=None
    def tail(self,n):
        c=self.routes[n]['cells'][-1]
        return c is not None and self.t-c>=8
    def move(self,n):
        cells=self.routes[n]['cells']
        for j in range(len(cells)-2,-1,-1):
            if cells[j] is not None and cells[j+1] is None and self.t-cells[j]>=8:
                cells[j+1]=self.t;cells[j]=None
    def step(self):
        self.t+=1
        for m in self.spec:self.flush(m)
        used=set()
        for n in self.route_order:
            if n in used:continue
            if not self.tail(n):self.move(n);used.add(n);continue
            dest=self.routes[n]['dst']
            group=[r for r in self.routes if self.routes[r]['dst']==dest]
            last=self.recv[dest]
            if last is not None:
                j=group.index(last)+1;group=group[j:]+group[:j]
            for r in group:
                if r in used:continue
                room=(self.sink if dest=='sink' else self.stock[dest])<50
                if self.tail(r) and room:
                    self.routes[r]['cells'][-1]=None
                    if dest=='sink':self.sink+=1
                    else:self.stock[dest]+=1
                    self.arr[r]+=1;self.recv[dest]=r
                self.move(r);used.add(r)
        for m in self.machine_order:
            routes=[r for r in self.routes if self.routes[r]['src']==m]
            routes.sort(key=lambda r:(-1 if self.last[r] is None else self.last[r],list(self.routes).index(r)))
            for r in routes:
                if self.out[m] and self.routes[r]['cells'][0] is None:
                    self.routes[r]['cells'][0]=self.t;self.out[m]-=1
                    self.last[r]=self.t;self.sent[r]+=1;break
            self.flush(m)
        for m in self.spec:
            if self.on[m] and self.cache[m] is None and self.stock[m]>0:
                self.stock[m]-=1;self.cache[m]=self.t+8
    def state(self):
        return {'stock':self.stock.copy(),'out':self.out.copy(),
          'cache':{m:None if c is None else max(0,c-self.t) for m,c in self.cache.items()},
          'routes':{n:[None if x is None else max(0,8-self.t+x) for x in r['cells']] for n,r in self.routes.items()},
          'sink':self.sink,'sent':self.sent.copy(),'arr':self.arr.copy()}
    def fill(self,route,i):
        assert self.routes[route]['cells'][i] is None
        self.routes[route]['cells'][i]=self.t
    def phi2(self):
        route=sum(sum(c is not None for c in self.routes[r]['cells']) for r in ('CA','AC'))
        return 2*(self.stock['A']+self.stock['C']+self.out['A']+route+sum(self.cache[m] is not None for m in ('A','C')))+self.out['C']

def belt(n,mod,continuous=True):
    cells=[None]*n;seen={};out=0;occupation=0
    for t in range(200000):
        if continuous:
            for i in range(n-2,-1,-1):
                if cells[i] is not None and cells[i+1] is None and t-cells[i]>=8:
                    cells[i]=None;cells[i+1]=t
        if cells[0] is None:cells[0]=t
        if cells[-1] is not None and t-cells[-1]>=8 and (mod==1 or t%mod!=0):
            cells[-1]=None;out+=1
        for i in range(n-2,-1,-1):
            if cells[i] is not None and cells[i+1] is None and t-cells[i]>=8:
                cells[i]=None;cells[i+1]=t
        occupation+=sum(v is not None for v in cells)
        key=(t%mod,tuple(None if c is None else max(0,8-t+c) for c in cells))
        if key in seen:
            s,q,h=seen[key];return {'K':t-s,'Q':out-q,'H':occupation-h}
        seen[key]=(t,out,occupation)
    raise RuntimeError('no cycle')
