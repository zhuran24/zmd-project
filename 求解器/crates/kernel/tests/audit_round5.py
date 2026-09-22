"""第五轮独立审计：schema、台账逐事务、键参考、真实CLI重跑及覆盖范围。"""
from pathlib import Path
import json,sys,subprocess,hashlib,copy,collections,itertools
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'数据/样例';E=ROOT/'crates/kernel/evidence/round5'
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT/'规格/第五轮规格修订'))
from test_runtime_input import validate_schema
from checkpoint_delta import decode_trace
from cycle_key_reference import cycle_key as reference_key
SCHEMA=json.loads((ROOT/'规格/内核输出.schema.json').read_text())
BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
PRODUCTS=('高容谷地电池','精选荞愈胶囊');FLOWS=('core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment')
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def n(v):return int(v['value'])
def time(v):return n(v['value'])
def counts(state):return collections.Counter({r['item']:n(r['quantity'])for r in state['warehouse']['slots']if r['item']})
def boxes(state,box_ids):
    out={u:collections.Counter()for u in box_ids}
    for r in state['inventory']:
        u=r['slot'].split(':')[0]
        if u in out:
            for c in r['contents']:out[u][c['item']]+=n(c['quantity'])
    return out

def audit_ledger(record,data):
    trace=decode_trace(record['trace']);previous=trace['start_state'];unit={u['id']:u['kind']for u in data['layout']['units']};channels={c['id']:c for c in data['layout']['physical_channels']};assignments={r['port']:r['slot']for r in data['settings']['warehouse_assignments']}
    for index,tick in enumerate(trace['ticks']):
        expected_time=time(previous['environment']['time'])+(index>0 or previous['semantic_context']['judgment_context']['value']['phase']=='after_closure')
        assert time(tick['time'])==expected_time
        ledger=tick['warehouse_ledger'];assert ledger['player_withdrawal']==[]
        raw_totals={p:{f:0 for f in FLOWS}for p in PRODUCTS}
        for f in FLOWS:
            for row in ledger[f]:
                assert n(row['quantity'])>0
                raw_totals.setdefault(row['item'],{k:0 for k in FLOWS})[f]+=n(row['quantity'])
        expected=[]
        for item,t in sorted(raw_totals.items()):
            t['actual_inbound']=t['core_inbound']+t['wireless_inbound']
            expected.append(dict(item=item,**{k:{'value':str(v),'category':'算术推论'}for k,v in t.items()}))
        assert ledger['totals']==expected
        before=counts(previous);after=counts(tick['state'])
        for item,t in raw_totals.items():before[item]+=t['actual_inbound']+t['external_supply']-t['port_outbound']-t['player_withdrawal']-t['representative_adjustment']
        assert +before==+after and all(v>=0 for v in before.values())
        movements={r['event']:r for r in tick['state']['semantic_context']['tick_context']['value']['movements']}
        stock=boxes(previous,[u for u,k in unit.items()if k=='协议储存箱'])
        core=[];outbound=[];wireless=[];external=[]
        for event in tick['events']:
            eid=event['event']
            if event['operation']=='move' and event['outcome']=='success':
                move=movements[eid];c=channels[move['channel']];src=c['source_port'];dst=c['target_port'];item=move['item'];assert n(move['quantity'])==1
                a,b=src.split(':')[0],dst.split(':')[0]
                if a in stock:stock[a][item]-=1;assert stock[a][item]>=0
                if b in stock:stock[b][item]+=1
                if unit[b]=='协议核心':core.append(dict(event=eid,channel=c['id'],port=dst,item=item,quantity={'value':'1','category':'算术推论'}))
                if src in assignments:
                    outbound.append(dict(event=eid,channel=c['id'],port=src,slot=assignments[src],item=item,quantity={'value':'1','category':'算术推论'}))
                    supply=data['parameters']['fixedness_unproven']['warehouse.external_supply']['value']
                    if supply['kind']=='sufficient' and item in ('源矿','蓝铁矿'):external.append(dict(event=eid,mode='sufficient',item=item,quantity={'value':'1','category':'算术推论'}))
            if event['operation']=='transfer' and event['outcome']=='success':
                u=event['target']
                for item,q in sorted(stock[u].items()):
                    if q:wireless.append(dict(event=eid,unit=u,item=item,quantity={'value':str(q),'category':'算术推论'}))
                stock[u].clear()
            if event['operation']=='ore_supply':
                row=json.loads(event['detail']);external.append(dict(event=eid,mode='explicit_ore_history',item=row['item'],quantity={'value':str(n(row['quantity'])),'category':'算术推论'}))
        assert ledger['core_inbound']==core and ledger['port_outbound']==outbound and ledger['wireless_inbound']==wireless and ledger['external_supply']==external
        assert {u:+v for u,v in stock.items()}=={u:+v for u,v in boxes(tick['state'],stock).items()}
        if record['execution_mode']=='finite_concrete':assert not ledger['representative_adjustment']
        else:assert {r['item']:n(r['quantity'])for r in ledger['representative_adjustment']}=={p:counts(previous)[p]for p in PRODUCTS if counts(previous)[p]}
        previous=tick['state']
    return len(trace['ticks'])

