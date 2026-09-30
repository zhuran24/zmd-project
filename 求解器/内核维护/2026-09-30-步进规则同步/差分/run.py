"""只读差分：公开 Rust 库逐步投影 vs 原 sim2；历史目录全量哈希守卫。

cargo build --workspace -j 4 须先由本轮 run.sh 守卫完成；本脚本不调用内核 CLI，
不改样例、源码、规格，不新建 profile。runner 二进制只放调用者的 scratchpad。
"""
from pathlib import Path
import argparse
import copy
import hashlib
import itertools
import json
import os
import random
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
MAINT = HERE.parent
ROOT = MAINT.parents[1]
TOOLS = ROOT / '数据/工具'
SAMPLES = ROOT / '数据/样例/步进/差分'
sys.path[:0] = [str(TOOLS), str(MAINT)]
import guard
import sim2_adapter as adapter
from step_graph import axis as get_axis, build, defaults, poll_state
from step_inputs import axis, q, t, generate
from step_samples import u


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_manifest():
    paths = [p for folder in ['crates/kernel/src', '数据/工具', '规则修订/2026-09-30-迟滞/sim2']
             for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT / '数据/正式静态目录.json', ROOT / '规格/内核配置-v2.json']
    paths += [ROOT.parent / s for s in guard.SOURCES]
    paths += list(SAMPLES.glob('*.json'))
    paths += list(HERE.glob('*.rs')) + list(HERE.glob('*.py'))
    return {str(p): sha(p) for p in sorted(paths)}


def history(raw, variant):
    """改变蓝图两组内的建成次序及同刻通道全序；全部时刻仍由较晚建成者推出。"""
    r = copy.deepcopy(raw)
    seed = int(r['initial_state']['nonwarehouse']['value']['environment']['time']['value']['value'])
    units = {u['id']: u for u in r['layout']['units']}
    nt = [u for u in r['construction']['selected_order'] if units[u]['kind'] != '传送带']
    belts = [u for u in r['construction']['selected_order'] if units[u]['kind'] == '传送带']
    rng = random.Random(91300 + variant)
    if variant == 1:
        nt.reverse(); belts.reverse()
    else:
        rng.shuffle(nt); rng.shuffle(belts)
    selected = nt + belts
    r['construction']['selected_order'] = selected
    event_of = {m['unit']: m['event'] for m in r['construction']['moments']}
    moments = {u: seed - len(selected) - 1 + i for i, u in enumerate(selected)}
    events = {e['id']: e for e in r['timeline']['events']}
    for u in selected:
        events[event_of[u]]['time'] = t(moments[u])
    channels = {c['id']: c for c in r['layout']['physical_channels']}
    for c in r['timeline']['connection_events']:
        a, b = [channels[c['channel']][z].split(':')[0] for z in ('source_port', 'target_port')]
        later = max((a, b), key=moments.get)
        c['cause'] = event_of[later]
        c['construction_basis']['value'].update(source_build=event_of[a], target_build=event_of[b], later_build=event_of[later])
        events[c['event']]['time'] = t(moments[later])
    tie = list(channels)
    rng.shuffle(tie)
    axis(r, 'connection.tie', {'kind':'explicit_order','channels':tie})
    graph = build(r, SAMPLES)
    old_choices = copy.deepcopy(get_axis(r, 'step.order')['layer_choices'])
    new_order = defaults(graph)
    new_order['layer_choices'] = old_choices
    axis(r, 'step.order', new_order)
    return r


def all_choices(raw):
    graph = build(raw, SAMPLES)
    branches = [(c, ds) for c, ds in sorted(graph['candidates'].items()) if len(ds) > 1]
    for values in itertools.product(*(ds for c, ds in branches)):
        r = copy.deepcopy(raw)
        get_axis(r, 'step.order')['layer_choices'] = [{'component':c,'downstream':d} for (c, _), d in zip(branches, values)]
        yield r, ','.join(c + '=' + d for (c, _), d in zip(branches, values)) or 'sole'


def baseline_cases():
    for p in sorted(SAMPLES.glob('*.json')):
        raw = json.loads(p.read_text())
        for variant in range(6):
            source = raw if variant == 0 else history(raw, variant)
            for r, choices in all_choices(source):
                yield p.stem + f'/history-{variant}/' + choices, r, int(raw['scenario']['differential']['steps']), 'required'


def stock_put(raw, slot, item, n, entered=None):
    row = next(r for r in raw['initial_state']['nonwarehouse']['value']['inventory'] if r['slot'] == slot)
    row['contents'] = [] if n == 0 else [dict(item=item, quantity=q(n), entered_at=None if entered is None else t(entered))]


