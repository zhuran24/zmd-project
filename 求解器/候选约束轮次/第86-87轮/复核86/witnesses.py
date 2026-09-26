"""Independent repeat-state and coordinate certificates for the two defects."""
import json
import os
from pathlib import Path
from dynamics import Net,plant,phi2

HERE=Path(__file__).resolve().parent
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
DIR={(1,0):'E',(-1,0):'W',(0,1):'N',(0,-1):'S'}
VEC={v:k for k,v in DIR.items()}
OPP={'E':'W','W':'E','N':'S','S':'N'}


class Layout:
    def __init__(self): self.units={};self.expected=set()
    def rect(self,name,x,y,w,h,kind='machine'):
        ports={}
        if kind in ('machine','box'):
            for j in range(y,y+h):
                ports[(x,j,'W')]='i';ports[(x+w-1,j,'E')]='o'
        self.units[name]=dict(cells={(i,j) for i in range(x,x+w) for j in range(y,y+h)},ports=ports,kind=kind)
    def special(self,name,p,ports,kind):
        self.units[name]=dict(cells={p},ports={(p[0],p[1],d):mode for d,mode in ports.items()},kind=kind)
    def path(self,label,start,points,end):
        # endpoint tuples: (unit, endpoint cell). Points are distinct transport cells.
        full=[start[1]]+points+[end[1]]
        names=[start[0]]+[label+str(i) for i in range(len(points))]+[end[0]]
        for i,p in enumerate(points):
            prev,nxt=full[i],full[i+2]
            di=DIR[(prev[0]-p[0],prev[1]-p[1])]
            do=DIR[(nxt[0]-p[0],nxt[1]-p[1])]
            self.special(names[i+1],p,{di:'i',do:'o'},'belt')
        for a,b in zip(names,names[1:]):self.expected.add((a,b))
    def check(self):
        occupancy={}
        for name,u in self.units.items():
            for p in u['cells']:
                assert 0<=p[0]<70 and 0<=p[1]<70,(name,p)
                assert p not in occupancy,(name,occupancy.get(p),p)
                occupancy[p]=name
        actual=set()
        for name,u in self.units.items():
            for (x,y,d),mode in u['ports'].items():
                dx,dy=VEC[d];p=(x+dx,y+dy)
                other=occupancy.get(p)
                if other is None:continue
                v=self.units[other]
                opposite=v['ports'].get((*p,OPP[d]))
                if mode=='o' and opposite=='i' and (u['kind'] in ('belt','gate','split','merge') or v['kind'] in ('belt','gate','split','merge')):
                    actual.add((name,other))
        assert actual==self.expected,(sorted(actual-self.expected),sorted(self.expected-actual))
        poles=[u for u in self.units.values() if u['kind']=='pole']
        powered={}
        for name,u in self.units.items():
            if u['kind']!='machine':continue
            coverage=False
            for p in poles:
                cx=min(x for x,y in p['cells'])+1;cy=min(y for x,y in p['cells'])+1
                coverage |= any(cx-6<=x+0.5<cx+6 and cy-6<=y+0.5<cy+6 for x,y in u['cells'])
            assert coverage,name
            powered[name]=coverage
        return dict(units={name:dict(kind=u['kind'],cells=sorted(u['cells']),
                                   ports=[[x,y,d,m] for (x,y,d),m in u['ports'].items()]) for name,u in self.units.items()},
                    channels=sorted(actual),powered=powered,unit_count=len(self.units),
                    transport_count=sum(u['kind'] in ('belt','gate','split','merge') for u in self.units.values()))


def gate_witness():
    n=Net()
    n.machine('Y',{'powder':1},'block')
    n.machine('X',{'block':1},'powder')
    n.link('Y','X','block',1,quota=1)
    n.link('X','Y','powder',15)
    n.m['Y']['stock']['powder']=50
    n.m['Y']['output']=50
    n.m['Y']['cache']=0
    n.close()
    seen={};trace=[]
    for t in range(200):
        n.t=t;n.close()
        line=n.lines[0]
        closed=n.m['Y']['output']>0 and not (line['window'] is None or t-line['window']>=5 or line['used']<1)
        row=dict(t=t,Y_stock=n.m['Y']['stock']['powder'],Y_output=n.m['Y']['output'],
                 Y_cache=None if n.m['Y']['cache'] is None else max(0,n.m['Y']['cache']-t),
                 X_stock=n.m['X']['stock']['block'],X_output=n.m['X']['output'],
                 X_cache=None if n.m['X']['cache'] is None else max(0,n.m['X']['cache']-t),
                 gate_temporarily_disconnected=closed,starts=dict(n.starts),state=n.key())
        trace.append(row)
        key=n.key()
        if key in seen:
            s=seen[key];cycle=trace[s:t]
            assert t-s==5 and all(r['Y_cache'] is not None for r in cycle)
            assert sum(r['X_cache'] is None for r in cycle)==4
            assert n.starts['Y']-trace[s]['starts'].get('Y',0)==1
            break
        seen[key]=t
    g=Layout();g.rect('Y',10,10,3,3);g.rect('X',14,10,3,3)
    g.rect('P',11,7,2,2,'pole');g.rect('core',50,50,9,9,'core')
    g.special('G',(13,11),{'W':'i','E':'o'},'gate')
    g.expected|={('Y','G'),('G','X')}
    ret=[(17,11),(18,11),(18,12),(18,13)]+[(x,13) for x in range(17,8,-1)]+[(9,12),(9,11)]
    assert len(ret)==15
    g.path('return',('X',(16,11)),ret,('Y',(10,11)))
    return dict(period=[s,t],period_trace=cycle,geometry=g.check(),
                item_mapping={'powder':'蓝铁粉末','block':'蓝铁块'},
                setup='Y stock 50 powder, output 50 block, completed cache; X and paths empty. Close t=0; then no intervention.')


