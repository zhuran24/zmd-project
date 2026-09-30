#!/usr/bin/env python3
"""步进差分、机制、周期与 fixtures 的确定性生成；只输出输入，不运行内核。"""
from pathlib import Path
import argparse,json,hashlib
from step_inputs import ROOT,generate,q,t,axis,ref
from step_graph import build,defaults,poll_state
from migrate_input_v4 import migrate
SOURCES=['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']
MECHANISMS=['无线空箱','无线全拒收','无线部分接收','无线多格全收','无线多格歧义','无线一满一可收','同刻双箱争余量','累计审计与窗口周期','累计调低保留','累计调高资格','身份实际切换','装载与普通制造','静止成熟与暂停键','成熟旧货重试']
NOTES={
 '无线空箱':'无货也重启 40 步冷却', '无线全拒收':'仓库满而传输全拒，箱货不动并冷却',
 '无线部分接收':'单格按仓库余量部分传输', '无线多格全收':'同种多格全部传走',
 '无线多格歧义':'同种多格且严格部分接收：必须 unsupported 停止', '无线一满一可收':'一种拒收不妨碍另一种传输',
 '同刻双箱争余量':'给定非运输次序下先判定箱先占余量', '累计审计与窗口周期':'无累计阈值的计数不入键，40 步窗口剩余入键',
 '累计调低保留':'累计超过调低上限仍保留且不再收货', '累计调高资格':'上限调高后的条件种子允许收货',
 '身份实际切换':'准入口按当前来件身份判定，不断边', '装载与普通制造':'普通制造、整批缓存、双出料通道',
 '静止成熟与暂停键':'成熟停留归零；停机保留剩余工作量', '成熟旧货重试':'成熟货随新步重试'}
def u(name,kind,x,y,r=0,layout=0):return dict(id=name,kind=kind,x=x,y=y,rotation=r,port_layout=layout)
def state(r):return r['initial_state']['nonwarehouse']['value']
def put(r,slot,item,n=1,entered=None):
    inv=next(i for i in state(r)['inventory'] if i['slot']==slot)
    inv['contents']=[dict(item=item,quantity=q(n),entered_at=t(entered) if entered is not None else None)]
def fill(r,unit,item='源石粉末'):
    for i in range(6):put(r,f'{unit}:storage:{i}',item,50)
def make(name,specs,assertions,steps=400):
    dest=ROOT/'数据/样例/步进/差分'/f'{name}.json'
    # The given sequence is the explicit construction order within each permitted group.
    order=[x['id'] for x in specs if x['kind']!='传送带']+[x['id'] for x in specs if x['kind']=='传送带']
    if not any(x['kind']=='协议核心' for x in specs):specs=[u('core','协议核心',50,50),*specs];order.insert(0,'core')
    r=generate(dict(units=specs,build_order=order),dest.parent)
    r['scenario']={'name':name,'differential':{'steps':steps,'note':'固定显式接通史、选支与非运输次序；sim2 eager 投影逐步比较'},'assertions':assertions}
    return r

