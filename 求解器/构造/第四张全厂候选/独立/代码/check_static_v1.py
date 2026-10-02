#!/usr/bin/env python3
"""从占格和端口重建实际进路；不导入摆放、布线或导出程序。"""
import json,sys,hashlib
from collections import Counter,defaultdict,deque
from fractions import Fraction as F
from pathlib import Path
D=((1,0),(0,1),(-1,0),(0,-1))
REC={
'粉碎-源矿':('粉碎机',{'源矿':1},{'源石粉末':1},1),
'粉碎-蓝铁块':('粉碎机',{'蓝铁块':1},{'蓝铁粉末':1},1),
'粉碎-砂叶':('粉碎机',{'砂叶':1},{'砂叶粉末':3},1),
'粉碎-荞花':('粉碎机',{'荞花':1},{'荞花粉末':2},1),
'精炼-蓝铁矿':('精炼炉',{'蓝铁矿':1},{'蓝铁块':1},1),
'精炼-致密蓝铁':('精炼炉',{'致密蓝铁粉末':1},{'钢块':1},1),
'研磨-致密蓝铁':('研磨机',{'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1},1),
'研磨-致密源石':('研磨机',{'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1},1),
'研磨-细磨荞花':('研磨机',{'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1},1),
'塑形-钢质瓶':('塑形机',{'钢块':2},{'钢质瓶':1},1),
'配件-钢制零件':('配件机',{'钢块':1},{'钢制零件':1},1),
'种植-砂叶':('种植机',{'砂叶种子':1},{'砂叶':1},1),
'种植-荞花':('种植机',{'荞花种子':1},{'荞花':1},1),
'采种-砂叶':('采种机',{'砂叶':1},{'砂叶种子':2},1),
'采种-荞花':('采种机',{'荞花':1},{'荞花种子':2},1),
'封装-电池':('封装机',{'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1},5),
'灌装-胶囊':('灌装机',{'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1},5)}

def expected():
    """按收货机器逐台展开，与生成器的按供应链展开分离。"""
    m={}; fs=[]
    def unit(n,r,q=1):m[n]=(r,F(q))
    def feed(a,b,it,q=1):fs.append((a,b,it,str(F(q))))
    sand=[['B1','B2','O1'],['O2','O3'],['B3','B4','O4'],['O5','O6'],['B5','B6','O7'],['O8','O9'],['B7','B8','B9'],['B10','Q1','Q2'],['B11','B12','B13'],['B14','Q3','Q4'],['B15','B16','Q5'],['B17'],['Q6']]
    lookup={t:f'S{i}' for i,ts in enumerate(sand,1) for t in ts}
    for k in range(1,35):
        unit(f'T{k}','精炼-蓝铁矿');unit(f'KB{k}','粉碎-蓝铁块')
        feed(f'OB{k}',f'T{k}','蓝铁矿');feed(f'T{k}',f'KB{k}','蓝铁块')
    for k in range(1,19):
        unit(f'U{k}','粉碎-源矿');feed('CORE' if k<=6 else f'OO{k}',f'U{k}','源矿')
    for prefix,n,raw,den,up in [('B',17,'蓝铁粉末','致密蓝铁','KB'),('O',9,'源石粉末','致密源石','U'),('Q',6,'荞花粉末','细磨荞花','KQ')]:
        for k in range(1,n+1):
            t=f'{prefix}{k}';rate=F(1,2) if t=='Q6' else F(1)
            unit(t,'研磨-'+den,rate)
            if prefix=='Q':
                for j in range(1 if k==6 else 2):feed(f'KQ{k}',t,raw)
            else:
                for j in [2*k-1,2*k]:feed(f'{up}{j}',t,raw)
            feed(lookup[t],t,'砂叶粉末',rate)
    for k in range(1,18):unit(f'R{k}','精炼-致密蓝铁');feed(f'B{k}',f'R{k}','致密蓝铁粉末')
    for k in range(1,7):
        unit(f'P{k}','配件-钢制零件');feed(f'R{k}',f'P{k}','钢块')
        unit(f'H{k}','塑形-钢质瓶',F(1,2) if k==6 else 1)
        for j in ([17] if k==6 else [2*k+5,2*k+6]):feed(f'R{j}',f'H{k}','钢块')
    for k in range(1,4):
        unit(f'E{k}','封装-电池',F(1,5))
        for j in [2*k-1,2*k]:feed(f'P{j}',f'E{k}','钢制零件')
        for j in [3*k-2,3*k-1,3*k]:feed(f'O{j}',f'E{k}','致密源石粉末')
        feed(f'E{k}','CORE','高容谷地电池',F(1,5))
    for k,js,q in [(1,[1,2],F(1,5)),(2,[3,4],F(1,5)),(3,[5],F(1,10)),(4,[6],F(1,20))]:
        unit(f'F{k}','灌装-胶囊',q)
        for j in js:
            feed(f'H{j}',f'F{k}','钢质瓶',F(1,2) if j==6 else 1)
            feed(f'Q{j}',f'F{k}','细磨荞花粉末',F(1,2) if j==6 else 1)
        feed(f'F{k}','CORE','精选荞愈胶囊',q)
    for p,n,plant in [('S',13,'砂叶'),('Q',6,'荞花')]:
        for k in range(1,n+1):
            total=sum(F(1,2) if t=='Q6' else F(1) for t in sand[k-1]) if p=='S' else (1 if k==6 else 2)
            rate=total/(3 if p=='S' else 2);rate=F(rate)
            if p=='Q':rate=F(1,2) if k==6 else F(1)
            unit(f'{p}A{k}','种植-'+plant,rate);unit(f'{p}B{k}','种植-'+plant,rate);unit(f'{p}C{k}','采种-'+plant,rate)
            cr=f'S{k}' if p=='S' else f'KQ{k}';unit(cr,'粉碎-'+plant,rate)
            feed(f'{p}C{k}',f'{p}A{k}',plant+'种子',rate);feed(f'{p}C{k}',f'{p}B{k}',plant+'种子',rate)
            feed(f'{p}A{k}',f'{p}C{k}',plant,rate);feed(f'{p}B{k}',cr,plant,rate)
    assert len(m)==230 and len(fs)==325
    return m,fs

def cells(u):
    if 'x' in u:return [(u['x'],u['y'])]
    return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def largest(occ):
    # Enumerate all x intervals and maximal all-empty vertical runs.
    best=(0,0);rect=None
    rowbits=[sum(1<<x for x in range(70) if (x,y) in occ) for y in range(70)]
    for x0 in range(65):
        for x1 in range(x0+5,70):
            mask=((1<<(x1-x0+1))-1)<<x0;y0=0
            for y in range(71):
                if y==70 or rowbits[y]&mask:
                    h=y-y0;w=x1-x0+1
                    if h>=6 and (w*h,min(w,h))>best:best=(w*h,min(w,h));rect=dict(x0=x0,y0=y0,x1=x1,y1=y-1)
                    y0=y+1
    return {'area':best[0],'short_side':best[1],'rectangle':rect}
def run(d):
    l=d['layout'];ck=[]
    def check(n,b,detail=None):ck.append({'name':n,'pass':bool(b),'detail':detail})
    check('基地70×70',l['W']==l['H']==70)
    groups=['machines','warehouse_outlets','power_poles','storage_boxes','transport']; us={};typ={};occ={};coll=[];outside=[]
    for g in groups+['core']:
        for u in ([l['core']] if g=='core' else l[g]):
            if u['id'] in us:coll.append(['duplicate_id',u['id']])
            us[u['id']]=u;typ[u['id']]=g
            for c in cells(u):
                if c in occ:coll.append([c,occ[c],u['id']])
                occ[c]=u['id']
                if any(type(v) is not int or not 0<=v<70 for v in c):outside.append([u['id'],c])
    check('不重叠',not coll,coll);check('不越界',not outside,outside)
    em,ef=expected();mm={u['id']:u for u in l['machines']};check('逐台230台',set(mm)==set(em),dict(actual=len(mm),expected=230))
    badshape=[];badrecipe=[]
    for name,u in mm.items():
        if name not in em:badrecipe.append(name);continue
        recipe,rate=em[name];model=REC[recipe][0];kind='中' if model in ['种植机','采种机'] else '大' if model in ['研磨机','封装机','灌装机'] else '小'
        w,h=(3,3) if kind=='小' else (5,5) if kind=='中' else (6,4) if u['Din']%2 else (4,6)
        if u['Din'] not in range(4) or (u['x1']-u['x0']+1,u['y1']-u['y0']+1)!=(w,h) or u['kind']!=kind:badshape.append(name)
        if u['model']!=model or u['recipe_ids']!=[recipe] or u['settings']!={'manufacture_on':True}:badrecipe.append(name)
    check('机身尺寸和旋转',not badshape,badshape);check('配方和开关',not badrecipe,badrecipe)
    check('无禁用单位和虚拟接口',not l['storage_boxes'] and not l['vin'] and not l['vout'] and all(u['type'] in ('belt','bridge') for u in l['transport']))
    co=l['core'];check('唯一9×9协议核心',co['id']=='CORE' and co['x1']-co['x0']==co['y1']-co['y0']==8 and co['Din'] in range(4))
    cfg={(p['side'],p['offset']):p['item'] for p in co['output_items']}
    check('核心六取货端口设源矿',len(co['output_items'])==6 and cfg=={(s,o):'源矿' for s in ((co['Din']+1)%4,(co['Din']+3)%4) for o in (1,4,7)})
    bo=[]
    for u in l['warehouse_outlets']:
        if not ((u['Dout']==0 and u['x0']==u['x1']==0 and u['y1']-u['y0']==2) or (u['Dout']==1 and u['y0']==u['y1']==0 and u['x1']-u['x0']==2)):bo.append(u['id'])
    check('46取货口贴左下边界',len(l['warehouse_outlets'])==46 and not bo,bo)
    check('34蓝铁矿及12源矿边界取货口',Counter(u['item'] for u in l['warehouse_outlets'])=={'蓝铁矿':34,'源矿':12})
    check('两边各23取货口',Counter(u['Dout'] for u in l['warehouse_outlets'])=={0:23,1:23})
    bp=[p['id'] for p in l['power_poles'] if p['x1']-p['x0']!=1 or p['y1']-p['y0']!=1 or p.get('orientation')!=0]
    unpowered=[n for n,u in mm.items() if not any(max(u['x0'],p['x0']-5)<=min(u['x1'],p['x0']+6) and max(u['y0'],p['y0']-5)<=min(u['y1'],p['y0']+6) for p in l['power_poles'])]
    check('供电桩尺寸',not bp,bp);check('230台全部供电',not unpowered,unpowered)
    ports={};locations={};trans=set(u['id'] for u in l['transport'])
    def port(u,side,off,mode):
        if 'x' in u:x,y=u['x'],u['y']
        elif side==0:x,y=u['x1'],u['y0']+off
        elif side==2:x,y=u['x0'],u['y0']+off
        elif side==1:x,y=u['x0']+off,u['y1']
        else:x,y=u['x0']+off,u['y0']
        ref=(u['id'],side,off);ports[ref]=(x,y,mode);locations[x,y,side]=ref
    for n,u in us.items():
        g=typ[n]
        if g=='machines':
            for side,mode in [(u['Din'],1),((u['Din']+2)%4,2)]:
                for off in range(u['y1']-u['y0']+1 if side%2==0 else u['x1']-u['x0']+1):port(u,side,off,mode)
        elif g=='warehouse_outlets':port(u,u['Dout'],1,2)
        elif g=='core':
            for side in [u['Din'],(u['Din']+2)%4]:
                for off in range(1,8):port(u,side,off,1)
            for (side,off),it in cfg.items():port(u,side,off,2)
        elif g=='transport':
            if u['type']=='belt':
                check('带方向.'+n,u['in_side'] in range(4) and u['out_side'] in range(4) and u['in_side']!=u['out_side'])
                port(u,u['in_side'],0,1);port(u,u['out_side'],0,2)
            elif u['type']=='bridge':
                for side in range(4):port(u,side,0,3)
    actual=set(); outgoing={}
    for p,(x,y,mode) in ports.items():
        if not mode&2:continue
        side=p[1];q=locations.get((x+D[side][0],y+D[side][1],(side+2)%4))
        if q and ports[q][2]&1 and (p[0] in trans or q[0] in trans):actual.add((p,q));outgoing[p]=q
    def ref(p):return p['unit'],p['side'],p['offset']
    claimed=d['design']['physical_channels'];cm={(ref(c['from']),ref(c['to'])):c for c in claimed}
    check('声明通道等于自动形成通道',len(cm)==len(claimed) and set(cm)==actual,{'missing':list(actual-set(cm)),'extra':list(set(cm)-actual)})
    actual_routes=[];errors=[];usedaxes=Counter();usedchannels=Counter();bridgeins={}
    for p,(x,y,mode) in ports.items():
        if p[0] in trans or not mode&2 or p not in outgoing:continue
        path=[];visited=set();a=p
        while a in outgoing:
            b=outgoing[a];path.append((a,b))
            if b[0] not in trans:break
            n=b[0];u=us[n]
            if n in visited:errors.append(['repeated_unit',p,n]);break
            visited.add(n);axis=b[1]%2 if u['type']=='bridge' else 0;usedaxes[n,axis]+=1
            if u['type']=='bridge':out=(b[1]+2)%4;bridgeins[n,axis]=b[1]
            else:out=u['out_side']
            a=(n,out,0)
        else:errors.append(['dead_end',p,a])
        if not path or path[-1][1][0] in trans:continue
        for z in path:usedchannels[z]+=1
        n=p[0]
        item=cfg[p[1],p[2]] if n=='CORE' else us[n]['item'] if typ[n]=='warehouse_outlets' else next(iter(REC[em[n][0]][2])) if n in em else '未知'
        actual_routes.append({'source':p,'target':path[-1][1],'item':item,'path':path,'length':len(path)-1})
    check('逐路连续且不重复单位',not errors,errors)
    check('运输物品格不共用',all(v==1 for v in usedaxes.values()) and all(v==1 for v in usedchannels.values()))
    check('全部运输单位在进路上',trans=={n for n,axis in usedaxes})
    reverse={(q,p) for p,q in usedchannels if p[0] in trans and q[0] in trans and us[p[0]]['type']==us[q[0]]['type']=='bridge'}
    check('无额外通道',actual==set(usedchannels)|reverse,{'unaccounted':list(actual-set(usedchannels)-reverse)})
    bridgebad=[]
    for u in l['transport']:
        if u['type']!='bridge':continue
        n=u['id']
        if u['H_in']!=bridgeins.get((n,0)) or u['V_in']!=bridgeins.get((n,1)):bridgebad.append(n)
    check('桥轴方向及空轴',not bridgebad,bridgebad)
    # Actual route identities are derived before reading the declared logical paths.
    exp=Counter((s,t,it) for s,t,it,q in ef);got=Counter((r['source'][0],r['target'][0],r['item']) for r in actual_routes)
    missing=list((exp-got).elements());extra=list((got-exp).elements())
    check('325条指定进路齐全',got==exp,{'completed':sum((got&exp).values()),'missing':missing,'extra':extra})
    rt={(s,t,it):q for s,t,it,q in ef}; byid={c['id']:c for c in claimed};decl=[]
    for z in d['design'].get('logical_feeds',[]):
        try:pp=tuple((ref(byid[c]['from']),ref(byid[c]['to'])) for c in z['path']);decl.append((ref(z['from']),ref(z['to']),z['item'],pp))
        except KeyError:errors.append(['bad_declared_path',z['id']])
    real=[(r['source'],r['target'],r['item'],tuple(r['path'])) for r in actual_routes]
    check('声明进路与重建逐格一致',Counter(decl)==Counter(real))
    check('进路设计流量',all(z['rate']==rt.get((z['from']['unit'],z['to']['unit'],z['item'])) for z in d['design'].get('logical_feeds',[])))
    check('通道物品',all(c['allowed_items']==[r['item']] for r in actual_routes for e in r['path'] if e in cm for c in [cm[e]]))
    equal={r['source'][0]:r['length'] for r in actual_routes if r['source'][0] in ('H6','Q6') and r['target'][0]=='F4'}
    check('H6和Q6到F4等长',len(equal)==2 and equal['H6']==equal['Q6'],equal)
    ins=defaultdict(Counter);outs=defaultdict(Counter)
    for r in actual_routes:
        s,t,it=r['source'][0],r['target'][0],r['item'];q=F(rt.get((s,t,it),'0'));ins[t][it]+=q;outs[s][it]+=q
    imbalance=[]
    for n,(recipe,q) in em.items():
        model,a,b,dt=REC[recipe]
        if ins[n]!=Counter({it:q*v for it,v in a.items()}) or outs[n]!=Counter({it:q*v for it,v in b.items()}) or dt*q>1:imbalance.append(n)
    check('精确平均物料守恒',not imbalance,imbalance)
    check('两种成品设计交付率',ins['CORE']==Counter({'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20)}),{k:str(v) for k,v in ins['CORE'].items()})
    maximum=largest(occ);rect=d.get('empty_rectangle');valid=False
    if rect:
        w,h=rect['x1']-rect['x0']+1,rect['y1']-rect['y0']+1
        valid=min(w,h)>=6 and not any(c in occ for c in cells(rect)) and (w*h,min(w,h))==(maximum['area'],maximum['short_side'])
    check('最大空矩形',valid,maximum)
    # Fixed-geometry reachability is a necessary condition, not a routing certificate.
    body={c for c,n in occ.items() if n not in trans}; comp={};ci=0
    for x in range(70):
        for y in range(70):
            if (x,y) in body or (x,y) in comp:continue
            ci+=1;comp[x,y]=ci;q=deque([(x,y)])
            while q:
                a,b=q.popleft()
                for dx,dy in D:
                    z=(a+dx,b+dy)
                    if 0<=z[0]<70 and 0<=z[1]<70 and z not in body and z not in comp:comp[z]=ci;q.append(z)
    opts=defaultdict(set)
    for p,(x,y,mode) in ports.items():
        if p[0] in trans:continue
        dx,dy=D[p[1]];c=(x+dx,y+dy)
        if c in comp:opts[p[0],mode].add(comp[c])
    obstructed=[(s,t,it) for s,t,it,q in ef if not opts[s,2]&opts[t,1]]
    stats={'machines':len(mm),'machine_area':sum(len(cells(u)) for u in mm.values()),'powered':len(mm)-len(unpowered),'power_poles':len(l['power_poles']),'occupied':len(occ),'transport_units':len(trans),'bridges':sum(u['type']=='bridge' for u in l['transport']),'transport_cells_used':sum(r['length'] for r in actual_routes),'automatic_channels':len(actual),'bridge_reverse_channels':len(reverse),'completed_routes':sum((got&exp).values()),'missing_routes':len(missing),'ore_routes':sum(r['item'] in ('源矿','蓝铁矿') for r in actual_routes),'product_routes':sum(r['target'][0]=='CORE' for r in actual_routes),'fixed_geometry_obstructed':len(obstructed),'empty_rectangle':maximum}
    return {'static_pass':all(c['pass'] for c in ck),'runtime_certified':False,'stats':stats,'checks':ck,'missing_routes':missing,'obstructed_routes':obstructed,'actual_routes':actual_routes}
if __name__=='__main__':
    p=Path(sys.argv[1]);r=run(json.loads(p.read_text()));r['layout_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();r['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=Path(sys.argv[2]);out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'static_pass':r['static_pass'],'stats':r['stats'],'failed':[c['name'] for c in r['checks'] if not c['pass']]},ensure_ascii=False))
