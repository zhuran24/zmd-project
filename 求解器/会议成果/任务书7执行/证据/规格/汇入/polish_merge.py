from pathlib import Path
import json,re
R=Path('/home/zhuran24/zmd-research-fresh'); S=R/'求解器/规格'
p=S/'运行语义.md';s=p.read_text()
s=s.replace('余货留箱；有货传输后5 tick冷却 | 空箱及全拒收零传输是否启动冷却缺游戏事实；暂停归属、残留格和同刻事件组织待任务6，代码迁移待任务8。','余货留箱；空箱、全拒收及有货送出每次尝试均起5 tick冷却 | 停用恢复的具体回放、同种跨格部分扣减及同刻事件组织继续核，代码迁移待任务8。')
s=s.replace('任务5/6的推导','任务5/6的条件证明与联合推导')
p.write_text(s)
p=S/'内核输入.md';s=p.read_text()
s=s.replace('正式循环对应证明未完成。认证时须引用真实提升关系和证明而非任意布尔值。','缺少反向复原或全称覆盖的具体义务时停止。认证时须引用受限转移§6.5对应关系及逐项证明。')
s=s.replace('`warehouse.periodic_lift`的stop登记正式循环对应尚待证明；生产抽象的旧准入与键见受限转移§6.1—6.4史料，须按现行规则复核后执行，不把有限具体库存段冒称无限循环。','`warehouse.periodic_lift`保留字段名作证明义务入口；stop只在具体反向复原或全称覆盖缺证时触发。生产抽象准入与新键见受限转移§6.1—6.4，完整周期对应见§6.5，依所用支持条件复核后执行。')
p.write_text(s)
p=S/'选择点清单.md';s=p.read_text().replace('## T18. 设计律的逐单位证据范围','## 设计律的逐单位证据范围（T4/T6的条件接口）');p.write_text(s)

# 改写剩余通用停止套话，防止无关轴误报“周期提升”。
p=S/'内核配置-v1.json'; c=json.loads(p.read_text())
for k,v in c['axes'].items():
 v['meaning']=v['meaning'].replace('；无终点返回unresolved，周期提升为待证义务','；按该字段具体未完成后效报告工程停止')
 if '提供提升证明' in v['extension_gate']:
  v['extension_gate']=v['extension_gate'].replace('实现有据后效或提供提升证明','实现该字段的有据后效并补相应证明')
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
p=S/'受限模型声明.md';s=p.read_text()
for k,v in c['axes'].items():
 row=f"| `{k}` | {v['disposition']} | `{json.dumps(v['value'],ensure_ascii=False,separators=(',',':'))}`：{v['meaning']} | 据：{v['basis']} | {v['coverage_loss']} | {v['extension_gate']} |"
 s=re.sub(r'^\| `'+re.escape(k)+r'` \|.*$',lambda m:row,s,flags=re.M)
p.write_text(s)

# JSON Schema 2020-12中items不约束同层prefixItems已覆盖的位置。
# 在proved分支的新子schema中items约束全部检查；原方案的同层语义已核，
# 下列显式allOf额外锁定每个前缀，便于实现者直接看出义务。
p=S/'内核输出.schema.json';sc=json.loads(p.read_text());D=sc['$defs']
for group,ob in D['CycleCorrespondence']['properties'].items():
 conditions=[x['allOf'][1]['properties']['condition']['const'] for x in ob['properties']['checks']['prefixItems']]
 proved=ob['allOf'][0]['then']['properties']['checks']
 proved['prefixItems']=[{'properties':{'condition':{'const':n},'status':{'const':'pass'}}} for n in conditions]
u=D['ProofCertificate']['properties']['all_reachable_cycles']
u['allOf'][0]['then']['properties']['checks']['prefixItems']=[{'properties':{'status':{'const':'pass'}}} for _ in u['properties']['checks']['prefixItems']]
# 循环投影成功需逐事件保持证明；全称及反向仍分列。
cr=D['CycleResult']
cr['allOf'].append({'if':{'properties':{'status':{'enum':['cycle_found','counterexample']}},'required':['status']},'then':{'properties':{'cycle':{'properties':{'correspondence':{'properties':{'forward_projection':{'properties':{'status':{'const':'proved'}}}}}}}}}})
cr['properties']['reading']['properties']['warehouse_acceptance']['enum']=['receivable_products','unresolved']
cr['properties']['reading']['properties']['acceptance_quantifier']['enum']=['all_candidate_and_actual_checks','unresolved']
cr['allOf'].append({'if':{'properties':{'status':{'enum':['cycle_found','counterexample','diagnostic_cycle']}},'required':['status']},'then':{'properties':{'reading':{'properties':{'warehouse_acceptance':{'const':'receivable_products'},'acceptance_quantifier':{'const':'all_candidate_and_actual_checks'}}}}}})
# Candidate key的新增时间编码在形状层显式表示；余下跨字段义务仍由语义核查。
canonical_quantity={'type':'object','properties':{'value':{'type':'string','minLength':1}},'required':['value'],'additionalProperties':False}
D['MaturityResidual']={'type':'object','properties':{'residual':canonical_quantity},'required':['residual'],'additionalProperties':False}
D['GateWindowProjection']={'oneOf':[
 {'type':'object','properties':{'phase':{'const':'idle'}},'required':['phase'],'additionalProperties':False},
 {'type':'object','properties':{'phase':{'const':'active'},'received':{'type':'integer','minimum':1,'maximum':5},'remaining':canonical_quantity},'required':['phase','received','remaining'],'additionalProperties':False}
]}
st=D['CycleKey']['properties']['state']['properties']
st['inventory']['items']={'type':'object','properties':{
 'slot':{'type':'string','minLength':1},'contents':{'type':'array','items':{'type':'object','properties':{
 'item':{'type':'string','minLength':1},'quantity':canonical_quantity,
 'entered_at':{'anyOf':[{'type':'null'},{'$ref':'#/$defs/MaturityResidual'},{'type':'object','properties':{'relative_time':canonical_quantity},'required':['relative_time'],'additionalProperties':False}]}
 },'required':['item','quantity','entered_at'],'additionalProperties':False}}
},'required':['slot','contents'],'additionalProperties':False}
st['logistics']['properties']={'gate_counters':{'type':'array','items':{'type':'object','properties':{'window_started_at':{'$ref':'#/$defs/GateWindowProjection'}},'required':['window_started_at']}}}
p.write_text(json.dumps(sc,ensure_ascii=False,indent=2)+'\n')
p=S/'受限转移定义.md';s=p.read_text()
s=s.replace('无未来读取的非运输entered_at设null，完整原值仍留端点。','无未来读取的非运输entered_at设null；仍有相对时标读取时编码为`{relative_time:{value:"entered_at−t"}}`，完整原值仍留端点。')
p.write_text(s)
print('reader polish: stale cooldown/history removed; schema obligations and new temporal encodings explicit')
