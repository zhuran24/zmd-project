"""Independent array/countdown model; no timestamp engine or sim2 imports."""
class Plant:
    def __init__(self,lengths=(7,13,31,5,5,5),k=2):
        # C,A,B,K indices 0,1,2,3; sink index 4.
        self.names=['C','A','B','K'];self.labels=['CA','CB','AC','BK','K0','K1']
        self.inputs=[0]*4;self.outputs=[0]*4;self.timer=[-1]*4;self.enabled=[True]*4
        self.produce=[2,1,1,k];self.src=[0,0,1,2,3,3];self.dst=[1,2,0,3,4,4]
        self.paths=[[-1]*l for l in lengths];self.success=[-1]*6;self.turn=[-1]*5
        self.delivered=[0]*6;self.dispatched=[0]*6;self.hold=0;self.clock=-1
        self.order=list(range(6));self.morder=list(range(4))
    def flush(self,i):
        if self.timer[i]==0 and self.outputs[i]+self.produce[i]<=50:
            self.outputs[i]+=self.produce[i];self.timer[i]=-1
    def step(self):
        self.clock+=1
        self.timer=[max(0,v-1) if v>=0 else -1 for v in self.timer]
        self.paths=[[max(0,v-1) if v>=0 else -1 for v in p] for p in self.paths]
        for i in range(4):self.flush(i)
        done=[False]*6
        def advance(j):
            p=self.paths[j]
            for i in reversed(range(1,len(p))):
                if p[i]==-1 and p[i-1]==0:p[i]=8;p[i-1]=-1
        for j in self.order:
            if done[j]:continue
            if self.paths[j][-1]!=0:
                advance(j);done[j]=True;continue
            d=self.dst[j];group=[i for i in range(6) if self.dst[i]==d]
            if self.turn[d] in group:
                at=group.index(self.turn[d]);group=group[at+1:]+group[:at+1]
            for i in group:
                if done[i]:continue
                available=(self.hold if d==4 else self.inputs[d])<50
                if self.paths[i][-1]==0 and available:
                    self.paths[i][-1]=-1
                    if d==4:self.hold+=1
                    else:self.inputs[d]+=1
                    self.delivered[i]+=1;self.turn[d]=i
                advance(i);done[i]=True
        for i in self.morder:
            available=[j for j in range(6) if self.src[j]==i and self.paths[j][0]==-1]
            if self.outputs[i] and available:
                j=min(available,key=lambda q:(self.success[q],q))
                self.outputs[i]-=1;self.paths[j][0]=8;self.success[j]=self.clock;self.dispatched[j]+=1
            self.flush(i)
        for i in range(4):
            if self.enabled[i] and self.timer[i]==-1 and self.inputs[i]:
                self.inputs[i]-=1;self.timer[i]=8
    def state(self):
        return {'stock':dict(zip(self.names,self.inputs)),'out':dict(zip(self.names,self.outputs)),
          'cache':{n:(None if c<0 else c) for n,c in zip(self.names,self.timer)},
          'routes':{n:[None if x<0 else x for x in p] for n,p in zip(self.labels,self.paths)},
          'sink':self.hold,'sent':dict(zip(self.labels,self.dispatched)),'arr':dict(zip(self.labels,self.delivered))}
    def phi2(self):
        # Separate ledger evaluation of every contributing storage location.
        ledger=[(self.inputs[1],2),(self.inputs[0],2),(self.outputs[1],2),(self.outputs[0],1),
                (int(self.timer[1]>=0),2),(int(self.timer[0]>=0),2)]
        ledger.extend((sum(v>=0 for v in self.paths[j]),2) for j in (0,2))
        return sum(n*w for n,w in ledger)

def belt(n,mod,continuous=True):
    # Reversed orientation: slot zero is the downstream tail.
    road=[-1]*n;history={};events=0;occupied=0
    for t in range(200000):
        road=[max(0,x-1) if x>=0 else -1 for x in road]
        if continuous:
            for i in range(n-1):
                if road[i]<0 and road[i+1]==0:road[i]=8;road[i+1]=-1
        if road[-1]<0:road[-1]=8
        if road[0]==0 and (mod==1 or t%mod):road[0]=-1;events+=1
        for i in range(n-1):
            if road[i]<0 and road[i+1]==0:road[i]=8;road[i+1]=-1
        occupied+=len(road)-road.count(-1)
        signature=(tuple(road),t%mod)
        previous=history.get(signature)
        if previous is not None:
            return {'K':t-previous[0],'Q':events-previous[1],'H':occupied-previous[2]}
        history[signature]=(t,events,occupied)
    raise RuntimeError('no cycle')
