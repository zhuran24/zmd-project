"""Independent four-machine step implementations, created for review 102H.

Absolute stores item-entry and manufacture-completion timestamps. Countdown
stores capped item ages, remaining work, and explicit polling queues. Neither
imports sim2, derivation code, or another review implementation.
"""
from copy import deepcopy

NAMES = ('C','A','B','K')
ENDS = ((0,1),(1,0),(0,2),(2,3))  # CA, AC, CB, BK

class Absolute:
    def __init__(self, initial, k, n):
        self.k, self.n = k,n
        self.yields = [2,1,1,k]
        self.m = deepcopy(initial['machines']) # [input,output,completion time/None]
        self.roads = [[None if a is None else -a for a in r] for r in initial['roads']]
        self.outlets = [None if a is None else -a for a in initial.get('outlets',[None]*n)]
        self.last = [[None,None],[],[],[None]*n]
        self.order = [[0,1],[],[],list(range(n))]
        self.events=[]
        self.starts=[0]*4
        self.delivered=0

    def flush(self, i,t):
        inp,out,finish=self.m[i]
        if finish is not None and finish<=t and out+self.yields[i]<=50:
            self.m[i][1]+=self.yields[i]
            self.m[i][2]=None

    def choose(self,i,ready):
        key=lambda j: (0,self.order[i].index(j)) if self.last[i][j] is None else (1,self.last[i][j])
        return next((j for j in sorted(range(len(ready)),key=key) if ready[j]),None)

    def step(self,t,setting):
        if setting['offline']:
            self.order[0]=setting['c_order'][:]
            self.order[3]=setting['k_order'][:]
            if setting['clear']:
                self.last[0]=[None,None]
                self.last[3]=[None]*self.n
        enabled=setting.get('enabled',[True]*4)
        # Pause is allowed only for B/K in bound checks.
        for i in range(4):
            if not enabled[i] and self.m[i][2] is not None and self.m[i][2]>=t:
                self.m[i][2]+=1
            self.flush(i,t)
        for j,x in enumerate(self.outlets):
            if x is not None and t-x>=8 and setting['drain'][j]:
                self.outlets[j]=None
                self.delivered+=1
        for r,(_,dest) in enumerate(ENDS):
            row=self.roads[r]
            for pos in range(len(row)-1,-1,-1):
                entry=row[pos]
                if entry is None or t-entry<8:
                    continue
                if pos==len(row)-1:
                    if self.m[dest][0]<50:
                        self.m[dest][0]+=1
                        row[pos]=None
                elif row[pos+1] is None:
                    row[pos+1]=t
                    row[pos]=None
        sent=[]
        for i in setting['machine_order']:
            if self.m[i][1]==0:
                continue
            if i==0:
                j=self.choose(0,[self.roads[0][0] is None,self.roads[2][0] is None])
                if j is None: continue
                self.roads[0 if j==0 else 2][0]=t
                self.last[0][j]=t
                sent.append('A' if j==0 else 'B')
            elif i in (1,2):
                r=1 if i==1 else 3
                if self.roads[r][0] is not None: continue
                self.roads[r][0]=t
            else:
                j=self.choose(3,[v is None for v in self.outlets])
                if j is None: continue
                self.outlets[j]=t
                self.last[3][j]=t
            self.m[i][1]-=1
            self.flush(i,t)
        for i in range(4):
            if enabled[i] and self.m[i][2] is None and self.m[i][0]>=1:
                self.m[i][0]-=1
                self.m[i][2]=t+8
                self.starts[i]+=1
        for word in sent:
            self.events.append((t,word))
        return sent

    def canonical(self,t):
        machines=[[a,b,None if c is None else max(0,c-t)] for a,b,c in self.m]
        roads=[[None if x is None else min(8,t-x) for x in r] for r in self.roads]
        outs=[None if x is None else min(8,t-x) for x in self.outlets]
        ranks=[]
        for i in (0,3):
            ranks.append(sorted(range(len(self.last[i])),key=lambda j:(0,self.order[i].index(j))
                                if self.last[i][j] is None else (1,self.last[i][j])))
        return [machines,roads,outs,ranks,self.starts,self.delivered]

    def phi2(self):
        return (2*(sum(v is not None for v in self.roads[0])+self.m[1][0]+self.m[1][1]
                 +sum(v is not None for v in self.roads[1])+self.m[0][0]
                 +sum(self.m[i][2] is not None for i in (0,1)))+self.m[0][1])

