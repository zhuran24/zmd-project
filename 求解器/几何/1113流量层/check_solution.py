#!/usr/bin/env python3
"""Direct integer checker of exported geometry/flows, independent of CP rows.

Does not import model builders. Checks the actual exported witness, including
capacity and axis conservation, without relying on a solver status string.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DIR = [(1,0),(0,1),(-1,0),(0,-1)]
OPP = [2,3,0,1]
COUNTS = {'crush':68,'refine':51,'parts':6,'mold':6,'plant':32,
          'seed':16,'grind':32,'pack':3,'fill':3}
BOUNDS = {'crush':(20,20,20,60),'refine':(20,20,20,20),'parts':(20,20,20,20),
          'mold':(0,40,0,20),'plant':(20,20,20,20),'seed':(20,20,40,40),
          'grind':(0,60,0,20),'pack':(100,100,4,4),'fill':(0,80,0,4)}
TOTAL = {'crush':(1360,1890),'refine':(1020,1020),'parts':(120,120),'mold':(220,110),
         'plant':(640,640),'seed':(320,640),'grind':(1890,630),'pack':(300,12),'fill':(220,11)}


def footprint(r):
    x,y,w,h=r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}


def face(r,axis,side,offsets=None):
    x,y,w,h=r
    if axis == 0:
        return [((x-1 if side==0 else x+w,y+i),0 if side==0 else 2)
                for i in (range(h) if offsets is None else offsets)]
    return [((x+i,y-1 if side==0 else y+h),1 if side==0 else 3)
            for i in (range(w) if offsets is None else offsets)]


def pattern(i):
    gl,gb=([(0,k) for k in range(24)]+[(k,0) for k in range(1,24)])[i]
    body=set(); ports=[]
    for axis,g in [(0,gl),(1,gb)]:
        starts=[3*k+(k>=g) for k in range(23)]
        for s in starts:
            body |= footprint((0,s,1,3) if axis==0 else (s,0,3,1))
            ports.append(((1,s+1),2) if axis==0 else ((s+1,1),3))
    return body,ports


def check(res):
    s=res['solution']; R=footprint(res['rect']); T=set(map(tuple,s['transport'])); B=set(map(tuple,s['bridges']))
    errors=[]
    def require(cond,message):
        if not cond: errors.append(message)
    require(len(T)==len(s['transport']),'duplicate transport')
    require(B<=T,'bridge outside transport')
    body,wh=pattern(s['warehouse_pattern'])
    require(len(body)==138 and len(wh)==46 and len(set(wh))==46,'warehouse construction')
    occupied=set(body)|R
    structural=set(); poles=[]; core=[]; generic=Counter()
    for p in s['placements']:
        k,r,a=p['kind'],p['rect'],p['axis']; c=footprint(r)
        expected_shapes={'small':[(3,3)],'medium':[(5,5)],'large':[(6,4),(4,6)],'core':[(9,9)],'pole':[(2,2)]}
        require(k in expected_shapes and tuple(r[2:]) in expected_shapes.get(k,[]),'body dimensions')
        if k!='pole':require(a in (0,1),'port axis')
        if k=='large':require((tuple(r[2:]),a) in [((6,4),1),((4,6),0)],'large long-edge ports')
        require(all(0<=x<70 and 0<=y<70 for x,y in c),'body outside board')
        require(not(occupied&c),f'body overlaps {p}')
        occupied |= c; structural |= c; generic[k]+=1
        if k in ('small','medium','large'):
            require(all(any(pt in T and min(pt)>=1 for pt,d in face(r,a,j)) for j in (0,1)),f'adjacency {p}')
        if k=='pole': poles.append(r)
        if k=='core': core.append(p)
    require(generic==Counter(small=131,medium=48,large=38,core=1,pole=s['P']),'generic counts')
    require(not(occupied&T),'transport overlaps occupied')
    require(all(0<=x<70 and 0<=y<70 for x,y in T),'transport outside board')
    require(10<=len(poles)<=12,'P range')
    for p in s['placements']:
        if p['kind'] not in ('small','medium','large'): continue
        require(any(footprint(p['rect']) & {(x,y) for x in range(px-5,px+7) for y in range(py-5,py+7)}
                    for px,py,_,_ in poles),f'unpowered {p}')
    q=({(0,k) for k in range(70)}|{(k,0) for k in range(70)})-body
    require(len(q)==1,'boundary gap')
    require(len(T)>=208+int(bool(q&T)),'transport lower bound')
    require(len(T)+len(B)>=306,'transport+bridge lower bound')
    J=sum(x in (1,68) or y in (1,68) for x,y,_,_ in poles)
    require(J==s['J'] and len(poles)==s['P'],'P/J export')
    a,b,w,h=res['rect']
    X=sum((c not in structural and c not in R) for c in [(69,k) for k in range(1,69)]+[(k,69) for k in range(1,69)])
    if (69,69) not in R and not any((69,69) in footprint(p) for p in poles): X+=2
    ring=[(a-1,k) for k in range(b,b+h)]+[(k,b-1) for k in range(a,a+w)]
    if a+w<70: ring += [(a+w,k) for k in range(b,b+h)]
    if b+h<70: ring += [(k,b+h) for k in range(a,a+w)]
    Y=sum(c not in structural for c in ring)
    require((X,Y)==(s['X'],s['Y']),'X/Y export')
    if res['cut_mode']=='formal':
        require(16*len(poles)-2*J+X+Y<=187,'area-gap cut')
        require(9*J<=23*len(poles)-217,'edge-power cut')
        loss=0
        for x,y,_,_ in poles:
            e=int(x in (1,68))+int(y in (1,68)); v=[0,9,15][e]
            if b<=y-5 and y+7<=b+h:
                g=a-x-2 if x+2<=a else x-a-w
                if 0<=g<=6: v=max(v,[10,9,9,6,5,4,1][g])
            if a<=x-5 and x+7<=a+w:
                g=b-y-2 if y+2<=b else y-b-h
                if 0<=g<=6: v=max(v,[10,9,9,6,5,4,1][g])
            loss+=v
        require(loss<=23*len(poles)-217,'pole-loss cut')
    require(len(core)==1,'core count')
    if len(core)!=1: return dict(ok=False,errors=errors)
    c=core[0];r=c['rect'];ax=c['axis']
    co={e for side in (0,1) for e in face(r,ax,side,[1,4,7])}
    ci={e for side in (0,1) for e in face(r,1-ax,side,range(1,8))}
    require(all(pt in T for pt,d in co),'core output adjacency')
    require(sum(pt in T for pt,d in ci)>=2,'core input adjacency')
    require(r[0]>=2 and r[1]>=2 and not(r[0]<=3 and r[1]<=3),'core corner cut')
    if res['cut_mode']=='formal':
        ml=sum(r[1]<=pt[1]<r[1]+9 for pt,d in wh if d==2)
        mb=sum(r[0]<=pt[0]<r[0]+9 for pt,d in wh if d==3)
        require(ml+3*(ax==0)<=(1 if r[1]==61 else 2)*(r[0]-1),'core left corridor')
        require(mb+3*(ax==1)<=(1 if r[0]==61 else 2)*(r[1]-1),'core bottom corridor')
    ass=s['assignments']; acount=Counter(p['kind'] for p in ass)
    expected=COUNTS if res['layer']=='all' else {'crush':68,'refine':51}
    require(acount==expected,'type counts')
    require(len({(tuple(p['rect']),p['axis']) for p in ass})==len(ass),'duplicate type assignment')
    gset={(tuple(p['rect']),p['axis']) for p in s['placements'] if p['kind'] in ('small','medium','large')}
    require(all((tuple(p['rect']),p['axis']) in gset for p in ass),'typed unselected geometry')
    for p in ass:
        k=p['kind'];shape=tuple(p['rect'][2:])
        allowed=((3,3),) if k in ('crush','refine','parts','mold') else (((5,5),) if k in ('plant','seed') else ((6,4),(4,6)))
        require(shape in allowed,'type dimensions')
        require(p['input_side'] in (0,1),'input side')
    stats={}
    for lname,flow in s['flows'].items():
        K=flow['K']; require(K==(1 if lname=='ore' else 20),'scale')
        tables={}
        for name,vals in flow.items():
            if name=='K': continue
            tab={((x,y),d):v for x,y,d,v in vals};tables[name]=tab
            require(len(tab)==len(vals),f'{lname} duplicate arcs {name}')
            require(all(isinstance(v,int) and 0<v<=K and pt in T and 0<=d<4 for (pt,d),v in tab.items()),f'{lname} arc capacity {name}')
        require(tables['warehouse']=={e:K for e in wh},f'{lname} warehouse equalities')
        require(tables['core_src']=={e:K for e in co},f'{lname} core source equalities')
        ain,aout={},{}
        sums=defaultdict(lambda:[0,0]); per_machine=[]
        for i,p in enumerate(ass):
            k=p['kind']
            if lname=='ore' and k not in ('crush','refine'): continue
            ip=[e for e in face(p['rect'],p['axis'],p['input_side']) if min(e[0])>=1]
            op=[e for e in face(p['rect'],p['axis'],1-p['input_side']) if min(e[0])>=1]
            for e in ip: require(e not in ain,'ambiguous input port');ain[e]=i
            if lname=='all':
                for e in op: require(e not in aout,'ambiguous output port');aout[e]=i
            ii=sum(tables['machine_in'].get(e,0) for e in ip)
            oo=sum(tables['machine_out'].get(e,0) for e in op)
            if lname=='ore': require(0<=ii<=K and oo==0,f'ore machine bound {i}')
            else:
                il,ih,ol,oh=BOUNDS[k];require(il<=ii<=ih and ol<=oo<=oh,f'all machine bound {i}')
            sums[k][0]+=ii;sums[k][1]+=oo
            per_machine.append(dict(kind=k,rect=p['rect'],inflow=ii,outflow=oo))
        require(set(tables['machine_in'])<=set(ain),f'{lname} illegal machine sink')
        require(set(tables['machine_out'])<=set(aout),f'{lname} illegal machine source')
        require(set(tables['core_sink'])<=ci,f'{lname} illegal core sink')
        if lname=='ore':
            require(sums['crush'][0]==18 and sums['refine'][0]==34,'ore type totals')
            require(not tables['core_sink'],'ore deposited in core')
        else:
            require(sum(tables['core_sink'].values())>=23,'core demand')
            for k,(ii,oo) in TOTAL.items(): require(sums[k][0]>=ii and sums[k][1]>=oo,f'all totals {k}')
        inflow=defaultdict(lambda:[0]*4);outflow=defaultdict(lambda:[0]*4)
        for (pt,d),v in tables['edgeflow'].items():
            dx,dy=DIR[d];n=pt[0]+dx,pt[1]+dy
            require(n in T,f'{lname} edge into nontransport')
            outflow[pt][d]+=v;inflow[n][OPP[d]]+=v
        for name in ['machine_out','core_src','warehouse']:
            for (pt,d),v in tables[name].items(): inflow[pt][d]+=v
        for name in ['machine_in','core_sink']:
            for (pt,d),v in tables[name].items(): outflow[pt][d]+=v
        throughput=0;dual=0;saturated=[];saturated_axes=[]
        for pt in T:
            ii,oo=inflow[pt],outflow[pt];throughput+=sum(ii)
            require(sum(ii)==sum(oo),f'{lname} cell conservation {pt}')
            if pt in B:
                for ax in (0,1):
                    require(ii[ax]+ii[ax+2]==oo[ax]+oo[ax+2]<=K,f'{lname} bridge axis {pt},{ax}')
                    if ii[ax]+ii[ax+2]==K:
                        saturated_axes.append(dict(cell=pt,axis='H' if ax==0 else 'V',
                            incoming=[ii[ax],ii[ax+2]],outgoing=[oo[ax],oo[ax+2]],value=K))
                dual+=int(ii[0]+ii[2]>0 and ii[1]+ii[3]>0)
            else: require(sum(ii)<=K,f'{lname} cell capacity {pt}')
            if sum(ii)==K*(2 if pt in B else 1):
                saturated.append(dict(cell=pt,bridge=pt in B,inflow=ii,outflow=oo))
        if lname=='all':require(dual>=max(0,306-len(T)),'all-layer dual-active bridge density')
        stats[lname]=dict(K=K,source_total=sum(tables['core_src'].values())+sum(tables['warehouse'].values()),
                         machine_totals=dict(sums),transport_throughput=throughput,
                         transport_edges=sum(tables['edgeflow'].values()),dual_active_bridges=dual,
                         saturated_count=len(saturated),saturated_examples=saturated[:20],
                         saturated_axis_count=len(saturated_axes),saturated_axis_examples=saturated_axes[:20],
                         source_cell_examples=[dict(cell=pt,enter_side=d,bridge=pt in B,
                             incoming=inflow[pt],outgoing=outflow[pt]) for pt,d in wh[:12]],
                         direction_order=['E','N','W','S'],per_machine=per_machine)
    return dict(ok=not errors,errors=errors,transport_count=len(T),bridge_count=len(B),P=s['P'],J=J,X=X,Y=Y,flow_statistics=stats)


if __name__=='__main__':
    source=Path(sys.argv[1]); result=check(json.loads(source.read_text()))
    target=source.with_name(source.stem+'.check.json');target.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='flow_statistics'},ensure_ascii=False))
    raise SystemExit(0 if result['ok'] else 1)
