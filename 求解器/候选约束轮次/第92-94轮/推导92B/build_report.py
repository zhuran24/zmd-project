"""汇总本席已经复证的记录；校验范围、候选名、冻结快照与独立算术结果。"""
from pathlib import Path
import json,re,hashlib

HERE=Path(__file__).resolve().parent
ROUND=HERE.parent
REPORT=ROUND/'推导92B.md'
INV=json.loads((HERE/'inventory.json').read_text())
byid={r['id']:r for r in INV}

def read_json(name):return json.loads((HERE/name).read_text())
def normalize(value):
    if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
    if isinstance(value,list):return [normalize(v) for v in value]
    return str(value)

def sections(text):
    matches=list(re.finditer(r'^### (N\d\d) [^\n]+\n',text,re.M))
    return {m.group(1):text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip() for i,m in enumerate(matches)}

records={}
foundation=sections((HERE/'foundation_audit.md').read_text())
for key,section in foundation.items():
    section=section.split('\n## 数字交叉核对')[0]
    reason=re.search(r'^一句理由：(.+)$',section,re.M).group(1)
    proof=re.sub(r'^一句理由：.+\n\n','',section,count=1)
    records[key]={**byid[key],'status':'确认成立','reason':reason,'proof':proof,'appendix':'foundation_audit.md'}
for r in read_json('counts_records.json'):
    records[r['id']]={**byid[r['id']],**r,'status':r['classification'],'appendix':'counts_audit.md'}
geo_sections=sections((HERE/'geo_audit.md').read_text())
for r in read_json('geo_summary.json'):
    key=r.get('id',r.get('ID')); section=geo_sections[key].split('\n## 3.')[0]
    section=re.sub(r'^\*\*一句理由：\*\*.+\n\n','',section,count=1)
    if key=='N61':section=section.split('\n核心邻格：')[0]
    records[key]={**byid[key],**r,'proof':section,'appendix':'geo_audit.md'}
area=(HERE/'area_audit.md').read_text()
area_proof=area.split('## 3. 方向账的现行证明\n',1)[1].split('## 6. 待审保守修订',1)[0]
area_rows={}
for line in area.splitlines():
    if line.startswith('| N'):
        cols=[s.strip() for s in line.strip('|').split('|')]
        key,name=cols[0].split(' ',1)
        area_rows[key]={'name':name,'status':cols[1],'reason':cols[2],'source':cols[3]}
for key,r in area_rows.items():
    proof='完整证明见本报告第6节的面积方向账，以及[面积复证分册](推导92B/area_audit.md)。'+r['reason']+'\n\n原证明定位：'+r['source']
    records[key]={**byid[key],**r,'proof':proof,'appendix':'area_audit.md'}

raw_candidates=read_json('geo_candidates.json')+read_json('area_candidates.json')
candidates=[]
for c in sorted(raw_candidates,key=lambda c:int(c.get('id',next(r['id'] for r in INV if r['name']==c['name']))[1:])):
    cid=c.get('id',next(r['id'] for r in INV if r['name']==c['name']))
    assert c['name']==byid[cid]['name']
    assert c['kind']=='必要条件'
    assert c['relation']==f'修订正式条目「{c["name"]}」'
    candidate={k:c[k] for k in ('name','kind','text','basis','derivation','relation')}
    if cid=='N61':candidate['derivation']='六个矿口邻格、取货边端头、核心角位与六格宽度逐项重证；只澄清“不被本条排除”不代表贴靠可实现。完整证明见推导92B.md第5节N61。'
    else:candidate['derivation']='保守补回已证范围，未否证原式；与另一项面积修订一并使用。完整证明见推导92B.md第5节'+cid+'及第6节。'
    candidates.append(candidate)
    records[cid]['new']=candidate
    records[cid]['status']='只改措辞' if cid=='N61' else '改结论（保守缩至已证范围；未否证原式）'

expected={r['id'] for r in INV if r['in_scope']}
assert set(records)==expected,(set(records)^expected)
assert len(INV)==77 and len(expected)==63
assert len(candidates)==3
assert normalize(read_json('foundation_a.json'))==normalize(read_json('foundation_b.json'))
snapshot=read_json('snapshot_sha256.json')
assert all(hashlib.sha256((ROUND/'前提快照'/name).read_bytes()).hexdigest()==digest for name,digest in snapshot.items())
confirmed=[r for r in records.values() if r['status']=='确认成立']
assert len(confirmed)==60

