#!/usr/bin/env python3
"""内核输入§6、输出§1–§3：工程复核的独立文件探针；写入仅限同目录。"""
import copy,hashlib,json,pathlib,platform,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[4]
OUT=pathlib.Path(__file__).resolve().parent
BIN=OUT/'target/release/kernel'
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
import verify_outputs as verifier

def write(path,data):
    """内核输出§1：保存带输入和返回码的可重复证据。"""
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def invoke(name,data,ticks=2,no_output=False):
    """第四轮§4.6：经真实CLI观察装载、运行与输出验收。"""
    data=copy.deepcopy(data)
    origin=ROOT/'数据/样例/混做粉碎机两下游.json'
    for section in [data['catalog'],data['parameters']['axis_registry']]:
        section['path']=str((origin.parent/section['path']).resolve())
    path=OUT/(name+'-input.json'); output=OUT/(name+'-record.json'); write(path,data)
    command=[str(BIN),'run',str(path),'--config',str(ROOT/'规格/内核配置-v1.json'),'--ticks',str(ticks)]
    command+=['--no-output'] if no_output else ['--out',str(output)]
    process=subprocess.run(command,capture_output=True,text=True,timeout=30)
    record=json.loads(process.stdout) if no_output else (json.loads(output.read_text()) if output.exists() else None)
    schema='不适用'
    if record and not no_output:
        try:
            s=verifier.checker.load_json(ROOT/'规格/内核输出.schema.json')
            verifier.validate_schema(record,s,s); schema='通过'
        except Exception as error: schema=str(error)
    return {'name':name,'command':command,'exit_code':process.returncode,'stdout':process.stdout,'stderr':process.stderr,'status':record.get('status') if record else None,'schema':schema,'record':str(output) if not no_output else record}

def main():
    """内核输入§6：合法对照与互不叠加的单字段负例。"""
    base=verifier.checker.load_json(ROOT/'数据/样例/混做粉碎机两下游.json')
    results=[invoke('control',base)]
    for name,value in [('reachability-null',None),('reachability-number',7),('reachability-object',{}),('reachability-string','合法')]:
        data=copy.deepcopy(base); data['initial_state']['reachability']=value; results.append(invoke(name,data))
    data=copy.deepcopy(base); del data['initial_state']['warehouse']['unlisted']; results.append(invoke('initial-unlisted-missing',data))
    data=copy.deepcopy(base); data['initial_state']['warehouse']['unlisted']='filled'; results.append(invoke('initial-unlisted-filled',data))
    # 已闭包种子只走引擎合法续跑入口，避开KQ-02的记录入口停止。
    control=json.loads((OUT/'control-record.json').read_text())
    restart=copy.deepcopy(base); restart['initial_state']['nonwarehouse']['value']=control['trace']['ticks'][-1]['state']
    results.append(invoke('restart-control',restart,no_output=True))
    for name,field,value in [('movement-build-alias','event','build_0'),('movement-missing-identity','event','not_registered'),('movement-item-number','item',7),('movement-item-forged','item','精选荞愈胶囊')]:
        data=copy.deepcopy(restart); data['initial_state']['nonwarehouse']['value']['semantic_context']['tick_context']['value']['movements'][0][field]=value
        results.append(invoke(name,data,no_output=True))
    write(OUT/'input-probes.json',results)
    command=[str(BIN),'run',str(ROOT/'crates/kernel/tests/fixtures/benchmark_1000.json'),'--config',str(ROOT/'规格/内核配置-v1.json'),'--ticks','1000','--no-output']
    start=time.perf_counter_ns(); process=subprocess.run(command,capture_output=True,text=True,timeout=30); elapsed=time.perf_counter_ns()-start
    write(OUT/'benchmark.json',{'command':command,'platform':platform.platform(),'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),'process_ns':elapsed,'exit_code':process.returncode,'stdout':json.loads(process.stdout),'stderr':process.stderr,'binary_sha256':hashlib.sha256(BIN.read_bytes()).hexdigest(),'input_sha256':hashlib.sha256((ROOT/'crates/kernel/tests/fixtures/benchmark_1000.json').read_bytes()).hexdigest()})
    print(json.dumps([{k:v for k,v in row.items() if k in ['name','exit_code','status','schema','stderr']} for row in results],ensure_ascii=False,indent=2))
    print((OUT/'benchmark.json').read_text())
if __name__=='__main__': main()