def edge_cases():
    # 合法已知货流边界；共同域不包含协议核心取货、两出口桥轴或部分接收的跨格残留。
    a = json.loads((SAMPLES/'a-纯链.json').read_text())
    for kind in ('working_paused', 'completed_blocked_same_item', 'batch2_flush'):
        r = copy.deepcopy(a)
        st = r['initial_state']['nonwarehouse']['value']
        progress = next(p for p in st['progress'] if p['unit']=='crusher')
        if kind == 'working_paused':
            progress.update(phase='working', recipe='粉碎-源矿', remaining=t(4))
            stock_put(r,'crusher:buffer:0','源矿',1)
            next(s for s in r['settings']['switches'] if s['unit']=='crusher')['enabled']=False
        elif kind == 'completed_blocked_same_item':
            progress.update(phase='completed',recipe='粉碎-源矿',remaining=None)
            stock_put(r,'crusher:buffer:0','源石粉末',1)
            stock_put(r,'crusher:input:0','源石粉末',1)
        elif kind == 'batch2_flush':
            progress.update(phase='completed',recipe='粉碎-荞花',remaining=None)
            stock_put(r,'crusher:buffer:0','荞花粉末',2)
            stock_put(r,'crusher:output:0','荞花粉末',49)
        yield 'edge/'+kind,r,48,'boundary'
    c = json.loads((SAMPLES/'c-换主料.json').read_text())
    # 充足库存的两种收货时间线，分别产生连续两批主料和交替两批主料的 16 步周期。
    for kind in ('same_main_16', 'alternating_main_16'):
        r=copy.deepcopy(c)
        for slot in r['initial_state']['nonwarehouse']['value']['inventory']:
            if slot['slot'].startswith(('a','b','sand')):
                slot['contents']=[]
        if kind=='same_main_16':
            stock_put(r,'m:input:0','源石粉末',50)
        else:
            # a/b 带端预置成熟两件，辅助格预装；另一主料提前一轮排队。
            for prefix,item in [('a','源石粉末'),('b','蓝铁粉末')]:
                stock_put(r,prefix+'15:transport:0',item,1,-8)
                stock_put(r,prefix+'14:transport:0',item,1,-8)
        yield 'c-extra/'+kind,r,100,'boundary'
    for case in (1,2):
        specs=[u('crusher','粉碎机',10,30),u('power','供电桩',14,30),u('out','传送带',11,33),u('core','协议核心',10,34)]
        for prefix,x in ([('a',10),('b',12)] if case==1 else [('ab',11)]):
            specs += [u(prefix+str(i),'传送带',x,14+i) for i in range(16)]
        r=generate({'units':specs},SAMPLES)
        for prefix,x in ([('a',10),('b',12)] if case==1 else [('ab',11)]):
            for i in range(16):
                item=('源矿' if prefix=='a' else '蓝铁块') if case==1 else ('源矿' if (15-i)%2==0 else '蓝铁块')
                stock_put(r,prefix+str(i)+':transport:0',item,1,-7)
        yield 'c-community/case'+str(case),r,240,'boundary'
    e=json.loads((SAMPLES/'e-汇流.json').read_text())
    for mode in ('near_expiry','quota_exhausted','nonempty_poll'):
        r=copy.deepcopy(e)
        if mode in ('near_expiry','quota_exhausted'):
            counter=r['initial_state']['nonwarehouse']['value']['logistics']['gate_counters'][0]
            counter.update(total_received=q(1),window_received=q(1),window_started_at=t(-39 if mode=='near_expiry' else 0))
            if mode=='quota_exhausted':r['settings']['gates'][0]['total_limit']=q(1)
        else:
            g=build(r,SAMPLES)
            for cur in r['initial_state']['nonwarehouse']['value']['logistics']['poll_state']['cursors']:
                node,side=cur['side'].rsplit(':',1)
                cur['last_success']=g['nodes'][node][side+'s'][-1]
        yield 'edge/gate-'+mode,r,100,'boundary'
    for timing in ('before_send','after_send'):
        wpath=ROOT/'数据/样例/步进/机制/无线空箱.json'
        r=json.loads(wpath.read_text())
        r['catalog']['path']=str((wpath.parent/r['catalog']['path']).resolve())
        r['parameters']['axis_registry']['path']=str((wpath.parent/r['parameters']['axis_registry']['path']).resolve())
        for x in get_axis(r,'transfer.timing')['values']:x['timing']=timing
        yield 'wireless/'+timing,r,100,'boundary'
    for p in sorted((ROOT/'数据/样例/步进/机制').glob('*.json')):
        r=json.loads(p.read_text())
        if r['scenario'].get('expected_stop') or get_axis(r,'warehouse.external_supply')['kind']!='sufficient':
            continue
        graph=build(r,p.parent)
        if any(n['kind']=='BeltRing' or (n['kind']=='桥接器' and len(n['outputs'])>1) or (n['kind']=='协议核心' and n['outputs']) for n in graph['nodes'].values()):
            continue
        # 原样例引用相对其自身目录，改为绝对引用才能使用统一差分 base。
        for key in ['catalog']:
            r[key]['path']=str((p.parent/r[key]['path']).resolve())
        r['parameters']['axis_registry']['path']=str((p.parent/r['parameters']['axis_registry']['path']).resolve())
        yield 'mechanism/'+p.stem,r,min(80,r['scenario']['steps']),'boundary'