header='''# 第92轮B组：正式必要条件的步进复扫

日期：2026-10-02。状态：范围内63条均已给出复核结果；60条确认成立、1条只改措辞、2条保守缩至已证范围，否证0条。两条保守修订对应的原全范围结论仍未证成或否证，不计作“原文确认成立”。本席提交3条必要条件候选，不提交充分条件或简化。

**空矩形上界1110（仅30×37及转置）的证明保留。** 本次没有给出合格布局，也没有提升下界L=0。“内带缺口”和“面积预算”的修订补回历史证明实际使用的范围；用于1110上界及1110配置限制的分支都在该范围内。核心邻格仅澄清局部排除的量词。

## 1. 快照、范围与分类

唯一数学前提为本轮[前提快照](前提快照/)的游戏规则115行、求解任务、求解约束77条、求解充分条件11条。快照SHA-256保存在[指纹](推导92B/snapshot_sha256.json)，交付前再次逐文件比对一致。不补的设定仅作背景，没有作为推理前提。历史候选、旧报告及旧程序均作为需要重新审查的材料。

编号按77条原顺序，包括开头四条不得依赖的量。排除N01—N07、N20、N34、N41、N43、N48、N49、N51，共14条；N20、N34、N43、N48是额外命中已删名词的正文或据行。筛选记录见[全部条目清单](推导92B/inventory.json)。未对这些A组条目作整条认证；本席依赖其中某一事实时，在相关条目的证明中单独证明所需部分。

本报告中的必要条件均对所声称的全部布局及其每个达标可到达循环成立，附配置前提的只在该前提内使用。N10“种子自给”是配方收支事实，不是具体植物回路不断料的充分保证。没有条目被用作“不丢最优”的简化；所有静态放宽可行点均不当作布局。

## 2. 新时间规则在证明中的位置

每tick八步。一个运输物品格容量一且每件至少停八步，所以周期平均最多一件/tick；一tick/五tick配方每台最多每八/四十步一批。以上是上界。达标需求与总上界相等时，所有间隔才被迫取等：多等一步会在循环中反复损失产量。这一论证不声称“有空位就能同一步补货”。

每条证明都按真实成功移动、开批或完成事件记账，缓存未完成批次按原料计、完成后按产物计。满箱晚一步、元件先于非运输单位、混做18步一轮，均可令某些接法达不到必要取等，但不能突破容量上界。N42给的是闭窗口最大出货数，N56给的是“已经满速”时的箱头存量必要界，均已重新用步号证明。

接通先后引起的层数、同层先后、分流器数层分支、轮询起点和取货优先级，不取有利值。证明对其任意合法取值分别成立。现行相邻桥接器读法与题述两项拟改读法均保留容量、滞留和不越过事实，本席全部结论在两种读法下相同；没有借拟改读法恢复某条线路的满速来证明布局可行。

## 3. 逐条结果表

| 编号 | 名称 | 结论 | 一句理由 |
|---|---|---|---|
'''
parts=[header]
for key in sorted(records):
    r=records[key]
    parts.append(f'| {key} | {r["name"]} | {r["status"]} | {r["reason"].replace("|","／")} |\n')
parts.append('''
## 4. 三项修订与未决边界

- **核心邻格：只改措辞。** 原“只在……时不能”容易把未被局部条件排除读成必能贴靠；改为明确列出排除情形，其余情形只说本条不据此排除。没有声称任何具体贴靠布局可达。
- **内带缺口：保守改结论。** 原第54轮周边账明确要求矩形左下角a,b≥4；正式条文没有带上此条件。a=2时相邻圈可能碰矿石首格，其法向已在无箱加强的整组方向里计过，不能不加证明就再次计Y。另一个遗漏是右上角可能被超配闲置机器占据，却仍被原X计费两次。修订补a,b≥4，并把X中的全部制造机身、核心排除。
- **面积预算：保守改结论。** 含X+Y式同步使用上条修订的范围和X定义；两个不含周边项的预算、A=1110的配置与桩数结论不变。两项修订须一并审查。

上述两处范围缺口在旧证明一般化时已存在，并非步进规则新造的反例。角格放关闭粉碎机只证明旧计数映射不覆盖一个局部合法状态；它不是达标全厂反例。本席没有证原全范围不等式为假，也没有用“放宽模型能摆”冒充反例。缺的是a≤3或b≤3时补偿重复计费的统一证明，以及原角格额外两单位费用的全布局补偿证明。

早期报告保留情况：第1—56轮多份原报告所指/tmp路径已不存在，未假称已读取；读取了候选文件保存的完整推导及第57轮以后的重证，并在下文重新列出所用证明。无桥接器1044→1040的旧“整数尺寸”说法不足，因为1044有18×58、29×36；本席用现行箱体过站的314格界重新推出无箱≤1036、有箱≤1035，足以确认原1040，不另外提交加强候选。

## 5. 逐条条文、据与复证

确认条目使用快照原文登记；改动条目使用完整新条文。状态“待审”表示本席结论等待流水线审查，只有标明修订的三条进入候选数组。详细分册为[基础](推导92B/foundation_audit.md)、[流量与箱体](推导92B/counts_audit.md)、[几何](推导92B/geo_audit.md)、[面积](推导92B/area_audit.md)。

''')
for key in sorted(records):
    r=records[key]; c=r.get('new'); text=c['text'] if c else r['text'];basis=c['basis'] if c else r['basis']
    parts.append(f'### {key} {r["name"]} — {r["status"]}\n\n{r["name"]}：{text}\n\n据：{basis}\n\n推导：{r["reason"]}\n\n{r["proof"]}\n\n')
    if c:parts.append(f'种类：必要条件。关系：{c["relation"]}。\n\n')
    parts.append('状态：待审。'+('本席确认成立，不作为候选。' if not c else '作为修订候选提交。')+'\n\n')
