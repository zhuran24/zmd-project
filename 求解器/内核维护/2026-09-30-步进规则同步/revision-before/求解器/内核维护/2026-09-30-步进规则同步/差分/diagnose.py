"""差分分歧归因：保存最小输入与原始首差，单点修正只在 Python 进程内回放。

不修改 simulator.py、适配器、内核或规格。每次运行前后核历史目录全量哈希。
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import time
import run
from simulator import Machine, World, BridgeAxis


def patched_reference(raw, steps, fix):
    flush, transfer = Machine.flush, World.transfer
    def unique_flush(self, world):
        if self.cache and any(s and s[0].kind==self.cache[0].kind for s in self.slots):
            return
        return flush(self, world)
    def physical_return(self, channel):
        item=channel.src.ready_item(self)
        if item is not None and not (isinstance(channel.src,BridgeAxis) and isinstance(channel.dst,BridgeAxis)):
            item.previous=''
        return transfer(self,channel)
    if fix=='ordinary_slot_unique':Machine.flush=unique_flush
    if fix=='return_uses_physical_unit':World.transfer=physical_return
    try:return run.reference(raw,steps)
    finally:Machine.flush=flush;World.transfer=transfer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scratch',type=Path,required=True)
    p.add_argument('--suite',type=Path,required=True)
    p.add_argument('--label',required=True)
    args=p.parse_args()
    report_path=run.HERE/(args.label+'.json')
    assert not report_path.exists()
    before=run.guard.guard(args.label+'-before')
    sources=run.source_manifest()
    started=time.monotonic()
    reports=[]
    specifications=[
        ('edge/completed_blocked_same_item','ordinary_slot_unique',48,'sim2-普通格同种唯一性.json',
         ['游戏规则L13','游戏规则L18','游戏规则L36'],
         '制造单位存货格已有源石粉末，缓存中已完成一批源石粉末，取货格为空；第0步内核留在completed且不出缓存，sim2却入取货格变idle并送出。',
         '内核正确，sim2 Machine.flush 漏核普通物品格的同种单格条件。',
         '粉碎在制时玩家可向存货格放入源石粉末；完成后缓存例外允许与存货格同种，但产物不能进入取货格。',
         '规则L13的一种物品只能占单位内一个普通物品格；缓存格是例外，不是允许产物进入第二个普通格。'),
        ('mechanism/累计审计与窗口周期','return_uses_physical_unit',80,'sim2-单位与元件混淆.json',
         ['游戏规则L24','游戏规则L29','游戏规则L65'],
         '传送带链 b→c→down→d→a 首尾由物品准入口相接：a→准入口在第0步成功，准入口→b在第8步内核成功而sim2拒绝，后者把两次接入同一带段C|a当作回到刚离开的单位。',
         '内核正确，sim2 World.transfer/World.move 把元件名当成物理单位名判断回头。',
         '数据/样例/步进/机制/累计审计与窗口周期.json 的合法布局：五格连续传送带与一个准入口构成环，初始a格成熟物品，准入口每40步只收1件；不是纯带环，也不含两出口桥轴。',
         '规则L24禁止准入口→a这种回到刚离开的单位，不禁止准入口→b；L29只把连续传送带合成一个判定元件，不能把各带单位合成一个物理单位。'),
    ]
    try:
        exe,command=run.compile_runner(args.scratch)
        available={name:(raw,steps) for name,raw,steps,group in run.edge_cases()}
        for name,fix,steps,filename,rules,scenario,verdict,realizable,basis in specifications:
            raw,_=available[name]
            job=dict(name=name,input=raw,steps=steps,base=str(run.SAMPLES),config=str(run.ROOT/'规格/内核配置-v2.json'))
            completed=subprocess.run([str(exe)],input=json.dumps(job,ensure_ascii=False)+'\n',text=True,capture_output=True,check=True)
            actual=json.loads(completed.stdout)
            assert 'error' not in actual,actual
            original=run.reference(raw,steps)
            corrected=patched_reference(raw,steps,fix)
            diff=run.first_difference(actual['rows'],original['rows'],'rows')
            assert diff is not None,name
            after_diff=run.first_difference(actual['rows'],corrected['rows'],'rows')
            polls=run.first_difference(actual['polls'],corrected['polls'],'polls')
            gates=run.first_difference(run.numeric_gate_rows(actual['gates']),run.numeric_gate_rows(corrected['gates']),'gates')
            assert after_diff is None and polls is None and gates is None,(name,after_diff,polls,gates)
            index=int(diff['path'].split('[',1)[1].split(']',1)[0])
            witness=dict(schema='kernel-sim2-counterexample-v1',name=name,base=str(run.SAMPLES),config=job['config'],input=raw,steps=steps,first_difference=diff,kernel_at_difference=actual['rows'][index],sim2_at_difference=original['rows'][index],rules=rules,diagnostic_fix=fix,patched_sim2_projection_equal=True,patched_sim2_poll_equal=True,patched_sim2_gate_equal=True)
            path=run.HERE/filename
            path.write_text(json.dumps(witness,ensure_ascii=False,indent=2)+'\n')
            reports.append(dict(name=name,summary=scenario,classification='内核对、sim2错',conclusion=verdict,rules=rules,basis=basis,realizability=realizable,first_difference=diff,witness=str(path),witness_sha256=run.sha(path),diagnostic_fix=dict(name=fix,steps=steps,all_projection_poll_and_gate_equal=True,scope='仅在进程内替换一项方法作归因，不改源码')))
    finally:
        after=run.guard.guard(args.label+'-after')
        history_delta=run.guard.difference(before['files'],after['files'])
        changes=run.guard.difference(sources,run.source_manifest())
        suite=json.loads(args.suite.read_text())
        required=[c for c in suite['cases'] if c['group']=='required']
        groups={}
        for c in required:groups.setdefault(c['name'].split('/')[0],[]).append(c)
        coverage=[]
        for name,cases in sorted(groups.items()):
            orders={tuple(c['graph']['order']) for c in cases}
            choices={c['name'].split('/',2)[-1] for c in cases}
            coverage.append(dict(name=name,cases=len(cases),steps=sum(c['steps'] for c in cases),distinct_judgment_orders=len(orders),distinct_layer_choices=sorted(choices),projection_poll_gate_layers_equal=all(all(c[k] is None for k in ['projection_diff','poll_diff','gate_diff','layer_diff']) for c in cases)))
        payload=dict(schema='kernel-sim2-differential-conclusion-v1',date='2026-09-30',status='completed',summary='九个必核构型的合法接通史和分流器选支变值逐步一致；补充边界发现两处sim2误判，内核均符合正式规则，无须修内核。',suite=str(args.suite),suite_sha256=run.sha(args.suite),required_cases=len(required),required_steps=sum(c['steps'] for c in required),compared_cases=len(suite['cases']),compared_steps=sum(c['steps'] for c in suite['cases']),coverage=coverage,findings=reports,history=dict(counts=before['counts'],files=sum(before['counts'].values()),before_sha256=run.sha(run.MAINT/(args.label+'-before-history.json')),after_sha256=run.sha(run.MAINT/(args.label+'-after-history.json')),difference=history_delta),source_changes=changes,sources=sources,seconds=round(time.monotonic()-started,3),limitations=['结论是列明输入和有限步数的差分，不是对全部布局、接通史和运行时长的证明。','共同域不含纯传送带环、两出口桥接器轴、协议核心送货、部分接收的跨格残留；单点修正回放仅用于确认首差原因。'],safe_reference_log=str(run.MAINT/'differential-reference.log'))
        report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(report=str(report_path),required_cases=len(required),required_steps=sum(c['steps'] for c in required),cases=len(suite['cases']),steps=sum(c['steps'] for c in suite['cases']),findings=len(reports),history_difference=history_delta,source_changes=changes),ensure_ascii=False))
    if any(history_delta.values()) or any(changes.values()):raise RuntimeError('归因运行期间来源或历史变化')

if __name__=='__main__':main()