def reference(raw, steps):
    """投影仍由正式适配器输出；插桩只读取判定后的轮询、计数和原 sim2 事件。"""
    extras={'polls':[],'gates':[],'events':[],'graph':None}
    original_adapt=adapter.adapt
    def inspect_adapt(*args):
        w,g,nodes,slots,wh=original_adapt(*args)
        extras['graph']={'layers':w.layers,'order':[u.name for u in w.order], 'rank':g['rank']}
        cursors={x['side']:x['last_success'] for x in raw['initial_state']['nonwarehouse']['value']['logistics']['poll_state']['cursors']}
        old_step=w.step
        def inspect_step():
            start=len(w.events)
            old_step()
            ev=w.events[start:]
            for e in ev:
                if e['event']!='send':continue
                matching=[cid for cid,(a,b) in g['ends'].items() if a==e['unit'] and b==e['destination']]
                if len(matching)!=1:raise ValueError('差分插桩要求通道对应的端点对唯一')
                cid=matching[0]
                for side in (e['unit']+':output',e['destination']+':input'):
                    if side in cursors:cursors[side]=cid
            recency=[]
            for row in raw['initial_state']['nonwarehouse']['value']['logistics']['poll_state']['recency']:
                n=nodes[row['unit']]
                successful=[c for c in n.output_channels if n.last_output[c]>=0 or any(g['rank'][cid]==c.connected for cid in row['order'])]
                successful.sort(key=lambda c:n.last_output[c])
                recency.append({'unit':row['unit'],'order':[next(cid for cid in g['ends'] if g['rank'][cid]==c.connected) for c in successful]})
            extras['polls'].append({'schema':'poll-state-v1','cursors':[{'side':s,'last_success':v} for s,v in sorted(cursors.items())],'recency':recency})
            gates=[]
            for name,n in sorted(nodes.items()):
                if not isinstance(n,adapter.ConfiguredGate):continue
                started=n.started
                received=n.received
                if started is not None and started+40<=w.t:started=None;received=0
                gates.append({'unit':g['nodes'][name]['unit'],'total_received':q(n.total),'window_received':q(received),'window_started_at':None if started is None else t(started)})
            gates.sort(key=lambda r:r['unit'])
            extras['gates'].append(gates)
            extras['events'].append(ev)
        w.step=inspect_step
        return w,g,nodes,slots,wh
    adapter.adapt=inspect_adapt
    try:rows=adapter.projections(raw,SAMPLES,steps)
    finally:adapter.adapt=original_adapt
    extras['rows']=rows
    return extras


