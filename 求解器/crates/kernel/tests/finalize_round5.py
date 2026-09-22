"""在当前锁定来源上重新执行；不刷新旧v2产物，不复制仓库或编译缓存。"""
from pathlib import Path
import json,subprocess,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'数据/样例';E=ROOT/'crates/kernel/evidence/round5';BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
sys.path.insert(0,str(BASE))
import check_golden_trace as g
import check_examples as checker
from runtime_record import build_record,validate_record
names={'混做粉碎机两下游':4,'分流器三路轮询':12,'桥接器双通路':30,'传输拒收与暂停核验':12,'研磨混做核验':20,'阻尼连续带核验':18,'阻尼切支恢复核验':18,'生产循环环带':50,'轮询均分核验':100,'密集结点核验':60,'密集结点闭环核验':240,'密集结点循环种子核验':100}
names.update({f'轮询均分序{i}核验':40 for i in range(6)})
reports=[]
for name,count in names.items():
    source=BASE/(name+'.json');out=BASE/(name+'-运行记录-v3-kernel.json')
    command=[str(BIN),'run',str(source),'--config',str(CFG),'--ticks',str(count),'--out',str(out)]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise RuntimeError((name,result.stderr,json.loads(out.read_text())['open_items']))
    reports.append(dict(input=str(source),output=str(out),ticks=count,status='completed'));print(name,flush=True)
for name in ['混做粉碎机两下游','分流器三路轮询']:
    source=BASE/(name+'.json');out=BASE/(name+'-运行记录-checkpoint_delta-v3-kernel.json')
    command=[str(BIN),'run',str(source),'--config',str(CFG),'--ticks',str(names[name]),'--format','checkpoint_delta','--checkpoint-interval','5','--out',str(out)]
    result=subprocess.run(command,capture_output=True,text=True);assert result.returncode==0,(name,result.stdout,result.stderr)
    data=checker.load_json(source);ticks=g.run(data);record=build_record(data,ticks,checker.load_json(g.GOLDEN)if name.startswith('混做')else None)
    validate_record(record,data,ticks)
    (BASE/(name+'-运行记录-v3.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
for name in ['生产循环环带','密集结点核验','密集结点闭环核验','密集结点循环种子核验']:
    out=BASE/(name+'-周期证书-kernel.json')
    result=subprocess.run([str(BIN),'cycle',str(BASE/(name+'.json')),'--config',str(CFG),'--max-ticks',str(names[name]),'--out',str(out)],capture_output=True,text=True)
    assert result.returncode==0,(name,result.stdout,result.stderr)
    reports.append(dict(output=str(out),status=json.loads(out.read_text())['status']));print('cycle',name,flush=True)
# 制造闭环保存实际cycle搜索前缀，避免把抽象运行误标成普通有限运行。
for index in range(6):
    name=f'密集制造闭环序{index}核验';out=BASE/(name+'-周期证书-kernel.json')
    result=subprocess.run([str(BIN),'cycle',str(BASE/(name+'.json')),'--config',str(CFG),'--max-ticks','1000','--out',str(out)],capture_output=True,text=True)
    assert result.returncode==0,(name,result.stdout,result.stderr)
    value=json.loads(out.read_text());record=BASE/(name+'-运行记录-v3-kernel.json')
    record.write_text(json.dumps(value['run_record'],ensure_ascii=False,separators=(',',':'))+'\n')
    reports.append(dict(output=str(out),status=value['status'],run_record=str(record)));print('cycle',name,flush=True)
(E/'regeneration.json').write_text(json.dumps(dict(config_revision=json.loads(CFG.read_text())['revision'],config_sha256=hashlib.sha256(CFG.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),results=reports),ensure_ascii=False,indent=2)+'\n')

for path in BASE.glob('*-v3-kernel.json'):
    path.write_text(json.dumps(json.loads(path.read_text()),ensure_ascii=False,separators=(',',':'))+'\n')
for path in BASE.glob('*-周期证书-kernel.json'):
    path.write_text(json.dumps(json.loads(path.read_text()),ensure_ascii=False,separators=(',',':'))+'\n')