parts.append('## 6. 面积方向账与修订条目的完整证明\n\n')
parts.append('本节同时支撑N66—N68、N74—N77。\n\n')
parts.append(area_proof.replace('## 4. 条带切线与四通结点','### 条带切线与四通结点').replace('## 5. 面积结论','### 面积结论').replace('本席复读证明，与本轮几何分席 N63 的复核相同。','N63给出两项动力排除的现行证明；本轮geo_corner_a/b对135支重新独立计算，逐支最优上界一致。').replace('本輪','本轮'))
parts.append('''
## 7. 程序、证据与限度

所有新脚本、数据、日志、分册和JSON都在[推导92B](推导92B/)。主报告之外未写入正式文件、候选文件或其他席位目录，未碰git，未跑内核cargo测试。各求解进程限制单线程；本席按主进程与三个分工各至多一核安排。没有使用有已知错误的sim2来认证结论。

| 核对项 | 两套编码及结果 | 证据性质 |
|---|---|---|
| 配方与数量 | foundation_a.py的有理数消元；foundation_b.py的20tick整数倒推：6113/20+2r件、217台、3291格、305/256通道、周期160步，逐字段相同 | 本轮独立算术重算 |
| 接口与箱预算 | counts_check_a/b.py的组合/位掩码与两种DP：关联164、55个增机组合、500组接口账一致 | 本轮独立算术重算 |
| 停批范围 | counts_freeze.py的快照解析库存证书与手抄配方次序：4、6、16配方 | 本轮独立编码 |
| 箱头窗口 | counts_check_a.json穷举全部13376个小相位/观察点组合；允许不同口同相位 | 辅助核对；全称证明见N56 |
| 方向权重与面积 | area_verify.py的支持集/流量向量、两套机群DP和两套尺寸筛选一致；Ω=219/2 | 本轮独立编码；可行放宽点不是布局 |
| 供电、边带与运输降幅 | geo_power_*与geo_small_checks记录域覆盖、两套端口模型、两套边带/DP | 新回执与旧完成回执分别记录于几何分册 |
| 无箱额外八次运输访问 | counts_ore_certificate_check.json核第63轮47+47份INFEASIBLE回执，预算7排除；模型域与现规则重新映射 | 旧静态证据复审，不冒称本轮重求 |
| 1110上界排除链 | area_verify.json保存14份历史完成回执；已读必要模型映射，所用高面积分支均a,b≥4且全部机器在产 | 旧完整求解的审计，不是新布局 |

N54完整双模型重跑的首支未及时完成，已停止，记录于counts_ore_probe.json；该未完成运行不提供任何不可行证据。普通供电权重55的CP-SAT曾返回UNKNOWN，也不当作54上界的证据；成功的独立模型与被复用的旧回执范围详见geo_audit.md及对应JSON。其余本轮小算术脚本成功完成。保留这些未完成状态，是为了区分本轮重算和静态旧证据复审。

结论没有给出一个全厂反例。两条保守修订以现行规则完整证成，原条文在被收窄掉的范围内是否仍成立是此次留下的明确断点。所有确认条目的承重步骤都是当前规则下的容量、守恒、静态死锁或几何必要条件，没有引用旧立即补货作为充分保证。
''')
REPORT.write_text(''.join(parts))
(HERE/'audit_records.json').write_text(json.dumps([records[k] for k in sorted(records)],ensure_ascii=False,indent=2)+'\n')
(HERE/'candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2)+'\n')
result={'report_path':str(REPORT),'candidates':candidates,'summary':'复核63条：60条确认、1条措辞修订、2条保守修订；两处原全范围未决，U=1110保留。','status':'复核完成；两处原全范围仍未证成或否证'}
(HERE/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report_path':str(REPORT),'in_scope':len(records),'confirmed':len(confirmed),'candidate_names':[c['name'] for c in candidates],'bytes':REPORT.stat().st_size},ensure_ascii=False))
