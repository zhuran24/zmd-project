#!/usr/bin/env python3
"""Build existing models without solving; extract exact variable incidence."""
import ast
import collections
import functools
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time
import types

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[2]
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')

def guard(event, args):
    if event == 'open':
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (flags is not None and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing and isinstance(path, (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(path)).resolve()
            if not p.is_relative_to(OUT):
                raise RuntimeError(f'Write outside output forbidden: {p}')

sys.addaudithook(guard)
import numpy as np
from ortools.sat.python import cp_model
from ortools.sat import cp_model_pb2

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def no_solve(*args, **kwargs):
    raise RuntimeError('Solving is forbidden in this detection task')

cp_model.CpSolver.solve = no_solve
cp_model.CpSolver.Solve = no_solve
ORIGINS = {}
SOURCES = {}
READS = set()

def record_read(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).resolve()
        if p.is_relative_to(ROOT) and not p.is_relative_to(OUT) and p.suffix in ('.py', '.json', '.txt', '.md'):
            READS.add(p)

sys.addaudithook(record_read)
for method in ('add', 'add_bool_or', 'add_bool_and', 'add_bool_xor', 'add_exactly_one', 'add_at_most_one', 'add_implication', 'add_allowed_assignments', 'add_forbidden_assignments'):
    orig = getattr(cp_model.CpModel, method)
    def wrap(fn):
        @functools.wraps(fn)
        def call(self, *args, **kwargs):
            frame = sys._getframe(1)
            while frame and not (str(ROOT) in frame.f_code.co_filename and '/结构检测/' not in frame.f_code.co_filename):
                frame = frame.f_back
            location = (str(Path(frame.f_code.co_filename).relative_to(ROOT)), frame.f_lineno) if frame else ('build_extract.py', 0)
            before = len(self.proto.constraints)
            result = fn(self, *args, **kwargs)
            if location not in SOURCES:
                SOURCES[location] = len(SOURCES)
            for index in range(before, len(self.proto.constraints)):
                ORIGINS.setdefault(index, SOURCES[location])
            return result
        return call
    setattr(cp_model.CpModel, method, wrap(orig))

NAMES = {'crush':'粉碎机', 'refine':'精炼炉', 'parts':'配件机', 'mold':'塑形机', 'plant':'种植机', 'seed':'采种机', 'grind':'研磨机', 'pack':'封装机', 'fill':'灌装机', 'small':'小制造单位', 'medium':'中制造单位', 'large':'大制造单位', 'core':'协议核心', 'pole':'供电桩', 's':'小制造单位', 'm':'中制造单位', 'l':'大制造单位', 'c':'协议核心', 'p':'供电桩'}

def variable_info(model, meta, bodies=None):
    info = [dict(id=i, name=v.name, domain=list(v.domain), family='未归类', layer='geometry', xy=None) for i,v in enumerate(model.proto.variables)]
    for kind, rect, axis, v in meta.get('placements', []):
        info[v.index].update(family=NAMES[kind]+'候选摆位', kind=NAMES[kind], rect=list(rect), axis=axis, xy=[rect[0]+rect[2]/2, rect[1]+rect[3]/2])
    for p in meta.get('typed', []):
        x,y,w,h=p['rect']
        info[p['var'].index].update(family=NAMES[p['kind']]+'候选摆位及存货边', kind=NAMES[p['kind']], rect=list(p['rect']), axis=p['axis'], input_side=p['side'], xy=[x+w/2,y+h/2])
    if bodies:
        for i,b in enumerate(bodies):
            x,y,w,h=(b[t] for t in ('x','y','w','h'))
            info[i].update(family=NAMES[b['kind']]+'候选摆位',kind=NAMES[b['kind']],rect=[x,y,w,h],xy=[x+w/2,y+h/2],axis=b['axis'])
    import re
    for v in info:
        n=v['name']
        if v['family']!='未归类':continue
        m=re.fullmatch(r'(t|body|bridge|power_prefix)_(\d+)_(\d+)',n)
        if m:
            fam,x,y=m.groups();v.update(family={'t':'运输格状态','body':'结构占格状态','bridge':'桥接器状态','power_prefix':'供电桩二维前缀和'}[fam],xy=[int(x)+.5,int(y)+.5]);continue
        m=re.fullmatch(r'(ore|all)_(edge|mi|mo|ci|co|wh)_(\d+)_(\d+)_(\d+)',n)
        if m:
            layer,port,x,y,d=m.groups()
            v.update(layer=layer,family={'edge':'相邻运输格流量','mi':'制造单位存货端口流量','mo':'制造单位取货端口流量','ci':'协议核心存货端口流量','co':'协议核心取货端口流量','wh':'仓库取货口流量'}[port],xy=[int(x)+.5,int(y)+.5],direction=int(d),items=['源矿','蓝铁矿'] if layer=='ore' else '全体物品合计');continue
        m=re.fullmatch(r'(ore_recv|all_rate_in|all_rate_out)_(\d+)',n)
        if m:
            typ,idx=m.groups();parent=info[int(idx)]
            v.update(layer='ore' if typ=='ore_recv' else 'all',family=('矿石合计收量' if typ=='ore_recv' else ('全体物品合计收量' if typ=='all_rate_in' else '全体物品合计出量'))+'：'+parent['kind'],kind=parent['kind'],xy=parent['xy'],parent_variable=int(idx));continue
        m=re.fullmatch(r'other_small_(\d+)',n)
        if m:
            kind,rect,axis,geo=meta['placements'][int(m[1])];v.update(family='配件机或塑形机候选摆位',xy=[rect[0]+rect[2]/2,rect[1]+rect[3]/2]);continue
        m=re.fullmatch(r'(input_side|two_input_exception|repeat)(\d+)',n)
        if m:
            typ,idx=m.groups();v.update(family={'input_side':'大制造单位存货边选择','two_input_exception':'大制造单位双存货端口例外','repeat':'重复供电计数'}[typ],xy=info[int(idx)]['xy']);continue
        if n.startswith('cell'):
            x,y=ast.literal_eval(n[4:]);v.update(family='结构占格状态',xy=[x+.5,y+.5]);continue
        if n.startswith('available_'):
            _,x,y=n.split('_');v.update(family='剩余可用且得电的3×3中心',xy=[int(x)+.5,int(y)+.5]);continue
        if n.startswith('free_group'):
            gx,gy=ast.literal_eval(n[len('free_group'):]);v.update(family='剩余可用格组指示',xy=[3*gx+1.5,3*gy+.5],group=[gx,gy]);continue
        if n.startswith('warehouse_pattern'):v.update(family='仓库取货口联合边带模式');continue
        if n.startswith('warehouse_gap') or n.startswith('gap('):v.update(family='仓库取货口边带缺格');continue
        if n.startswith('line_'):v.update(family='边段投影辅助计数');continue
        if n in ('P','J','S'):v.update(family={'P':'供电桩总数','J':'占边供电桩数','S':'面积缺口总账'}[n]);continue
        if not n:v.update(family='常量辅助变量');continue
    assert not [v['name'] for v in info if v['family']=='未归类'], [v['name'] for v in info if v['family']=='未归类'][:10]
    return info

def ref(i): return i if i>=0 else -i-1

def constraint_refs(proto, idx, seen=None):
    """All variable references, including enforcement; intervals are constraint IDs."""
    c=proto.constraints[idx];kind=c.WhichOneof('constraint');r=set(map(ref,c.enforcement_literal));q=getattr(c,kind) if kind else None
    def add(xs):r.update(map(ref,xs))
    def expr(e):add(e.vars)
    if kind in ('bool_or','bool_and','at_most_one','exactly_one','bool_xor'):add(q.literals)
    elif kind=='linear':add(q.vars)
    elif kind in ('int_div','int_mod','int_prod','lin_max'):
        expr(q.target)
        for e in q.exprs:expr(e)
    elif kind=='all_diff':
        for e in q.exprs:expr(e)
    elif kind=='element':
        if q.HasField('linear_index'):
            expr(q.linear_index);expr(q.linear_target)
            for e in q.exprs:expr(e)
        else:add([q.index,q.target]);add(q.vars)
    elif kind in ('table','automaton'):
        add(q.vars)
        for e in q.exprs:expr(e)
    elif kind=='inverse':add(q.f_direct);add(q.f_inverse)
    elif kind in ('circuit','routes'):add(q.literals)
    elif kind=='reservoir':
        for e in list(q.time_exprs)+list(q.level_changes):expr(e)
        add(q.active_literals)
    elif kind=='interval':
        for e in (q.start,q.size,q.end):expr(e)
    elif kind in ('no_overlap','no_overlap_2d','cumulative'):
        ids=list(q.intervals) if kind!='no_overlap_2d' else list(q.x_intervals)+list(q.y_intervals)
        for j in ids:r.update(constraint_refs(proto,j))
        if kind=='cumulative':
            expr(q.capacity)
            for e in q.demands:expr(e)
    elif kind=='dummy_constraint':add(q.vars)
    elif kind is not None:raise ValueError('Unsupported constraint type '+kind)
    return sorted(r)

def build(which):
    start=time.monotonic();bodies=None
    if which.startswith('flow_'):
        directory=ROOT/'求解器/几何/1113流量层';sys.path.insert(0,str(directory))
        mod=importlib.import_module('flow_model_global')
        pos=next(p for p in json.loads((directory/'inputs/positions.json').read_text()) if p['rect']==[49,17,21,53])
        model,meta=mod.build(pos,layer=which[5:],cut_mode='formal')
        settings=dict(position=pos,layer=which[5:],cut_mode='formal',boundary_cuts=False,allowed_P=[10,11,12],patterns=list(range(47)))
    elif which=='geometry':
        directory=ROOT/'求解器/几何/1113放松';sys.path.insert(0,str(directory))
        mod=importlib.import_module('solve_relaxation')
        pos=next(p for p in json.loads((directory/'positions.json').read_text())['candidates'] if p['rect']==[49,17,21,53])
        model,meta=mod.build(pos,boundary_cuts=False)
        settings=dict(position=pos,boundary_cuts=False)
    elif which=='residual75':
        directory=ROOT/'求解器/候选约束轮次/第75-77轮/推导75';sys.path.insert(0,str(directory))
        cp72=importlib.import_module('cp72');cp72.ROUNDS=directory.parents[1]
        source=directory/'residual_model75.py';tree=ast.parse(source.read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        # Execute only the existing construction statements, stopping before a.fixed.
        # A has no fixed bodies, no chosen witness, no solve or source-directory writes.
        begin=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='start' for t in n.targets))
        end=next(i for i,n in enumerate(main.body) if isinstance(n,ast.If) and isinstance(n.test,ast.Attribute) and n.test.attr=='fixed')
        prefix=ast.Module(body=main.body[begin:end],type_ignores=[])
        a=types.SimpleNamespace(encoding='A',cap=187,shift=[0,1])
        ns=dict(a=a,time=time,cp72=cp72,ast=ast,defaultdict=collections.defaultdict)
        exec(compile(prefix,str(source),'exec'),ns)
        model=ns['m'];bodies=ns['bs'];meta={}
        settings=dict(encoding='A',cap=187,shift=[0,1],fixed=None,position=[49,17,21,53],centers=len(ns['centers']),groups=len(ns['classes']),construction_source=str(source.relative_to(ROOT)),ast_statement_start=main.body[begin].lineno,ast_statement_end=main.body[end-1].end_lineno)
    else:raise ValueError(which)
    seconds=time.monotonic()-start
    dest=OUT/'models'/which;dest.mkdir(exist_ok=True)
    err=model.validate();assert not err,err
    assert not model.has_objective()
    model.export_to_file(str(dest/'model.pb'))
    p=cp_model_pb2.CpModelProto();p.ParseFromString((dest/'model.pb').read_bytes())
    variables=variable_info(model,meta,bodies)
    dump(dest/'variables.json',variables)
    offsets=[0];pins=[];kinds=[]
    for i,c in enumerate(p.constraints):
        edge=constraint_refs(p,i);assert all(0<=v<len(p.variables) for v in edge)
        pins.extend(edge);offsets.append(len(pins));kinds.append(c.WhichOneof('constraint'))
    assert len(ORIGINS)==len(p.constraints),(len(ORIGINS),len(p.constraints))
    source_list=[None]*len(SOURCES)
    for (file,line),idx in SOURCES.items():source_list[idx]=dict(file=file,line=line)
    dump(dest/'constraint_sources.json',source_list)
    np.savez_compressed(dest/'incidence.npz',offsets=np.array(offsets,dtype=np.int64),pins=np.array(pins,dtype=np.int32),source=np.array([ORIGINS[i] for i in range(len(p.constraints))],dtype=np.int32))
    lens=np.diff(offsets)
    stats=dict(model=which,settings=settings,variables=len(p.variables),constraints=len(p.constraints),pins=len(pins),constraint_types=dict(collections.Counter(kinds)),max_constraint_variables=int(max(lens)),clique_pair_occurrences=int(sum(int(s)*(int(s)-1)//2 for s in lens)),build_seconds=seconds,extract_seconds=time.monotonic()-start-seconds,model_sha256=hashlib.sha256((dest/'model.pb').read_bytes()).hexdigest(),validated=True,solver_called=False,sources=[dict(file=str(f.relative_to(ROOT)),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(READS) if f.exists()])
    dump(dest/'metadata.json',stats)
    print(json.dumps(stats,ensure_ascii=False),flush=True)

if __name__=='__main__':build(sys.argv[1])
