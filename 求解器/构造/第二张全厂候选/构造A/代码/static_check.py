#!/usr/bin/env python3
"""本席独立静态检查器：从完整占格重建全部端口与自动通道。

支持full-factory-static-v1的S2纯带子域，单位ID使用逻辑接法.json中的ID。
没有布局时逐项报告NOT_RUN_NO_LAYOUT，绝不把拓扑证书当作布局通过。
"""
import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
BASE=Path(__file__).resolve().parents[1]
D=((1,0),(0,1),(-1,0),(0,-1))
CHECKS={
 'schema':'格式和依据指纹',
 'in_bounds':'全部单位在70×70内',
 'no_overlap':'全部实体占格互不重叠',
 'machines':'230台机器的种类、尺寸、旋转、配方与制造开关',
 'core_outlets':'唯一协议核心、六口源矿、46个左下边界仓库取货口',
 'transport':'只有合法纯有向传送带，没有被禁止的单位',
 'automatic_channels':'全端口独立重建，与声明逐端点完全相等，无额外自动通道',
 'pure_paths':'全部进路至少一格，简单有向、不共用运输格、无游离格或纯运输环',
 's2_connections':'逐台逐路对应S2全部325条接法和各路物品',
 'power':'每台制造单位与至少一个供电桩的12×12覆盖相交',
 'equal_length':'H6→F4与Q6→F4运输格数相等',
 'empty_rectangle':'无单位占用，短边至少6，面积和短边按全图最大值核验',
 'material_balance':'按实际分解进路核对精确平均流、配方批率、全部矿口与成品目标',
 'logical_feed_claims':'可选logical_feeds的路径、物品、速率与端点声明',
}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    def unique(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('重复JSON键：'+k)
            out[k]=v
        return out
    return json.loads(Path(p).read_text(),object_pairs_hook=unique)


def ref(p):return p['unit'],p['side'],p['offset']


def port_cell(u,s,k):
    if s==0:return u['x1'],u['y0']+k
    if s==1:return u['x0']+k,u['y1']
    if s==2:return u['x0'],u['y0']+k
    return u['x0']+k,u['y0']


def rebuild_channels(ports, belts):
    """ports:引用->(内侧格,存取类型)。不读physical_channels。"""
    at={}
    for p,(cell,kind) in ports.items():
        key=cell,p[1],kind
        if key in at:raise ValueError('重叠端口几何')
        at[key]=p
    result=set()
    for p,(cell,kind) in ports.items():
        if kind!='out':continue
        dx,dy=D[p[1]]
        q=at.get(((cell[0]+dx,cell[1]+dy),(p[1]+2)%4,'in'))
        if q is not None and (p[0] in belts or q[0] in belts):result.add((p,q))
    return result


def maximum_rectangle(occupied,w=70,h=70,minimum=6):
    """穷举纵区间，按连续空列取最宽矩形；O(H²W)，含同面积短边比较。"""
    best=None;score=(-1,-1)
    for y0 in range(h):
        forbidden=[False]*w
        for y1 in range(y0,h):
            for x in range(w):forbidden[x]|=(x,y1) in occupied
            height=y1-y0+1
            if height<minimum:continue
            start=0
            for end in range(w+1):
                if end==w or forbidden[end]:
                    width=end-start
                    if width>=minimum:
                        candidate=(width*height,min(width,height))
                        if candidate>score:
                            score=candidate
                            best=dict(x0=start,y0=y0,x1=end-1,y1=y1,width=width,height=height,
                                      area=candidate[0],short_side=candidate[1])
                    start=end+1
    return best


class Audit:
    def __init__(self):self.rows={k:dict(id=k,name=v,status='PASS',evidence=[],errors=[]) for k,v in CHECKS.items()}
    def test(self,k,ok,message):
        self.rows[k]['evidence'].append(message)
        if not ok:self.rows[k]['status']='FAIL';self.rows[k]['errors'].append(message)
    def block(self,k,message):self.rows[k]['status']='NOT_RUN_INVALID_PREREQUISITE';self.rows[k]['errors'].append(message)


def check_layout(path,contract):
    a=Audit();d=read(path);l=d['layout']
    a.test('schema',d.get('schema')=='full-factory-static-v1','schema')
    a.test('schema',set(d)<=set(['schema','candidate_id','source_fingerprints','targets','layout','empty_rectangle','design','flow_witness','provenance']),'根字段')
    expected_hashes=dict(rules=sha(BASE/'依据快照/规则.txt'),task=sha(BASE/'依据快照/任务.txt'),constraints=sha(BASE/'依据快照/约束.txt'))
    a.test('schema',d.get('source_fingerprints')==expected_hashes,'冻结规则、任务、约束SHA-256')
    a.test('schema',d.get('targets')=={'高容谷地电池':'3/5','精选荞愈胶囊':'11/20'},'成品目标')
    a.test('schema',l['W']==l['H']==70 and l['vin']==l['vout']==[],'基地尺寸及无虚拟接口')
    a.test('transport',not l['storage_boxes'],'没有协议储存箱')
    a.test('schema',d['design']['class']=='p2p','本检查器支持p2p中的S2纯带子域')
    expected_m={u['id']:u for u in contract['machines']}
    expected_o={u['id']:u for u in contract['warehouse_outlets']}
    a.test('machines',Counter(m['id'] for m in l['machines'])==Counter(expected_m.keys()),'制造单位身份和台数')
    a.test('core_outlets',Counter(m['id'] for m in l['warehouse_outlets'])==Counter(expected_o.keys()),'仓库取货口身份和台数')
    units={};occ={};ports={};belts=set()

    def add_unit(u,cells):
        a.test('no_overlap',u['id'] not in units,dict(unit=u['id'],reason='唯一ID'))
        units[u['id']]=u
        for c in cells:
            a.test('in_bounds',all(type(x)==int and 0<=x<70 for x in c),dict(unit=u['id'],cell=c))
            a.test('no_overlap',c not in occ,dict(unit=u['id'],cell=c,other=occ.get(c)))
            occ[c]=u['id']

    def rectangle(u):
        for k in ['x0','y0','x1','y1']:
            if type(u[k])!=int:raise ValueError('坐标必须为整数')
        if u['x1']<u['x0'] or u['y1']<u['y0']:raise ValueError('倒置矩形')
        return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]

    def add_side(u,side,kind,offsets=None):
        if type(side)!=int or side not in range(4):raise ValueError('方向错误')
        length=u['y1']-u['y0']+1 if side%2==0 else u['x1']-u['x0']+1
        for k in range(length) if offsets is None else offsets:
            ports[(u['id'],side,k)]=(port_cell(u,side,k),kind)

    for u in l['machines']:
        add_unit(u,rectangle(u))
        spec=expected_m.get(u['id'])
        ok=spec is not None and u['model']==spec['model'] and u['kind']==spec['kind'] and u['recipe_ids']==[spec['recipe_id']] and u['settings']=={'manufacture_on':True}
        a.test('machines',ok,dict(unit=u['id'],reason='机型、配方和制造开关'))
        w,h=u['x1']-u['x0']+1,u['y1']-u['y0']+1
        dim=(3,3) if u['kind']=='小' else (5,5) if u['kind']=='中' else (4,6) if u['Din']%2==0 else (6,4)
        a.test('machines',(w,h)==dim,dict(unit=u['id'],actual=[w,h],required=dim))
        add_side(u,u['Din'],'in');add_side(u,(u['Din']+2)%4,'out')
    for u in l['warehouse_outlets']:
        add_unit(u,rectangle(u))
        side=u['Dout']
        geom=((u['x0']==u['x1']==0 and u['y1']==u['y0']+2) if side==0 else
              (u['y0']==u['y1']==0 and u['x1']==u['x0']+2) if side==1 else False)
        spec=expected_o.get(u['id'])
        a.test('core_outlets',geom and spec is not None and spec['item']==u['item'],dict(unit=u['id'],reason='位置、端口和矿石'))
        add_side(u,side,'out',[1])
    a.test('core_outlets',Counter(u['Dout'] for u in l['warehouse_outlets'])=={0:23,1:23},'左下各23个取货口')
    u=l['core'];add_unit(u,rectangle(u))
    a.test('core_outlets',u['id']=='CORE' and u['x1']==u['x0']+8 and u['y1']==u['y0']+8,'协议核心身份和9×9尺寸')
    for s in [u['Din'],(u['Din']+2)%4]:add_side(u,s,'in',range(1,8))
    out_sides=[(u['Din']+1)%4,(u['Din']+3)%4]
    for s in out_sides:add_side(u,s,'out',[1,4,7])
    actual_core=Counter((q['side'],q['offset'],q['item']) for q in u['output_items'])
    want_core=Counter((s,k,'源矿') for s in out_sides for k in [1,4,7])
    a.test('core_outlets',actual_core==want_core,'核心六个取货端口全部设源矿')
    for u in l['power_poles']:
        add_unit(u,rectangle(u))
        a.test('power',u['x1']==u['x0']+1 and u['y1']==u['y0']+1 and u['orientation']==0,dict(unit=u['id'],reason='供电桩尺寸'))
    for u in l['storage_boxes']:add_unit(u,rectangle(u))
    for u in l['transport']:
        add_unit(u,[(u['x'],u['y'])]);belts.add(u['id'])
        ok=u['type']=='belt' and type(u.get('in_side'))==int and type(u.get('out_side'))==int and u.get('in_side') in range(4) and u.get('out_side') in range(4) and u['in_side']!=u['out_side']
        a.test('transport',ok,dict(unit=u['id']))
        if not ok:continue
        ports[u['id'],u['in_side'],0]=((u['x'],u['y']),'in')
        ports[u['id'],u['out_side'],0]=((u['x'],u['y']),'out')
    for m in l['machines']:
        covering=[p['id'] for p in l['power_poles'] if
                  m['x1']>=p['x0']-5 and m['x0']<=p['x0']+6 and m['y1']>=p['y0']-5 and m['y0']<=p['y0']+6]
        a.test('power',bool(covering),dict(machine=m['id'],poles=covering))

    channels=rebuild_channels(ports,belts)
    claimed=d['design']['physical_channels']
    pairs=[(ref(e['from']),ref(e['to'])) for e in claimed]
    a.test('automatic_channels',len(set(pairs))==len(pairs) and len({e['id'] for e in claimed})==len(claimed),'声明端点对、通道ID唯一')
    a.test('automatic_channels',set(pairs)==channels,dict(extra=sorted(channels-set(pairs)),missing=sorted(set(pairs)-channels)))
    incoming=defaultdict(list);outgoing=defaultdict(list)
    for edge in channels:outgoing[edge[0][0]].append(edge);incoming[edge[1][0]].append(edge)
    for uid in belts:
        a.test('pure_paths',len(incoming[uid])==len(outgoing[uid])==1,dict(belt=uid,in_degree=len(incoming[uid]),out_degree=len(outgoing[uid])))
    actual_routes=[];used_belts=Counter();used_edges=Counter()
    for first in sorted(channels):
        if first[0][0] in belts:continue
        edge=first;walk=[];seen=set();es=[];last=None
        while True:
            es.append(edge)
            v=edge[1][0]
            if v not in belts:last=edge[1];break
            if v in seen or len(outgoing[v])!=1:break
            walk.append(v);seen.add(v);edge=outgoing[v][0]
        valid=last is not None and bool(walk)
        a.test('pure_paths',valid,dict(source=first[0],target=last,belt_count=len(walk)))
        if not valid:continue
        start=first[0];src=start[0]
        if src=='CORE':
            vals=[q['item'] for q in l['core']['output_items'] if (q['side'],q['offset'])==start[1:]]
            item=vals[0] if len(vals)==1 else '未知物品'
        elif src in expected_o:item=units[src]['item']
        elif src in expected_m:item=next(iter(expected_m[src]['outputs']))
        else:item='未知物品'
        actual_routes.append(dict(source=src,target=last[0],item=item,from_port=start,to_port=last,belts=walk,edges=es))
        used_belts.update(walk);used_edges.update(es)
    a.test('pure_paths',set(used_belts)==belts and all(n==1 for n in used_belts.values()),'全部运输格恰属于一条进路')
    a.test('pure_paths',set(used_edges)==channels and all(n==1 for n in used_edges.values()),'全部自动通道恰属于一条进路')
    expected_feeds=Counter((e['source'],e['target'],e['item']) for e in contract['logical_feeds'])
    got_feeds=Counter((e['source'],e['target'],e['item']) for e in actual_routes)
    a.test('s2_connections',got_feeds==expected_feeds,dict(missing=list((expected_feeds-got_feeds).elements()),extra=list((got_feeds-expected_feeds).elements())))
    decl_by_pair={p:e for p,e in zip(pairs,claimed)}
    decl_ids={e['id']:p for e,p in zip(claimed,pairs)}
    rates={(e['source'],e['target'],e['item']):Fraction(e['rate']) for e in contract['logical_feeds']}
    quantities_in=defaultdict(lambda:defaultdict(Fraction));quantities_out=defaultdict(lambda:defaultdict(Fraction))
    for route in actual_routes:
        triple=route['source'],route['target'],route['item']
        if triple not in rates:continue
        rate=rates[triple]
        quantities_out[route['source']][route['item']]+=rate
        quantities_in[route['target']][route['item']]+=rate
        for edge in route['edges']:
            decl=decl_by_pair.get(edge)
            a.test('automatic_channels',decl is not None and decl['allowed_items']==[route['item']],dict(edge=edge,actual_item=route['item']))
        a.test('material_balance',0<rate<=1,dict(route=triple,rate=str(rate)))
    for m in contract['machines']:
        rate=Fraction(m['batch_rate'])
        a.test('material_balance',rate*m['duration']<=1,dict(machine=m['id'],utilization=str(rate*m['duration'])))
        for table,way in [(quantities_in,'inputs'),(quantities_out,'outputs')]:
            want={item:qty*rate for item,qty in m[way].items()}
            a.test('material_balance',dict(table[m['id']])==want,dict(machine=m['id'],way=way))
    for w in contract['warehouse_outlets']:
        a.test('material_balance',dict(quantities_out[w['id']])=={w['item']:Fraction(1)},dict(outlet=w['id'],reason='满速矿石'))
    a.test('material_balance',dict(quantities_out['CORE'])=={'源矿':Fraction(6)},'核心六口源矿合计6')
    a.test('material_balance',dict(quantities_in['CORE'])=={'高容谷地电池':Fraction(3,5),'精选荞愈胶囊':Fraction(11,20)},'精确成品交付和非成品零入库')
    lens={src:[len(e['belts']) for e in actual_routes if e['source']==src and e['target']=='F4'] for src in ['H6','Q6']}
    a.test('equal_length',len(lens['H6'])==len(lens['Q6'])==1 and lens['H6']==lens['Q6'],lens)
    if 'logical_feeds' in d['design']:
        decl_routes=d['design']['logical_feeds']
        real={tuple(decl_by_pair[e]['id'] for e in r['edges']):r for r in actual_routes if all(e in decl_by_pair for e in r['edges'])}
        given_paths=[]
        for claim in decl_routes:
            p=tuple(claim['path']);given_paths.append(p);r=real.get(p)
            ok=r is not None and ref(claim['from'])==r['from_port'] and ref(claim['to'])==r['to_port'] and claim['item']==r['item']
            if ok:ok=Fraction(claim['rate'])==rates[r['source'],r['target'],r['item']]
            a.test('logical_feed_claims',ok,dict(logical_feed=claim['id']))
        a.test('logical_feed_claims',Counter(given_paths)==Counter(real.keys()),'声明路径与实际路径全部一致')
    else:a.rows['logical_feed_claims']['evidence'].append('未附可选声明，已从物理通道重建325路')
    maximum=maximum_rectangle(occ)
    r=d['empty_rectangle'];w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1
    valid=0<=r['x0']<=r['x1']<70 and 0<=r['y0']<=r['y1']<70 and min(w,h)>=6
    if valid:valid=all((x,y) not in occ for x in range(r['x0'],r['x1']+1) for y in range(r['y0'],r['y1']+1))
    a.test('empty_rectangle',valid,'所声明矩形界内、短边≥6且无任何单位')
    a.test('empty_rectangle',maximum is not None and (w*h,min(w,h))==(maximum['area'],maximum['short_side']),dict(recomputed=maximum))
    return dict(candidate_sha256=sha(path),checks=list(a.rows.values()),
                coordinate_checks_pass=all(r['status']=='PASS' for r in a.rows.values()),
                recomputed=dict(occupied_cells=len(occ),belts=len(belts),channels=len(channels),
                                logical_routes=len(actual_routes),maximum_empty_rectangle=maximum))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--layout',type=Path)
    p.add_argument('--out',type=Path,default=BASE/'证据/静态检查结果.json')
    args=p.parse_args()
    if not args.out.resolve().is_relative_to(BASE):p.error('输出只允许在构造A目录内')
    contract=read(BASE/'逻辑接法.json')
    from check_topology import witness_paths,verify_paths
    left,right,paths=witness_paths(2)
    topology=verify_paths(read(BASE/'依据快照/既有逻辑图.json'),left,right,paths)
    if args.layout is None:
        result=dict(candidate_sha256=None,checks=[dict(id=k,name=v,status='NOT_RUN_NO_LAYOUT',reason='固定S2接法已被平面性必要条件排除，没有坐标布局') for k,v in CHECKS.items()],coordinate_checks_pass=False)
    else:
        try:result=check_layout(args.layout,contract)
        except (ValueError,TypeError,KeyError,IndexError) as e:
            result=dict(candidate_sha256=sha(args.layout),checks=[dict(id='input',status='FAIL',error=str(e))],coordinate_checks_pass=False)
    result.update(checker='construction-A-static-1',checker_sha256=sha(__file__),
                  topology_precondition='FAIL' if topology['pass_certificate'] else 'UNRESOLVED',
                  topology_evidence='拓扑复核结果.json',static_pass=False,layout_path=str(args.layout) if args.layout else '',
                  runtime_certified=False,L_updated=False,
                  scope='坐标层执行状态与拓扑不可行证书分列；没有布局时不认证任何逐格条件')
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(static_pass=result['static_pass'],layout_path=result['layout_path'],topology_precondition=result['topology_precondition'],out=str(args.out)),ensure_ascii=False))
    return 1


if __name__=='__main__':raise SystemExit(main())
