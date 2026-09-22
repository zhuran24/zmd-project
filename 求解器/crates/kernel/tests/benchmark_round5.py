"""第五轮K7：目录导出的两档合成逻辑通道展开，未冒称候选B真实几何。"""
import json,subprocess,time,hashlib,platform
from pathlib import Path
import build_fixtures as b
from migrate_round5 import migrate,save
from generate_examples import unit
from runtime_example import quantity,time_value,decision
ROOT=b.ROOT;E=ROOT/'crates/kernel/evidence/round5';b.OUT=ROOT/'crates/kernel/tests/fixtures'
def generate(name,machines,logical,columns):
    units=[unit(f'm{i}','精炼炉',1+4*(i%columns),1+4*(i//columns))for i in range(machines)]
    links=[]
    for offset in range(3):
        for i in range(machines-columns):
            if len(links)==logical:break
            links.append((i,i+columns,offset))
    units += [unit(f'b{j}','传送带',1+4*(i%columns)+offset,4+4*(i//columns))for j,(i,_,offset)in enumerate(links)]
    d=b.generate(name,units)
    b.set_axis(d,'warehouse.external_supply',{'kind':'sufficient'})
    seed=d['initial_state']['nonwarehouse']['value']
    for i in range(machines):
        item='源矿' if (i//columns)%2==0 else '蓝铁矿'
        next(r for r in seed['inventory'] if r['slot']==f'm{i}:output:0')['contents']=[dict(item=item,quantity=quantity(50),entered_at=time_value(-1))]
    d=migrate(d);seed=d['initial_state']['nonwarehouse']['value']
    d['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(E/'实施与验证.md'),'scope':'合成压力初态，库存为条件预置；没有证明从任务初值可达'},'第五轮K7合成基准，实际尺寸/端口/容量由目录核验')
    d['scenario']['assertions']=[f'合成规模：{machines}台制造单位，{logical}条直连逻辑段，每段展开为2条PC；条件预装货50件；制造开关关闭，测物流活动及后续阻塞。']
    source=b.OUT/(name+'.json');save(source,d)
    return source,dict(manufacturing_units=machines,total_units=len(d['layout']['units']),logical_channels=logical,physical_channels=len(d['layout']['physical_channels']),inventory_slots=len(seed['inventory']))
def generate_dense_brick():
    units=[unit(f'node{x}_{y}','分流器' if (x+y)%2==0 else '汇流器',10+x,10+y,'r180') for y in range(7) for x in range(8)]
    d=b.generate('benchmark_brick_60',units)
    b.set_axis(d,'warehouse.external_supply',{'kind':'sufficient'})
    for r in d['initial_state']['nonwarehouse']['value']['inventory']:
        u=r['slot'].split(':')[0]
        if next(v for v in units if v['id']==u)['kind']=='分流器':r['contents']=[dict(item='高容谷地电池',quantity=quantity(1),entered_at=time_value(-1))]
    d=migrate(d)
    d['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(E/'实施与验证.md'),'scope':'棋盘运输压力初态，未证明任务起动可达'},'第五轮K7条件库存')
    source=b.OUT/'benchmark_brick_60.json';save(source,d)
    return source,dict(manufacturing_units=0,total_units=len(d['layout']['units']),logical_channels=0,physical_channels=len(d['layout']['physical_channels']),inventory_slots=len(d['initial_state']['nonwarehouse']['value']['inventory']))

def run(stage='before'):
    reports=[]
    binary_digest=hashlib.sha256((ROOT/'target/release/kernel').read_bytes()).hexdigest()
    binary=ROOT/'target/release/kernel';config=ROOT/'规格/内核配置-v1.json'
    for name,m,l,c in [('benchmark_brick_60',0,0,0),('benchmark_brick',30,50,6),('benchmark_candidate_b',219,315,17)]:
        source,shape=generate_dense_brick() if m==0 else generate(name,m,l,c)
        r=subprocess.run([str(binary),'seed',str(source),'--config',str(config),'--out',str(source)],capture_output=True,text=True)
        if r.returncode:raise RuntimeError((name,r.stderr,source.read_text()[:600]))
        command=[str(binary),'run',str(source),'--config',str(config),'--ticks','12','--no-output']
        start=time.perf_counter_ns();r=subprocess.run(command,capture_output=True,text=True);elapsed=time.perf_counter_ns()-start
        if r.returncode:raise RuntimeError((name,r.stdout,r.stderr))
        result=json.loads(r.stdout);ms=int(result['elapsed_ns'])/1e6/12
        reports.append(dict(name=name,**shape,ticks=12,ms_per_tick=ms,target_ms=1 if m!=219 else 20,target_met=ms<=(1 if m!=219 else 20),engine=result,wall_ns=elapsed,command=command,input_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
        print(name,ms,flush=True)
    output=dict(stage=stage,platform=platform.platform(),binary_sha256=binary_digest,reports=reports,scope='合成物流压力测试；砖档57单位/97PC，另保留81单位/100PC的纵向送料对照；候选B档219制造台/315逻辑段/630PC，未声称真实候选B布置可行或制造满载。')
    save(E/f'benchmark-{stage}.json',output)
if __name__=='__main__':
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else 'before')