class Countdown:
    def __init__(self, initial,k,n):
        self.n=n
        self.product=dict(zip(NAMES,[2,1,1,k]))
        self.inventory={name:{'raw':v[0],'finished':v[1],'work':v[2]}
                        for name,v in zip(NAMES,initial['machines'])}
        self.lanes={name:list(row) for name,row in zip(['CA','AC','CB','BK'],initial['roads'])}
        self.exits=initial.get('outlets',[None]*n)[:]
        self.unused={'C':[0,1],'K':list(range(n))}
        self.used={'C':[],'K':[]}
        self.starts=dict.fromkeys(NAMES,0)
        self.delivered=0

    def move_ready_batch(self,name):
        m=self.inventory[name]
        if m['work']==0 and m['finished']<=50-self.product[name]:
            m['finished']+=self.product[name]
            m['work']=None

    def step(self,t,setting):
        if setting['offline']:
            for name,perm in [('C',setting['c_order']),('K',setting['k_order'])]:
                if setting['clear']:
                    self.unused[name]=list(perm)
                    self.used[name]=[]
                else:
                    self.unused[name]=[j for j in perm if j in self.unused[name]]
        enabled=dict(zip(NAMES,setting.get('enabled',[True]*4)))
        for name,m in self.inventory.items():
            if m['work'] is not None and m['work']>0 and enabled[name]:
                m['work']-=1
            self.move_ready_batch(name)
        for row in list(self.lanes.values())+[self.exits]:
            for j in range(len(row)):
                if row[j] is not None:
                    row[j]=min(8,row[j]+1)
        for j in range(self.n):
            if self.exits[j]==8 and setting['drain'][j]:
                self.exits[j]=None
                self.delivered+=1
        # Work backwards from the endpoint; this is one belt component's step.
        for lane,dest in [('CA','A'),('AC','C'),('CB','B'),('BK','K')]:
            row=self.lanes[lane]
            if row[-1]==8 and self.inventory[dest]['raw']<50:
                self.inventory[dest]['raw']+=1
                row[-1]=None
            for pos in reversed(range(len(row)-1)):
                if row[pos]==8 and row[pos+1] is None:
                    row[pos+1]=0
                    row[pos]=None
        sent=[]
        for idx in setting['machine_order']:
            name=NAMES[idx]
            m=self.inventory[name]
            if not m['finished']: continue
            if name in ('A','B'):
                row=self.lanes['AC' if name=='A' else 'BK']
                if row[0] is not None: continue
                row[0]=0
            else:
                options=self.unused[name]+self.used[name]
                available=(lambda j:self.lanes['CA' if j==0 else 'CB'][0] is None) if name=='C' else (lambda j:self.exits[j] is None)
                picked=next((j for j in options if available(j)),None)
                if picked is None: continue
                if picked in self.unused[name]: self.unused[name].remove(picked)
                else: self.used[name].remove(picked)
                self.used[name].append(picked)
                if name=='C':
                    self.lanes['CA' if picked==0 else 'CB'][0]=0
                    sent.append('A' if picked==0 else 'B')
                else: self.exits[picked]=0
            m['finished']-=1
            self.move_ready_batch(name)
        for name,m in self.inventory.items():
            if enabled[name] and m['work'] is None and m['raw']:
                m['raw']-=1
                m['work']=8
                self.starts[name]+=1
        return sent

    def canonical(self,t):
        m=[[self.inventory[n][f] for f in ['raw','finished','work']] for n in NAMES]
        return [m,list(self.lanes.values()),self.exits,
                [self.unused[n]+self.used[n] for n in ('C','K')],list(self.starts.values()),self.delivered]

    def phi2(self):
        m=self.inventory
        return sum([2*sum(a is not None for a in self.lanes['CA']),2*m['A']['raw'],2*m['A']['finished'],
                    2*sum(a is not None for a in self.lanes['AC']),2*m['C']['raw'],
                    2*int(m['A']['work'] is not None),2*int(m['C']['work'] is not None),m['C']['finished']])
