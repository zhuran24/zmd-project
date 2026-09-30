"""第五轮K6：从共享目录导出几何，具体参数点和库存来源均显式留档。"""
import sys,json,copy,subprocess
from pathlib import Path
import build_fixtures as b
from migrate_round5 import migrate,save
ROOT=b.ROOT;OUT=ROOT/'数据/样例';b.OUT=OUT
from generate_examples import unit
from runtime_example import quantity as q,time_value as t,decision
BIN=ROOT/'target/release/kernel';CONFIG=ROOT/'规格/内核配置-v1.json'
def put(d,slot,item,n):
    next(r for r in d['initial_state']['nonwarehouse']['value']['inventory'] if r['slot']==slot)['contents']=[dict(item=item,quantity=q(n),entered_at=t(-1))]
def finish(d,name,ticks=30,cycle=False):
    d['scenario']['name']=name
    b.set_axis(d,'warehouse.external_supply',{'kind':'sufficient'})
    if d['initial_state']['reachability'].get('value',{}).get('kind')!='conditional_state':d['initial_state']['reachability']=decision({'kind':'conditional_history','document':'第五轮样例说明-kernel.md','scope':'显式合成有限库存或仓库供料；不声称玩家精确起动可达'},'第五轮K6机制试验的条件种子')
    d=migrate(d)
    source=OUT/(name+'.json');save(source,d)
    canonical=OUT/(name+'-派生临时-kernel.json')
    cmd=[str(BIN),'seed',str(source),'--config',str(CONFIG),'--out',str(canonical)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode:raise RuntimeError((name,r.stderr,canonical.read_text()[:1200]))
    source.write_bytes(canonical.read_bytes());canonical.unlink()
    record=OUT/(name+'-运行记录-v3-kernel.json')
    r=subprocess.run([str(BIN),'run',str(source),'--config',str(CONFIG),'--ticks',str(ticks),'--out',str(record)],capture_output=True,text=True)
    if r.returncode:raise RuntimeError((name,r.stderr,json.loads(record.read_text())['open_items']))
    print(name,'completed',ticks,flush=True)
    if cycle:
        cert=OUT/(name+'-周期证书-kernel.json')
        r=subprocess.run([str(BIN),'cycle',str(source),'--config',str(CONFIG),'--max-ticks',str(ticks),'--out',str(cert)],capture_output=True,text=True)
        print(name,'cycle',r.returncode,json.loads(cert.read_text()).get('status'),flush=True)
    return source

def main():
    d=json.loads((ROOT/'crates/kernel/tests/fixtures/bridge.json').read_text())
    put(d,'south_box:storage:0','高容谷地电池',8);put(d,'west_box:storage:0','精选荞愈胶囊',8)
    for s in d['settings']['switches']:s['enabled']=s['unit'] in ('north_box','east_box')
    finish(d,'桥接器双通路',30)
    d=json.loads((ROOT/'crates/kernel/tests/fixtures/bridge.json').read_text())
    put(d,'south_box:storage:0','高容谷地电池',2);put(d,'south_box:storage:1','砂叶',1)
    for switch in d['settings']['switches']:switch['enabled']=switch['unit']=='south_box'
    next(p for p in d['initial_state']['nonwarehouse']['value']['progress'] if p['unit']=='east_box')['cooldowns'][0]['remaining']=t(3)
    phase=d['parameters']['fixedness_unproven']['transfer.phase']['value']
    next(p for p in phase['values'] if p['unit']=='east_box')['remaining']=t(3)
    finish(d,'传输拒收与暂停核验',12)
    d=b.generate('研磨混做核验',[unit('grinder','研磨机',10,10),unit('feed_a','协议储存箱',9,6),unit('feed_b','协议储存箱',13,6),unit('belt_a','传送带',10,9),unit('belt_b','传送带',14,9),unit('belt_out','传送带',10,14),unit('sink','协议储存箱',10,15),unit('power','供电桩',17,12)])
    put(d,'feed_a:storage:0','蓝铁粉末',2);put(d,'feed_a:storage:1','源石粉末',2);put(d,'feed_b:storage:0','砂叶粉末',2)
    for s in d['settings']['switches']:s['enabled']=s['unit'] in ('grinder','sink')
    finish(d,'研磨混做核验',20)
    d=json.loads((ROOT/'crates/kernel/tests/fixtures/priority.json').read_text())
    put(d,'source:storage:0','高容谷地电池',12)
    finish(d,'阻尼连续带核验',18)
    d=json.loads((ROOT/'crates/kernel/tests/fixtures/revision_r2_branch_cut.json').read_text())
    d['settings']['gates'][0]['total_limit']=None;d['settings']['gates'][0]['window_limit']=q(1)
    put(d,'source:storage:0','源矿',30)
    finish(d,'阻尼切支恢复核验',18)
    d=b.generate('生产循环环带',[unit('a','传送带',10,10,'r90',1),unit('b','传送带',10,11,'r0',1),unit('c','传送带',11,11,'r270',1),unit('d','传送带',11,10,'r180',1),unit('box','协议储存箱',15,10),unit('power','供电桩',19,10)])
    put(d,'a:transport:0','高容谷地电池',1);put(d,'box:storage:0','精选荞愈胶囊',5)
    for s in d['settings']['switches']:s['enabled']=True
    finish(d,'生产循环环带',50,True)
    # 同级三支，每刻先清空下游，再供货/制造/输出。
    units=[unit('source','仓库取货口',9,0),unit('furnace','精炼炉',9,9),unit('power','供电桩',14,9)]
    units += [unit(f'feed_{y}','传送带',10,y) for y in range(1,9)]
    units += [unit('a0','传送带',9,12,'r0',2),unit('a1','传送带',8,12,'r90',1),unit('b0','传送带',10,12),unit('c0','传送带',11,12,'r0',1),unit('c1','传送带',12,12,'r270'),unit('c2','传送带',13,12,'r270',2)]
    units += [unit(f'a{y}','传送带',8,y) for y in range(13,16)]+[unit(f'b{y}','传送带',10,y) for y in range(13,20)]+[unit(f'c{y}','传送带',13,y) for y in range(13,16)]
    units += [unit('box_a','协议储存箱',7,16),unit('box_b','协议储存箱',10,20),unit('box_c','协议储存箱',13,16)]
    d=b.generate('轮询均分核验',units)
    d['settings']['warehouse_assignments'].append(dict(port='source:north:1',slot='warehouse_1'))
    # 源矿格标签不由名字猜测。
    ore=next(r['slot'] for r in d['initial_state']['warehouse']['slots'] if r['item']=='蓝铁矿')
    d['settings']['warehouse_assignments'][-1]['slot']=ore
    for s in d['settings']['switches']:s['enabled']=s['unit']=='furnace'
    order=d['parameters']['fixed']['judgment.order']['value']['template_order']
    out=[r for r in order if r['operation']=='move' and r['target'].startswith('PC|furnace:')]
    other=[r for r in order if r not in out and r['operation']!='manufacture']
    # 下游源口从远到近，保证先释放后收；所有首格出边先于炉口。
    positions={u['id']:int(u['origin'][1]['value']) for u in units}
    other.sort(key=lambda r:-positions.get(r['target'].split('|')[1].split(':')[0],0) if r['operation']=='move' else 0)
    d['parameters']['fixed']['judgment.order']['value']['template_order']=other+[r for r in order if r['operation']=='manufacture']+out
    finish(d,'轮询均分核验',100)
    # 两真实仓库矿口供D/E；M的两直接分流器级接通同刻，另有各自出路。
    units=[unit('source_d','仓库取货口',9,0),unit('source_e','仓库取货口',21,0),unit('fork_d','分流器',10,10),unit('fork_e','分流器',11,11,'r180'),unit('merge','汇流器',11,10,'r180')]
    units += [unit(f'fd{y}','传送带',10,y)for y in range(1,10)]
    units += [unit(f'fe{y}','传送带',22,y)for y in range(1,15)]
    units += [unit('fe_top','传送带',22,15,'r0',2)]+[unit(f'fe_left{x}','传送带',x,15,'r90')for x in range(12,22)]+[unit('fe_turn','传送带',11,15,'r90',2)]+[unit(f'fe_down{y}','传送带',11,y,'r180')for y in (12,13,14)]
    units += [unit('dn0','传送带',10,11,'r0',2),unit('dn1','传送带',9,11,'r90',1),unit('dw','传送带',9,10,'r90'),unit('de','传送带',12,11,'r270'),unit('mo','传送带',11,9,'r180',2)]+[unit(f'mo{x}','传送带',x,9,'r270')for x in range(12,17)]
    units += [unit('sink_dn','协议储存箱',7,12),unit('sink_dw','协议储存箱',6,9,'r90'),unit('sink_e','协议储存箱',13,10,'r270'),unit('sink_m','协议储存箱',17,8,'r270')]
    d=b.generate('密集结点核验',units)
    slot=next(r['slot']for r in d['initial_state']['warehouse']['slots']if r['item']=='源矿')
    d['settings']['warehouse_assignments'] += [dict(port=p+':north:1',slot=slot)for p in ('source_d','source_e')]
    finish(d,'密集结点核验',60,True)
if __name__=='__main__':main()