def differential():
    results={}
    r=make('a-纯链',[u('source','仓库取货口',10,0),*[u(f'b{i}','传送带',11,i+1) for i in range(3)],u('crusher','粉碎机',10,4),u('power','供电桩',14,4),u('out','传送带',11,7),u('core','协议核心',10,8)],['启动后每 8 步开工一次'])
    results['a-纯链']=r
    for name,n,following in [('b-迟滞',2,1),('断尾',1,2)]:
        specs=[u('source','仓库取货口',10,0),u('in','传送带',11,1),u('x','分流器',11,2),u('d1','物品准入口',12,2,270),u('d2','物品准入口',13,2,270)]
        specs += [u(f's{i}','传送带',11,3+i) for i in range(n)]
        specs += [u(f'g{i}','物品准入口',11,3+n+i) for i in range(following)]
        specs += [u('core','协议核心',10,3+n+following)]
        r=make(name,specs,[f'活支 n={n}，观察到间隔每 {n} 次合计 {8*n+1} 步；X 按断支数层'])
        order=defaults(build(r,ROOT/'数据/样例/步进/差分'));order['layer_choices']=[dict(component='C|x',downstream='C|d1')];axis(r,'step.order',order)
        for slot in state(r)['inventory']:
            if ':transport:' in slot['slot']:put(r,slot['slot'],'源矿',1,-8)
        for wh in [r['initial_state']['warehouse'],state(r)['warehouse']]:
            next(w for w in wh['slots'] if w['item']=='源矿')['quantity']=q(60000)
        results[name]=r
    specs=[u('m','研磨机',10,30),u('power','供电桩',16,30),u('out','传送带',11,34),u('core','协议核心',10,35)]
    specs += [u(f'{p}{i}','传送带',x,14+i) for p,x in [('a',10),('b',12),('sand',15)] for i in range(16)]
    r=make('c-换主料',specs,['研磨机蓝铁粉末/源石粉末交替；同主料两次开工相隔 18 步（对照 a 的 8 步）'],800)
    for p,item in [('a','源石粉末'),('b','蓝铁粉末'),('sand','砂叶粉末')]:
        for i in range(16):put(r,f'{p}{i}:transport:0',item,1,-7)
    put(r,'m:input:1','砂叶粉末',50)
    results['c-换主料']=r
    specs=[u('core','协议核心',10,14)]+[u(f'box{i}','协议储存箱',10,4*i+2) for i in range(3)]+[u(f'b{i}','传送带',11,4*i+1) for i in range(4)]
    r=make('d-满箱串联',specs,['b0 首次送出在第 3 步，三个满箱各晚一步'])
    for i in range(3):fill(r,f'box{i}')
    for i in range(4):put(r,f'b{i}:transport:0','源石粉末',1,-8)
    results['d-满箱串联']=r
    specs=[u('fast','协议储存箱',6,12,270),u('sparse','协议储存箱',10,9),u('a','传送带',9,13,270),u('b','传送带',10,13,270),u('gate','物品准入口',11,12),u('m','汇流器',11,13),u('out','传送带',11,14),u('core','协议核心',10,15)]
    r=make('e-汇流',specs,['稳态汇流器每 8 步送出；稀疏支每 40 步限 1 件'])
    fill(r,'fast');fill(r,'sparse');r['settings']['gates'][0].update(item='源石粉末',window_limit=q(1))
    for p in ('a','b','m','out'):put(r,p+':transport:0','源石粉末',1,-8)
    results['e-汇流']=r
    # Vertical splitter trunk and two eastward branches, one furnace on each.
    specs=[u('source','仓库取货口',9,0),u('input','传送带',10,1),u('x1','分流器',10,2),u('x2','分流器',10,8),u('f1','精炼炉',13,1,270),u('f2','精炼炉',13,7,270),u('power1','供电桩',16,3),u('power2','供电桩',16,9),u('core','协议核心',20,2,90)]
    specs += [u(f't{i}','传送带',10,3+i) for i in range(5)]
    for j,y in [(1,2),(2,8)]:
        specs += [u(f'a{j}_{i}','传送带',11+i,y,270) for i in range(2)]
        specs += [u(f'o{j}_{i}','传送带',16+i,y,270) for i in range(4)]
    r=make('分矿',specs,['两台精炼炉各每 16 步开工，合计每 8 步一批'])
    results['分矿']=r
    specs=[u('feed','协议储存箱',6,12,270),u('side','协议储存箱',10,10),u('m','汇流器',11,13),u('a','传送带',9,13,270),u('b','传送带',10,13,270),u('out','传送带',11,14),u('core','协议核心',10,15)]
    r=make('侧面优先',specs,['满过路带每 8 步收到一件，侧箱送货 0'])
    for n in ('feed','side'):fill(r,n)
    for n in ('a','b','m','out'):put(r,n+':transport:0','源石粉末',1,-8)
    results['侧面优先']=r
    specs=[u('feed_l','协议储存箱',15,19,270),u('feed_r','协议储存箱',23,19,90),u('feed_b','协议储存箱',19,15),u('left','分流器',19,20,270),u('right','分流器',21,20,90),u('m','汇流器',20,20),u('l','传送带',18,20,270),u('r','传送带',22,20,90),u('b0','传送带',20,18),u('b1','传送带',20,19),u('out','传送带',20,21),u('core','协议核心',19,22)]
    r=make('三上游',specs,['汇流器三上游仅一家成功收货，总每 8 步一件'])
    for n in ('feed_l','feed_r','feed_b'):fill(r,n)
    for n in ('left','right','m','l','r','b0','b1','out'):put(r,n+':transport:0','源石粉末',1,-8)
    results['三上游']=r
    return results

def generate_all():
    outputs={};diff=ROOT/'数据/样例/步进/差分'
    for name,raw in differential().items():outputs[diff/f'{name}.json']=raw
    for name in MECHANISMS+['生产环带','生产循环环带']:
        src=ROOT/'数据/样例'/('生产循环环带.json' if name=='生产循环环带' else f'任务7内核/{name}.json')
        dest=ROOT/'数据/样例/步进'/('机制' if name in MECHANISMS else '周期')/f'{name}.json'
        raw=migrate(json.loads(src.read_text()),src.parent,dest.parent)
        raw['scenario']['migration'].update(source=str(src.relative_to(ROOT)),sha256=hashlib.sha256(src.read_bytes()).hexdigest())
        raw['scenario']['steps']=80 if name!='生产循环环带' else 800
        raw['scenario']['assertions']=[NOTES.get(name,'生产代表键重复；仅提交诊断周期')]
        if name=='无线多格歧义':raw['scenario']['expected_stop']={'status':'unsupported','axis':'transfer.partial_residual','step':0}
        outputs[dest]=raw
    for name in ('bridge','core_inbound','priority','benchmark_1000'):
        src=ROOT/f'crates/kernel/tests/fixtures/{name}.json';dest=src.parent/'step'/src.name
        raw=migrate(json.loads(src.read_text()),src.parent,dest.parent);raw['scenario']['steps']=64
        raw['scenario']['migration'].update(source=str(src.relative_to(ROOT)),sha256=hashlib.sha256(src.read_bytes()).hexdigest());outputs[dest]=raw
    return outputs
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case');a=p.parse_args();out=generate_all()
    if a.case:
        rows=[raw for path,raw in out.items() if path.stem==a.case]
        if len(rows)!=1:raise ValueError('case 必须唯一')
        print(json.dumps(rows[0],ensure_ascii=False,indent=2))
    else:print(json.dumps({str(k.relative_to(ROOT)):v for k,v in out.items()},ensure_ascii=False,indent=2))