def audit_record(path):
    record=read(path);validate_schema(record,SCHEMA,SCHEMA)
    input_path=next(Path(r['path'])for r in record['fingerprints']if r['role']=='input');data=read(input_path)
    for r in record['fingerprints']:assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'],r['path']
    count=audit_ledger(record,data)
    result=subprocess.run([str(BIN),'verify-record',str(path),'--config',str(CFG)],capture_output=True,text=True)
    assert result.returncode==0,(path,result.stdout,result.stderr)
    return dict(path=str(path),ticks=count,ledger='逐事件/逐物种通过',rust_replay='整份记录逐字段通过')

def audit_bridge_first_contact(record, data):
    """输出§1、K6：直接核方向锚点及事件种类，不能从生产者覆盖标签推实际定向。"""
    bridges=[u for u in data['layout']['units'] if u['kind']=='桥接器']
    row=next(r for r in record['uncovered_axes'] if r['axis']=='connection.bridge_first_contact')
    if not bridges:
        assert row['coverage_status']=='not_exercised'
        return dict(bridges=[],runtime_events=[],status='not_exercised')
    trace=decode_trace(record['trace']);start=time(trace['start_state']['environment']['time'])
    events={e['id']:e for e in data['timeline']['events']};contacts=[]
    bridge_ids={u['id'] for u in bridges}
    for u in bridges:
        assert all(a['status']=='resolved' and a['input_side'] for a in u['bridge_axes'].values())
    for c in data['timeline']['connection_events']:
        if any(p.split(':')[0] in bridge_ids for p in c['channel'].split('|')[1:]):
            at=time(events[c['event']]['time']);assert at<=start
            contacts.append(dict(event=c['event'],time=at,channel=c['channel']))
    # 本版所有几何/方向先于运行解定；运行操作集合中没有建造或定向操作。
    operations={e['operation'] for tick in trace['ticks'] for e in tick['events']}
    assert operations<= {'move','manufacture','transfer','manufacture_complete','ore_supply',
                         'gate_window_expiry','gate_identity_maintenance'}
    assert row['coverage_status']=='input_checked', '历史已定向桥上的搬运不能算先接执行'
    return dict(bridges=sorted(bridge_ids),seed_time=start,historical_contacts=contacts,
                runtime_events=[],status='input_checked',reason='固定已建成段未执行先接定向')