def merger_witness():
    g=Layout()
    for name,x,y,w,h in [('C',10,10,5,5),('A',20,10,5,5),('B',20,1,5,5),('K',28,1,3,3)]:g.rect(name,x,y,w,h)
    g.rect('Z',36,1,3,3,'box');g.rect('P1',15,17,2,2,'pole');g.rect('P2',25,5,2,2,'pole')
    g.rect('core',50,50,9,9,'core')
    ca=[(x,11) for x in range(15,20)]
    ac=[(25,13),(26,13),(26,14),(26,15),(26,16)]+[(x,16) for x in range(25,7,-1)]+[(8,y) for y in (15,14,13)]+[(9,13)]
    cb=[(15,10),(16,10)]+[(16,y) for y in range(9,2,-1)]+[(17,3),(18,3),(19,3)]
    bk=[(25,3),(26,3),(27,3)]
    g.path('CA',('C',(14,11)),ca,('A',(20,11)))
    g.path('AC',('A',(24,13)),ac,('C',(10,13)))
    g.path('CB',('C',(14,10)),cb,('B',(20,3)))
    g.path('BK',('B',(24,3)),bk,('K',(28,3)))
    g.special('M',(31,2),{'W':'i','N':'i','S':'i','E':'o'},'merge')
    g.special('D',(31,3),{'N':'i','S':'o','E':'o','W':'o'},'split')
    g.expected|={('K','M'),('D','M')}
    mz=[(x,2) for x in range(32,36)]
    zd=[(39,2),(40,2),(41,2),(41,3),(41,4),(41,5)]+[(x,5) for x in range(40,30,-1)]+[(31,4)]
    g.path('MZ',('M',(31,2)),mz,('Z',(36,2)))
    g.path('ZD',('Z',(38,2)),zd,('D',(31,3)))
    geo=g.check()
    # Execute the actual bypass channels. Items received at t mature at t+1.
    bypass={name for name in g.units if name in ('M','D') or name.startswith(('MZ','ZD'))}
    ready={name:1 for name in bypass}
    stock=49;trace=[];K_output=50
    edges=[(a,b) for a,b in g.expected if a in bypass|{'Z','K'} and b in bypass|{'Z'}]
    edges.sort()
    for t in range(1,7):
        transfers={};m_empties=False
        while True:
            changed=False
            for a,b in edges:
                available=(stock>0 if a=='Z' else K_output>0 if a=='K' else ready[a] is not None and ready[a]<=t)
                room=stock<50 if b=='Z' else ready[b] is None
                if not available or not room:continue
                if b=='M' and a=='K' and ready['D'] is not None and ready['D']<=t:
                    continue # M grants the higher direct-splitter inventory grade.
                if a=='Z':stock-=1
                elif a=='K':K_output-=1
                else:
                    ready[a]=None
                    if a=='M':m_empties=True
                if b=='Z':stock+=1
                else:ready[b]=t+1
                transfers[(a,b)]=transfers.get((a,b),0)+1
                changed=True
            if not changed:break
        assert stock==49 and K_output==50 and all(v==t+1 for v in ready.values())
        assert transfers.get(('D','M'))==1 and transfers.get(('K','M'),0)==0 and m_empties
        trace.append(dict(t=t,Z_stock=stock,M_was_empty=m_empties,
                          D_to_M=transfers.get(('D','M'),0),K_to_M=transfers.get(('K','M'),0),
                          all_bypass_cells_occupied=True,all_bypass_ages_after_settlement=0,
                          successful_moves=[[a,b,n] for (a,b),n in sorted(transfers.items())]))
    return dict(lengths=[len(ca),len(ac),len(cb),len(bk)],phi=str(len(ca)+len(ac)+177),
                period=1,trace=trace,geometry=geo,
                initial='Four machines: stock=50, output=50, correct completed cache; internal plant paths mature and full. Z has 49 flower powder, wireless off. Bypass slots full, one-tick residence between successive settlements.',
                priority='D -> M is a direct-splitter input grade, connected earlier than the ordinary K -> M grade.')


def boundary_check():
    n=plant()
    n.m['C']['output']=2
    n.m['C']['pointer']=1
    n.lines[0]['cells'][0]=1
    before=phi2(n)
    n.close();settled=phi2(n)
    n.t=1;n.close();later=phi2(n)
    assert (before,settled,later)==(4,3,2)
    return dict(before_settlement_phi2=before,settled_phi2=settled,at_tick1_phi2=later,
                note='Only a boundary-convention test. No claim that an imprecise player selects an intermediate zero-time judgement as the release state.')


if __name__=='__main__':
    data=dict(gate=gate_witness(),merger=merger_witness(),unsettled_boundary=boundary_check())
    (HERE/'witnesses.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:dict(period=v['period'],units=v['geometry']['unit_count'],
                             transport=v['geometry']['transport_count']) for k,v in data.items() if 'geometry' in v},ensure_ascii=False))
