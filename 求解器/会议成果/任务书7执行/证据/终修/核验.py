#!/usr/bin/env python3
"""终修定向复核。只向本目录写证据，不重写原席脚本/日志/证书。"""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from collections import deque
import ast
import contextlib
import io
import json
import re
import subprocess

B=Path('/home/zhuran24/zmd-research-fresh/求解器')
D=B/'会议成果/任务书7执行'
E=Path(__file__).resolve().parent
checks=[]
commands=[]
def digest(p): return sha256(p.read_bytes()).hexdigest()
def write(name,value): (E/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def check(name,value,detail=None):
    checks.append({'name':name,'pass':bool(value),'detail':detail})
    assert value,(name,detail)
def command(name,args,expected=0):
    r=subprocess.run(args,cwd=B,text=True,capture_output=True)
    commands.append({'name':name,'argv':args,'cwd':str(B),'exit_code':r.returncode,'expected_exit_code':expected,'stdout':r.stdout,'stderr':r.stderr})
    (E/(name+'.log')).write_text(r.stdout+r.stderr)
    check('command:'+name,r.returncode==expected,{'exit_code':r.returncode})
    return r

def transport_probe(births,order):
    """定向局部查错：精确实数事件子集；证明由成品跨桥推导承担。"""
    layout=json.loads((D/'密排布局.json').read_text())
    routes={r['source_unit']:r['cells'] for r in layout['routes'] if r['source_unit'] in order and r['id'].endswith('成品')}
    bridges={tuple(u['xy']) for u in layout['units'] if u['kind']=='桥接器'}
    positions={r:[None]*len(c) for r,c in routes.items()}
    source={r:deque() for r in routes}
    events=sorted((F(t),r,i) for r,ts in births.items() for i,t in enumerate(ts))
    pending=deque(events);t=events[0][0];deliveries=[];maxq=0;maxflight=0
    while pending or any(source.values()) or any(any(a for a in cells) for cells in positions.values()):
        while pending and pending[0][0]==t:
            b,r,i=pending.popleft();source[r].append((r,i,b));maxq=max(maxq,len(source[r]))
        changed=True
        while changed:
            changed=False
            for r in order:
                cells=routes[r]
                for edge in range(len(cells)+1):
                    token=source[r][0] if edge==0 and source[r] else (positions[r][edge-1][0] if edge>0 and positions[r][edge-1] and positions[r][edge-1][1]+1<=t else None)
                    if token is None: continue
                    if edge<len(cells):
                        if positions[r][edge]:continue
                        c=tuple(cells[edge])
                        if c in bridges and any(positions[rr][ii] is not None for rr,cc in routes.items() for ii,cell in enumerate(cc) if tuple(cell)==c):continue
                    if edge==0:source[r].popleft()
                    else:positions[r][edge-1]=None
                    if edge<len(cells):positions[r][edge]=(token,t)
                    else:deliveries.append({'source':r,'token':token[1],'born':str(token[2]),'box':str(t),'delay':str(t-token[2])})
                    changed=True
            maxflight=max(maxflight,sum(v is not None for cells in positions.values() for v in cells))
        future=[pending[0][0]] if pending else []
        future.extend(v[1]+1 for cells in positions.values() for v in cells if v and v[1]+1>t)
        if not future:
            assert not any(source.values()) and not any(any(v for v in cells) for cells in positions.values())
            break
        t=min(future)
    bounds={'M213':16,'M214':8,'M215':18}
    assert all(F(x['delay'])<=bounds[x['source']] for x in deliveries)
    assert len(deliveries)==sum(map(len,births.values()))
    assert maxq<=2 and maxflight<=10
    return {'births':{r:list(map(str,v)) for r,v in births.items()},'fixed_order':order,'deliveries':deliveries,'max_output_queue':maxq,'max_in_flight':maxflight}

def main():
    original=json.loads((E/'输入指纹.json').read_text())['files']
    rows=[]
    for p in sorted(E.glob('修改清单-*.json')):rows.extend(json.loads(p.read_text()))
    allowed={r['path'] for r in rows}
    check('modified_paths_unique',len(allowed)==len(rows))
    changes=[]
    for row in original:
        p=Path(row['path']);actual=digest(p)
        if actual!=row['sha256']:
            check('write_scope:'+str(p),str(p) in allowed)
            changes.append({'path':str(p),'before':row['sha256'],'after':actual})
    check('all_declared_changes_present',{r['path'] for r in changes}==allowed)
    check('no_evidence_artifact_other_formats',all(p.suffix in ('.py','.json','.md','.log') for p in E.rglob('*') if p.is_file()))
    expected={
        '《明日方舟：终末地》游戏规则.txt':'d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a',
        '求解任务.txt':'1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac',
        '求解约束.txt':'f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6'}
    for name,h in expected.items():check('formal:'+name,digest(B.parent/name)==h)
    R=(B.parent/'《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
    check('R36_current_quote','即使那个物品格中没有物品也一样，能送多少送多少，5 tick 冷却' in R[35])
    check('R13_bridge_scope','（协议储存箱和缓存格除外）' in R[12] and '每对独立拥有一个物品格' in R[62])
    for path in allowed:
        p=Path(path)
        if p.suffix=='.md':check('end_record:'+p.name,'## 终修记录（任务书7终修席，2026-09-21）' in p.read_text())
    for n in ['回路总数决定论-v2.md','总纲-流量存量相位.md']:
        text=(B/'规格/推导'/n).read_text();first=text.split('## §6 终修记录')[0] if n.startswith('回路') else text.split('## 7. 任务3')[0]
        check('current_source:'+n,expected['《明日方舟：终末地》游戏规则.txt'] in first and '31ced2a24fef' not in first)
    phase=(B/'规格/推导/三种相位不改产量-v2.md').read_text()
    check('phase_current_source','d150b86b398f' in next(l for l in phase.splitlines() if l.startswith('| 规则 |')))
    for p in [D/'仓库接收与循环对应.md',D/'受限转移定义-§6.5替换稿.md']:
        text=p.read_text().split('## 终修记录')[0]
        check('no_obsolete_cooling:'+p.name,'空箱无实际发送的尝试是否启动冷却' not in text and '仍缺空箱' not in text and '31ced2a24fef' not in text)
    transition=(B/'规格/受限转移定义.md').read_text()
    check('exact_manufacturing_key','trigger={kind:"remaining_work",value:Time(remaining)}' in transition and 'deadline≤t+remaining' in transition)
    check('exact_same_species_merge','同种审计分组数量相加成一行' in transition)
    check('proof_vs_attempt_separated','否证不成立”仅指该攻击' in (D/'推导复核范围.md').read_text())
    layout=json.loads((D/'密排布局.json').read_text())
    products=[r for r in layout['routes'] if r['id'].endswith('成品')]
    check('product_contracts',len(products)==6 and all(r['service_capacity_given_receiving_boundary'] is None and r['service_contract']['preloaded_recovery_bound_ticks'] is None for r in products))
    check('no_promoted_layout',layout['L']==0 and layout['U']==1113 and not layout['full_layout_certified'] and not layout['default_start_certified'] and all(r['actual_rate'] is None for r in layout['routes']))
    check('new_waiting_bounds',[r['service_contract']['completion_to_warehouse_bound_ticks'] for r in products]==[21,13,23,21,13,23])
    # 全量解码大接口、配置与schema，核每个JSON语法；不据解析通过声明运行认证。
    for p in [D/'送料与接口.json',D/'调试后状态.json',B/'规格/内核配置-v1.json',B/'规格/内核输出.schema.json']:
        obj=json.loads(p.read_text());check('json:'+p.name,isinstance(obj,dict))
    for p in E.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    # 原审查算法只重定向输出，原文件保持；不同于更新原证据哈希。
    for name in ['check_geometry.py','bridge_delay_witness.py']:
        src=D/'证据/复核接口'/name;out=io.StringIO()
        with contextlib.redirect_stdout(out):exec(compile(src.read_text(),str(src),'exec'),{'__file__':str(E/name),'__name__':'__main__'})
        commands.append({'name':name,'source':str(src),'source_sha256':digest(src),'invocation':'exec original source; only __file__ output root changed','exit_code':0,'stdout':out.getvalue(),'stderr':''})
        (E/(name+'.log')).write_text(out.getvalue())
    cases=[
        ({'M213':[F(0)+5*i for i in range(12)],'M214':[F(0)+5*i for i in range(12)],'M215':[F(0)+5*i for i in range(12)]},['M213','M214','M215']),
        ({'M213':[F(14,5)+5*i for i in range(12)],'M214':[F(19,10)+5*i for i in range(12)],'M215':[F(5)+5*i for i in range(12)]},['M213','M214','M215']),
        ({'M213':[F(1,7)+5*i+i//3 for i in range(12)],'M214':[F(4,3)+5*i+2*(i//4) for i in range(12)],'M215':[F(17,9)+5*i+3*(i//2) for i in range(12)]},['M215','M214','M213'])]
    probe=[transport_probe(*case) for case in cases];write('跨桥定向查错.json',{'scope':'三组有限精确分数时序，只核局部事件与数值；普遍界由正文引理证明，未扫描全参数','cases':probe})
    check('bridge_targeted_cases',len(probe)==3)
    battery,capsule=F(3,5),F(11,20)
    check('ore_ceiling',50*battery+40*capsule==52)
    steel=10*battery+20*capsule
    check('capacity_arithmetic',30*battery+2*steel+10*capsule+(steel+15*battery+10*capsule)/3==68 and 2*steel+steel==51)
    bad=[(a,b,h) for a in range(51) for b in range(51) for h in ('A','B') if not (a>=2 and b>=1) and ((h=='A' and a==50) or (h=='B' and b==50))]
    check('Z_three_boundaries',bad==[(0,50,'B'),(1,50,'B'),(50,0,'A')])
    check('Z_safe_integer_prefix',[i for i in range(-150,151) if -99<-50+i<50]==list(range(-48,100)))
    # 文档变动后重新生成绑定现行语义的三项关联证据，不刷新旧证书。
    (E/'runs').mkdir(exist_ok=True)
    binary=str(B/'target/release/kernel');cfg=str(B/'规格/内核配置-v1.json')
    check('same_kernel_binary',digest(Path(binary))=='eaa6d2653c951b58d3517c0805a84f6af288ca2b40d5524dd9e35d30fff9182a')
    cases=[('暂停键',B/'数据/样例/任务7内核/静止成熟与暂停键.json'),('分组合并',D/'证据/内核/negative/同种年龄分组-input.json'),('累计调低',B/'数据/样例/任务7内核/累计调低保留.json')]
    for label,p in cases:
        out=E/'runs'/f'{label}-cycle.json'
        command(label+'-cycle',[binary,'cycle',str(p),'--config',cfg,'--max-ticks','5','--no-record','--out',str(out)])
        command(label+'-verify',[binary,'verify-cycle',str(out),'--config',cfg])
        obj=json.loads(out.read_text());c=obj['cycle']
        check('diagnostic:'+label,obj['schema']=='kernel-cycle-v3' and obj['status']=='diagnostic_cycle' and c['start_key']==c['end_key'])
        check('period_rates:'+label,F(c['period']['value'])>0 and all(F(r['average']['value'])==F(r['inbound']['value'])/F(c['period']['value']) for r in c['rates']))
        for f in obj['fingerprints']:check('fingerprint:'+label+':'+f['path'],digest((out.parent/f['path']).resolve())==f['sha256'])
        for side in ['start','end']:
            state=c[side+'_state'];key=c[side+'_key']['state']
            for event in key['semantic_context']['pending_events']['value']:
                if event['operation']=='manufacture_complete':
                    progress=next(p for p in state['progress'] if p['unit']==event['target']);value=progress['remaining']['value']['value']
                    check('remaining_work:'+label+side,event['trigger']['kind']=='remaining_work' and event['event']==['manufacture_complete',event['target'],value] and event['trigger']['value']['value']['value']==value)
            for row in key['inventory']:
                groups=row['contents']
                if all(x['entered_at'] is None for x in groups):check('merged:'+label+side+row['slot'],len({x['item'] for x in groups})==len(groups))
        check('forward_unresolved:'+label,c['correspondence']['forward_projection']['status']=='unresolved')
    command('schema-replay-batch',[binary,'verify-batch',str(E/'runs'),'--config',cfg])
    old=D/'证据/内核/runs/静止成熟与暂停键-cycle.json'
    cp=command('old-certificate-rejected',[binary,'verify-cycle',str(old),'--config',cfg],expected=2)
    check('old_rejection_is_fingerprint','指纹' in cp.stdout+cp.stderr or 'fingerprint' in cp.stdout+cp.stderr)
    # 局部链接；只检查修订交付中的存在性，历史审查指纹不当现行通过票。
    missing=[]
    for path in allowed:
        p=Path(path)
        if p.suffix!='.md':continue
        for target in re.findall(r'\]\(([^\n)]+)\)',p.read_text()):
            if target.startswith(('http:','https:','#')):continue
            target=target.split('#')[0]
            q=Path(target) if target.startswith('/') else p.parent/target
            if target and not q.exists():missing.append({'path':str(p),'target':target})
    check('local_links',not missing,missing)
    write('commands.json',commands)
    write('核验结果.json',{'status':'pass','checks':checks,'check_count':len(checks),'changed_files':changes,'unchanged_count':len(original)-len(changes),'scope':'正文/版本/受保护文件、静态几何、局部精确分数见证及三个当前诊断周期；无全厂认证'})
    print(json.dumps({'status':'pass','checks':len(checks),'changed':len(changes),'originals_unchanged':len(original)-len(changes),'cycles':3,'L':0,'U':1113},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as ex:
        write('commands.json',commands);write('核验结果.json',{'status':'fail','error':repr(ex),'checks':checks});raise