def polling_check(record):
    trace=decode_trace(record['trace']);firsts=('a0','b0','c0');entered={};exits=[];sent=[]
    for tick in trace['ticks']:
        t=time(tick['time']);moves={r['event']:r for r in tick['state']['semantic_context']['tick_context']['value']['movements']}
        for e in tick['events']:
            if e['operation']!='move' or e['outcome']!='success':continue
            move=moves[e['event']];_,src,dst=move['channel'].split('|');a,b=src.split(':')[0],dst.split(':')[0]
            if a in firsts:
                assert a in entered and t-entered.pop(a)==1,(a,t,entered)
                exits.append((a,t))
            if a=='furnace':
                assert not entered,('下个供货组前首格没有全部释放',t,entered)
                assert b in firsts and move['item']=='蓝铁块';entered[b]=t;sent.append((b,t))
    prefix=collections.Counter()
    for u,_ in sent:
        prefix[u]+=1;assert max(prefix[v]for v in firsts)-min(prefix[v]for v in firsts)<=1
    counts=collections.Counter(u for u,_ in sent);assert len(counts)==3 and max(counts.values())-min(counts.values())<=1
    assert all(b[1]-a[1]==1 for a,b in zip(sent,sent[1:]));assert len(sent)>12
    return dict(status='pass',scope='已记录有限前缀；末刻新收件未观察到未来释放',groups=len(sent),counts=dict(counts),one_tick_releases=len(exits),supply='真实仓库蓝铁矿口→运输链→精炼炉；每组1，相邻和2≤3',remaining='有限箱容纳不证明无限接收；六局部序不等于全参数族')

