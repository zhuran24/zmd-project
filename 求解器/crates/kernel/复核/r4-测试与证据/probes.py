#!/usr/bin/env python3
"""轴执行证据、最终规格D.2与schema独立复核。"""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
BASE=ROOT/'数据/样例'
BIN=ROOT/'target/release/kernel'
CFG=ROOT/'规格/内核配置-v1.json'
REPORT=json.loads((OUT/'probe-commands.json').read_text()) if (OUT/'probe-commands.json').exists() else []
def read(p):return json.loads(Path(p).read_text())
def save(name,v):
    p=OUT/name;p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');return p
def command(name,mode,source,expected=0,extra=()):
    out=OUT/(name+'.json')
    args=[str(BIN),mode,str(source),'--config',str(CFG),'--out',str(out),*map(str,extra)]
    p=subprocess.run(args,capture_output=True,text=True,timeout=90)
    REPORT.append(dict(command=args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
    save('probe-commands.json',REPORT)
    assert p.returncode==expected,REPORT[-1]
    return read(out)
def source(path):
    data=read(path)
    for r in [data['catalog'],data['parameters']['axis_registry']]:r['path']=str((path.parent/r['path']).resolve())
    return data
def set_axis(data,axis,value):
    for section in ['fixed','variable_after_offline','fixedness_unproven']:
        if axis in data['parameters'].get(section,{}):data['parameters'][section][axis]['value']=copy.deepcopy(value)
    for row in data['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis']==axis:row['value']['value']=copy.deepcopy(value)

def d2():
    results=[]
    for mode in ['pc','box']:
        for count in [79999,80000]:
            origin=ROOT/'crates/kernel/tests/fixtures/core_inbound.json' if mode=='pc' else BASE/'生产循环环带.json'
            data=source(origin)
            seed=data['initial_state']['nonwarehouse']['value']
            set_axis(data,'warehouse.external_supply',{'kind':'sufficient'})
            next(r for r in seed['warehouse']['slots']if r['item']=='源矿')['quantity']['value']=str(count)
            slot='belt:transport:0' if mode=='pc' else 'box:storage:0'
            next(r for r in seed['inventory']if r['slot']==slot)['contents']=[dict(item='源矿',
                quantity={'value':'1','category':'候选'},entered_at={'kind':'rational','value':{'value':'-1','category':'候选'}})]
            name=f'd2-{mode}-{count}'
            path=save(name+'-input.json',data)
            command(name+'-seed','seed',path)
            seed_path=OUT/(name+'-seed.json')
            finite=command(name+'-run','run',seed_path,extra=['--ticks',1])
            cycle=command(name+'-cycle','cycle',seed_path,expected=2,extra=['--max-ticks',2])
            assert finite['status']=='completed'
            assert cycle['status']=='stopped' and cycle['stop']['axis']=='cycle.domain.D2' and cycle['cycle'] is None
            assert cycle['budget']['completed_ticks']==0
            tick=finite['trace']['ticks'][0]
            flow='core_inbound' if mode=='pc' else 'wireless_inbound'
            amount=sum(int(r['quantity']['value'])for r in tick['warehouse_ledger'][flow]if r['item']=='源矿')
            assert amount==(1 if count==79999 else 0)
            results.append(dict(mode=mode,ore=count,finite_ore_inbound=amount,cycle_status=cycle['status'],
                                stop=cycle['stop'],completed_ticks=0))
    save('d2-capacity-before-stop.json',dict(status='pass',cases=results))

def coverage():
    # 新生成含marker的真实记录再交公开verify-record；没有篡改记录。
    r=command('dormant-axis-record','run',BASE/'阻尼连续带核验.json',extra=['--ticks',3])
    v=command('dormant-axis-verified','verify-record',OUT/'dormant-axis-record.json')
    row=next(a for a in r['uncovered_axes']if a['axis']=='damping.belt_adjacency')
    e=next(e for t in r['trace']['ticks']for e in t['events']if e['event']==row['evidence'][0])
    data=read(BASE/'阻尼连续带核验.json')
    values={a:row['value'] for s in ['fixed','fixedness_unproven','variable_after_offline']
            for a,row in data['parameters'].get(s,{}).items()if a.startswith('damping.')}
    save('dormant-axis-evidence.json',dict(record_status=r['status'],axis=row,first_event=e,
         parameters=values,verify_result=v,spec='选择点参数轴.md:40仅geometric_components使用；受限模型声明.md:40明确path_runs不调用该值',
         code='polling.rs:124-127只在belt&&previous_belt写marker，未求几何邻接；output.rs:273-275据marker报exercised'))
    # 对每条要求轴保存原始行及首条事件，机制的条件核验在报告中逐项给出。
    audit=read(ROOT/'crates/kernel/evidence/round5/audit-results.json')
    config=read(CFG)['axes']
    required=[a for a in config if a.startswith(('transfer.','bridge.','manufacturing.'))]+[
        'connection.bridge_first_contact','warehouse.delivery_count','warehouse.empty_slot_identity',
        'warehouse.external_supply','damping.branch','damping.belt_adjacency','damping.belt_component_rule']
    selected={}
    for axis in required:
        names=audit['coverage'].get(axis,[])
        preferred=('传输拒收与暂停核验' if axis in ['transfer.pause','transfer.partial_acceptance','transfer.failure_cooldown']
            else '研磨混做核验' if axis.startswith('manufacturing.') else '桥接器双通路' if axis.startswith(('bridge.','transfer.','warehouse.'))
            else '阻尼切支恢复核验' if axis=='damping.branch' else '阻尼连续带核验')
        name=preferred if preferred in names else names[0] if names else None
        if name is None:
            selected[axis]=dict(status='not_exercised',reason=audit['required_unexercised_reasons'].get(axis));continue
        path=BASE/(name+'-运行记录-v3-kernel.json');record=read(path)
        entry=next(r for r in record['uncovered_axes']if r['axis']==axis)
        events={e['event']:dict(time=t['time'],event=e)for t in record['trace']['ticks']for e in t['events']}
        assert all(e in events for e in entry['evidence'])
        selected[axis]=dict(record=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
           reported_status=entry['coverage_status'],reported_evidence_count=len(entry['evidence']),
           first_event=events[entry['evidence'][0]])
    save('coverage-event-excerpts.json',selected)

def schema():
    schema=read(ROOT/'规格/内核输出.schema.json')
    report=read(OUT/'revision_r3_cli/results.json')
    script="""const fs=require('fs');const Ajv=require(process.argv[1]);
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
const ajv=new Ajv({strict:false,allErrors:true});const validate=ajv.compile(payload.schema);
const results=payload.cases.map(c=>({case:c.case,output:c.output,
status:validate(c.data)?'pass':'fail',errors:structuredClone(validate.errors||[])}));
process.stdout.write(JSON.stringify(results));"""
    rows=[]
    for case in report['cases']:
        data=read(case['output'])
        if data.get('schema')=='kernel-input-v3':continue
        rows.append(dict(case=case['case'],output=case['output'],data=data))
    p=subprocess.run(['node','-e',script,'/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'],
        input=json.dumps(dict(schema=schema,cases=rows),ensure_ascii=False),capture_output=True,text=True,check=True)
    rows=json.loads(p.stdout)
    assert [r['case']for r in rows if r['status']=='fail']==['age-overflow-cycle']
    save('independent-schema.json',dict(validator='AJV2020 independent implementation',passed=sum(r['status']=='pass' for r in rows),
         failed=sum(r['status']=='fail'for r in rows),cases=rows))

def supply():
    original=source(BASE/'轮询均分核验.json')
    records={}
    for mode in ['sufficient','explicit_ore_history']:
        data=copy.deepcopy(original)
        value={'kind':'sufficient'} if mode=='sufficient' else {'kind':mode,'events':[],
            'through':{'kind':'rational','value':{'value':'40','category':'候选'}}}
        set_axis(data,'warehouse.external_supply',value)
        path=save('supply-'+mode+'-input.json',data)
        records[mode]=command('supply-'+mode+'-record','run',path,extra=['--ticks',30])
    a=records['sufficient']['trace']['ticks'];b=records['explicit_ore_history']['trace']['ticks']
    fields=['inventory','progress','logistics','environment']
    counts={}
    for x,y in zip(a,b):
        for field in fields:assert x['state'][field]==y['state'][field]
        for field in ['events','closure','time']:assert x[field]==y[field]
        for field in ['core_inbound','wireless_inbound','port_outbound','player_withdrawal','representative_adjustment']:
            assert x['warehouse_ledger'][field]==y['warehouse_ledger'][field]
    for mode,record in records.items():
        previous=record['trace']['start_state']
        n_out=n_supply=0
        for tick in record['trace']['ticks']:
            before={r['item']:int(r['quantity']['value'])for r in previous['warehouse']['slots']if r['item']}
            after={r['item']:int(r['quantity']['value'])for r in tick['state']['warehouse']['slots']if r['item']}
            for item in before.keys()|after.keys():
                flows={f:sum(int(r['quantity']['value'])for r in tick['warehouse_ledger'][f]if r['item']==item)
                       for f in ['core_inbound','wireless_inbound','external_supply','port_outbound']}
                assert after.get(item,0)-before.get(item,0)==flows['core_inbound']+flows['wireless_inbound']+flows['external_supply']-flows['port_outbound']
                n_out+=flows['port_outbound'];n_supply+=flows['external_supply']
            previous=tick['state']
        assert n_out>0
        if mode=='sufficient':assert n_supply==n_out
        else:assert n_supply==0
        counts[mode]=dict(ore_out=n_out,external_supply=n_supply)
    save('supply-differential.json',dict(status='pass',ticks=30,state_fields=fields,events_equal=True,
         actual_inbound_and_outbound_equal=True,independent_conservation=True,counts=counts,
         scope='未耗尽、无回矿候选、显式历史为空但覆盖40刻；不是耗尽或回矿情形等价证明。'))

def main():
    {'d2':d2,'coverage':coverage,'schema':schema,'supply':supply}[sys.argv[1]]()

if __name__=='__main__':main()