def first_difference(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return {'path':path+'.keys','kernel':sorted(a),'sim2':sorted(b)}
        for k in sorted(a):
            d=first_difference(a[k],b[k],path+'.'+k)
            if d:return d
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return {'path':path+'.length','kernel':len(a),'sim2':len(b)}
        for i,(x,y) in enumerate(zip(a,b)):
            d=first_difference(x,y,path+f'[{i}]')
            if d:return d
    elif a!=b:return {'path':path,'kernel':a,'sim2':b}
    return None


def numeric_gate_rows(rows):
    # Quantity.category 是内核证据分类，sim2 只有整数；不把证据标签当动力学差异。
    return [[dict(unit=g['unit'], total_received=int(g['total_received']['value']),
                  window_received=int(g['window_received']['value']),
                  window_started_at=None if g['window_started_at'] is None else int(g['window_started_at']['value']['value']))
             for g in row] for row in rows]


def compile_runner(scratch):
    exe=scratch/'differential-runner'
    # 共享 target 留有不同 feature/profile 的同版本 serde_json；以编译期类型身份核匹配。
    diagnostics=[]
    for dependency in sorted((ROOT/'target/debug/deps').glob('libserde_json-*.rlib')):
        command=['rustc','--edition=2021',str(HERE/'runner.rs'),'-L','dependency='+str(ROOT/'target/debug/deps'),'--extern','kernel='+str(ROOT/'target/debug/libkernel.rlib'),'--extern','serde_json='+str(dependency),'-o',str(exe)]
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode==0:return exe,command
        diagnostics.append(result.stderr)
    raise RuntimeError('观察器编译失败：'+'\n'.join(diagnostics))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scratch',type=Path,required=True)
    p.add_argument('--label',required=True)
    p.add_argument('--mode',choices=['required','all','edges'],default='all')
    args=p.parse_args()
    assert args.scratch.is_dir()
    assert args.label.replace('-','').isalnum()
    output=HERE/(args.label+'.json')
    assert not output.exists(), output
    before=guard.guard(args.label+'-before')
    sources=source_manifest()
    started=time.monotonic()
    cases=[]; mismatches=[]; errors=[]; command=[]
    try:
        exe,command=compile_runner(args.scratch)
        variants=[]
        if args.mode!='edges':variants.extend(baseline_cases())
        if args.mode!='required':variants.extend(edge_cases())
        for name,raw,steps,group in variants:
            job=dict(name=name,input=raw,steps=steps,base=str(SAMPLES),config=str(ROOT/'规格/内核配置-v2.json'))
            result=subprocess.run([str(exe)],input=json.dumps(job,ensure_ascii=False)+'\n',text=True,capture_output=True)
            if result.returncode:
                errors.append(dict(name=name,rust_stderr=result.stderr));continue
            got=json.loads(result.stdout)
            row=dict(name=name,group=group,steps=steps,input_sha256=hashlib.sha256(json.dumps(raw,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
            if 'error' in got:
                row['kernel_error']=got['error'];errors.append(row);continue
            try:expected=reference(raw,steps)
            except Exception as e:
                row['sim2_error']=repr(e);errors.append(row);continue
            row['graph']=got['graph']
            row['projection_diff']=first_difference(got['rows'],expected['rows'],'rows')
            row['poll_diff']=first_difference(got['polls'],expected['polls'],'polls')
            row['gate_diff']=first_difference(numeric_gate_rows(got['gates']),numeric_gate_rows(expected['gates']),'gates')
            # 未写送货通道的元件位置不可观察，独立次序核对只比较有送货通道的主体。
            row['layer_diff']=first_difference(got['graph']['layers'],expected['graph']['layers'],'layers')
            visible={n for n,x in build(raw,SAMPLES)['nodes'].items() if not n.startswith('C|') or x['outputs']}
            row['order_diff']=first_difference([n for n in got['graph']['order'] if n in visible],[n for n in expected['graph']['order'] if n in visible],'order')
            row['starts']=[(e['t'],e['unit'],e['kind']) for events in expected['events'] for e in events if e['event']=='start']
            row['sends']=[(e['t'],e['unit'],e['destination'],e['kind']) for events in expected['events'] for e in events if e['event']=='send']
            cases.append(row)
            if any(row[k] for k in ('projection_diff','poll_diff','gate_diff','layer_diff','order_diff')):
                detail=dict(name=name,input=raw,base=str(SAMPLES),kernel=got,sim2=expected)
                witness=args.scratch/(hashlib.sha256(name.encode()).hexdigest()[:16]+'.json')
                witness.write_text(json.dumps(detail,ensure_ascii=False))
                mismatches.append(dict(name=name,witness=str(witness),**{k:row[k] for k in ('projection_diff','poll_diff','gate_diff','layer_diff','order_diff')}))
            print(json.dumps({'name':name,'steps':steps,'equal':not any(row[k] for k in ('projection_diff','poll_diff','gate_diff','layer_diff','order_diff'))},ensure_ascii=False),flush=True)
    finally:
        after=guard.guard(args.label+'-after')
        delta=guard.difference(before['files'],after['files'])
        source_delta=guard.difference(sources,source_manifest())
        report=dict(schema='kernel-sim2-differential-v1',label=args.label,mode=args.mode,runner_compile=command,kernel_library_sha256=sha(ROOT/'target/debug/libkernel.rlib'),sources=sources,source_changes=source_delta,history=dict(counts=before['counts'],before_sha256=sha(MAINT/(args.label+'-before-history.json')),after_sha256=sha(MAINT/(args.label+'-after-history.json')),difference=delta),seconds=round(time.monotonic()-started,3),cases=cases,mismatches=mismatches,errors=errors)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(report=str(output),cases=len(cases),steps=sum(c['steps'] for c in cases),mismatches=len(mismatches),errors=errors,source_changes=source_delta,history_difference=delta),ensure_ascii=False),flush=True)
    if any(delta.values()) or any(source_delta.values()):raise RuntimeError('运行期间历史或被核对来源发生变化，结论须重跑')

if __name__=='__main__':main()