def main():
    names=['混做粉碎机两下游','分流器三路轮询','桥接器双通路','传输拒收与暂停核验','研磨混做核验','阻尼切支恢复核验','阻尼连续带核验','生产循环环带','轮询均分核验','密集结点核验','密集结点闭环核验','密集结点循环种子核验']
    names += [f'轮询均分序{i}核验' for i in range(6)]
    names += [f'密集制造闭环序{i}核验' for i in range(6)]
    reports=[audit_record(BASE/(n+'-运行记录-v3-kernel.json'))for n in names]
    for name in names[:2]:reports.append(audit_record(BASE/(name+'-运行记录-checkpoint_delta-v3-kernel.json')))
    cycles=[]
    for name in ['生产循环环带','密集结点核验','密集结点闭环核验','密集结点循环种子核验']+[f'密集制造闭环序{i}核验' for i in range(6)]:
        path=BASE/(name+'-周期证书-kernel.json');result=read(path);validate_schema(result,SCHEMA,SCHEMA)
        if result['cycle']:
            c=result['cycle'];assert reference_key(c['start_state'])==c['start_key'];assert reference_key(c['end_state'])==c['end_key']
            period=n(c['period']);start=time(c['start_time']);end=time(c['end_time'])
            assert period>0 and end-start==period
            for state in (c['start_state'],c['end_state']):assert state['semantic_context']['judgment_context']['value']['phase']=='after_closure'
            assert c['start_key']==c['end_key']
            trace=decode_trace(result['run_record']['trace'])
            segment=[dict(time=r['time'],warehouse_ledger=r['warehouse_ledger']) for r in trace['ticks'] if start<time(r['time'])<=end]
            assert len(segment)==period and c['ledger']==segment
            accumulated={p:{f:0 for f in FLOWS}for p in PRODUCTS}
            for row in segment:
                for f in FLOWS:
                    for transaction in row['warehouse_ledger'][f]:accumulated.setdefault(transaction['item'],{k:0 for k in FLOWS})[f]+=n(transaction['quantity'])
            expected=[]
            for item,amounts in sorted(accumulated.items()):
                amounts['actual_inbound']=amounts['core_inbound']+amounts['wireless_inbound']
                expected.append(dict(item=item,**{k:{'value':str(v),'category':'算术推论'}for k,v in amounts.items()}))
            assert c['totals']==expected
            assert [r['item']for r in c['rates']]==list(PRODUCTS)
            for row,target in zip(c['rates'],(Fraction(3,5),Fraction(11,20))):
                inbound=accumulated[row['item']]['actual_inbound'];average=Fraction(inbound,period)
                assert n(row['inbound'])==inbound and n(row['period'])==period
                assert Fraction(row['average']['value'])==average and Fraction(row['target']['value'])==target
                assert row['comparison']==('lt'if average<target else'eq'if average==target else'gt')

        process=subprocess.run([str(BIN),'verify-cycle',str(path),'--config',str(CFG)],capture_output=True,text=True)
        assert process.returncode==0,(name,process.stdout,process.stderr)
        cycles.append(dict(path=str(path),status=result['status'],verification=json.loads(process.stdout)))
    coverage={};bridge_audit=[]
    for name in names:
        r=read(BASE/(name+'-运行记录-v3-kernel.json'))
        bridge_audit.append(dict(name=name,**audit_bridge_first_contact(r,read(BASE/(name+'.json')))))
        for a in r['uncovered_axes']:
            if a['coverage_status']=='exercised':coverage.setdefault(a['axis'],[]).append(name)
    config=read(CFG);required=[a for a in config['axes']if a.startswith(('transfer.','bridge.'))]+['connection.bridge_first_contact','warehouse.delivery_count','warehouse.empty_slot_identity','warehouse.external_supply','damping.branch','damping.belt_adjacency','damping.belt_component_rule']+[a for a in config['axes']if a.startswith('manufacturing.')]
    missing=[a for a in required if a not in coverage]
    reasons={'connection.bridge_first_contact':'运行支持域只接已建成且桥方向已解的布局；先接历史仅作input_checked，需建造/方向变更转移才能取得运行证据。',
             'transfer.resume_event':'运行段供电和开关固定；暂停后重新启用所需的调试/离线后效未实现。'}
    reasons['damping.belt_adjacency']='本版path_runs只计路径带串，不读取几何邻接轴；须实现geometric_components后才能获得运行证据。'
    for name in names:
        record=read(BASE/(name+'-运行记录-v3-kernel.json'))
        axis=next(a for a in record['uncovered_axes'] if a['axis']=='damping.belt_adjacency')
        assert axis['coverage_status']=='not_exercised'
        assert not any('belt_adjacency:' in b for t in record['trace']['ticks'] for e in t['events'] for b in e['basis'])
    assert set(missing)==reasons.keys(), missing
    write(E/'bridge-first-contact-audit.json',dict(status='pass',cases=bridge_audit,
          missing_reason=reasons['connection.bridge_first_contact']))
    polling=polling_check(read(BASE/'轮询均分核验-运行记录-v3-kernel.json'))
    variants=[dict(input=str(BASE/(f'轮询均分序{i}核验.json')),**polling_check(read(BASE/(f'轮询均分序{i}核验-运行记录-v3-kernel.json')))) for i in range(6)]
    write(E/'polling-six-orders.json',dict(status='pass',cases=variants,scope='当前来源下六局部顺序的实际回放，不代替全局全序约减'))
    validate_schema(read(E/'invalid-cycle-result.json'),SCHEMA,SCHEMA)
    dense=read(BASE/'密集结点核验-运行记录-v3-kernel.json');flux=collections.Counter(e['target']for t in dense['trace']['ticks']for e in t['events']if e['operation']=='move'and e['outcome']=='success'and e['target'].split('|')[-1].startswith('merge:'))
    from audit_dense_round5 import main as audit_dense
    dense_periods=audit_dense()
    result=dict(status='pass',records=reports,cycles=cycles,coverage=coverage,required_unexercised=missing,required_unexercised_reasons={a:reasons[a] for a in missing},bridge_first_contact=bridge_audit,polling=polling,dense=dict(status='conditional_sensitivity_observed',historical_prefix_flux=dict(flux),manufacturing_cycles=dense_periods,scope='四份周期核过场景前件，两个局部序仍未决；不证明全参数/种子族或一般相容性。'))
    write(E/'audit-results.json',result);print(json.dumps(dict(status='pass',records=len(reports),cycles=len(cycles),missing=missing),ensure_ascii=False))
if __name__=='__main__':main()
