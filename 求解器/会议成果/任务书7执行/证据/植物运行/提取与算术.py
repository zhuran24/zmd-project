#!/usr/bin/env python3
"""只复算既有 A/B 送料数据及本文局部算术；不是游戏执行器。"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter, defaultdict
import contextlib, csv, io, json, runpy

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent
ROOT = OUT.parents[2]
OLD = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
def write(p, x):
    write_text_if_changed(p,json.dumps(x, ensure_ascii=False, indent=2)+'\n')
def write_text_if_changed(p, value):
    if not p.exists() or p.read_text()!=value:
        p.write_text(value)
def rate(x): return str(F(x))

B = json.loads((ROOT/'求解器/数据/候选B/contract.json').read_text())
with (OLD/'machines.csv').open() as fp: original_machines=list(csv.DictReader(fp))
assert len(original_machines)==len(B['machines'])==219
for row,m in zip(original_machines,B['machines']):
    assert row['机器id']==m['id']
    assert row['配方']==m['recipes'][0]['recipe']
    assert F(row['批次每20tick'])/20==F(m['recipes'][0]['planned_batch_rate']['value'])
with (OLD/'channels.csv').open() as fp: original_feeds=list(csv.DictReader(fp))
assert len(original_feeds)==len(B['logical_feeds'])==315
for row,f in zip(original_feeds,B['logical_feeds']):
    assert row['通道id'][1:]==f['id'][2:]
    assert row['物品']==f['item']
    assert F(row['件每20tick'])/20==F(f['planned_rate']['value'])
    if row['源机器id'].startswith('M'):assert row['源机器id']==f['source']
    if row['目标机器id'].startswith('M'):assert row['目标机器id']==f['target']
# portmatch.py 全文已检查：只定义、计算、打印，无写文件、子进程或网络操作。
# 重放已定版的速率分配，未搜索新布局；旧打印中的结论仅作历史输出。
capture = io.StringIO()
with contextlib.redirect_stdout(capture):
    A = runpy.run_path(str(OLD/'portmatch.py'))
write_text_if_changed(HERE/'候选A原脚本重放.log',capture.getvalue())

species = ['荞花', '砂叶']
plant_items = {s+t for s in species for t in ('','种子','粉末')}
raw_items = {s+t for s in species for t in ('','种子')}
def record(fid, source, target, sp, tp, item, r):
    return dict(id=fid, source=source, target=target, source_port=sp,
        target_port=tp, item=item, expected_rate_per_tick=rate(r),
        proven_actual_rate_per_tick=None,
        actual_rate_status='具体候选全部初态及全参数未证',
        transport_cells=None, occupied_physical_cells=None,
        initial_inventory=None, guarantee_reference=None)

bf = [record(f['id'], f['source'], f['target'], f['source_port'],
      f['target_port'], f['item'], f['planned_rate']['value']) for f in B['logical_feeds']]
af=[]; sout=Counter(); tin=Counter(); ore=0
for i,(item,s,d,n) in enumerate(A['edges']):
    src = f'A_M{s.gid:03}' if s is not None else f'A_ORE{ore:03}'
    if s is None: ore+=1
    dst = 'A_CORE' if d=='核心' else f'A_M{d.gid:03}'
    sout[src]+=1; tin[dst]+=1
    af.append(record(f'AF{i:03}',src,dst,f'{src}:out:{sout[src]}',
        f'{dst}:in:{tin[dst]}',item,F(n,20)))

def bmachine(m):
    return dict(id=m['id'], kind=m['kind'], recipes=[dict(name=x['recipe'],
      expected_batches_per_tick=x['planned_batch_rate']['value'],
      proven_actual_batches_per_tick=None) for x in m['recipes']],
      coordinates=None, orientation=None)
am=[]
for m in A['insts']:
    am.append(dict(id=f'A_M{m.gid:03}', kind=('精炼炉' if m.group.startswith('精炼-') else m.group.split('-')[0]+'机'),
      recipes=[dict(name=m.group,expected_batches_per_tick=rate(F(m.batches,20)),
                    proven_actual_batches_per_tick=None)],coordinates=None,orientation=None))

def audit(feeds):
    selected=[f for f in feeds if f['item'] in plant_items]
    return dict(logical_feeds=len(feeds), plant_and_powder_feeds=len(selected),
      item_edge_counts=dict(Counter(f['item'] for f in selected)),
      raw_plant_logical_feeds=sum(f['item'] in raw_items for f in feeds),
      actual_transport_cells=None, reason='源表没有坐标、路径或带长；逻辑边不等于物理格')

def roots(feeds):
    # 植物种子/植株图 SCC：每个 SCC 的入出边列出，以便检查局部收支边界。
    out={}
    for s in species:
        fs=[f for f in feeds if f['item'] in {s,s+'种子'}]
        nodes=sorted({f[k] for f in fs for k in ('source','target')})
        adj={n:[] for n in nodes}
        for f in fs: adj[f['source']].append(f['target'])
        idx={}; low={}; stack=[]; on=set(); comps=[]
        def visit(v):
            idx[v]=low[v]=len(idx);stack.append(v);on.add(v)
            for w in adj[v]:
                if w not in idx: visit(w);low[v]=min(low[v],low[w])
                elif w in on: low[v]=min(low[v],idx[w])
            if low[v]==idx[v]:
                c=[]
                while True:
                    w=stack.pop();on.remove(w);c.append(w)
                    if w==v:break
                comps.append(sorted(c))
        for n in nodes:
            if n not in idx:visit(n)
        out[s]=[dict(machines=c,incoming=[f['id'] for f in fs if f['target'] in c and f['source'] not in c],
                    outgoing=[f['id'] for f in fs if f['source'] in c and f['target'] not in c])
                for c in comps if len(c)>1 or c[0] in adj[c[0]]]
    return out

capacities={}
for s,p,h,g,b in [('荞花',11,6,6,2),('砂叶',21,11,11,3)]:
    capacities[s]=dict(planter=p,harvester=h,crusher=g,
      ordinary_all_materials=100*(p+h+g),
      ordinary_seeds=50*(p+h+g),
      ordinary_seeds_normal_recipe_slots=50*(p+h),
      ordinary_plants=50*(p+h+g),
      ordinary_seed_plus_plant=100*(p+h)+50*g,
      reachable_normal_cache_all_materials=p+2*h+b*g,
      reachable_normal_cache_seed_plus_plant=p+2*h+g,
      seed_plus_plant_with_normal_cache=100*(p+h)+50*g+p+2*h+g,
      transport_slots_to_add=None,physical_cache_capacity='infinite')

inventory_definitions=dict(
  machine_group='每种仅计其P/H/G机器组；其他机器中的调试寄存另计。',
  ordinary_all_materials='R17、44、50：每机两个普通格各50，全部物料的容量预算。',
  ordinary_seeds='R13、17：本组每机普通格同一种种子至多50；全放输入、输出空且关闭可达到。荞花1150、砂叶2150，合3300。',
  ordinary_seeds_normal_recipe_slots='P输入、H输出放本种种子，其他普通格只放其计划配方物品或空；荞花850、砂叶1600，合2450。',
  ordinary_plants='R13、17：本组每机普通格同一种植株至多50；全放输入可达到。正常配方槽位中P输出、H输入、G输入亦给相同容量。',
  normal_recipe_slots='P输入种子/输出植株；H输入植株/输出种子；G输入植株/输出粉末，各格也可为空。',
  ordinary_seed_plus_plant='仅normal_recipe_slots域，100*(P+H)+50*G；两种合5750。',
  normal_cache='R18、35：从空缓存开始且仅经正常制造门流入，单机至多一批，按在制输入或完成产物所在阶段计。',
  reachable_normal_cache_all_materials='normal_cache域下各机最大产物或输入批量之和。',
  reachable_normal_cache_seed_plus_plant='normal_cache域下P+2*H+G；G完成后的粉末不计N。',
  seed_plus_plant_with_normal_cache='normal_recipe_slots与normal_cache共同成立时的联合N上界，荞花2029、砂叶3804，合5833；运输实际格另加。',
  safety='容量上界与充分起动条件分列；默认程序后置状态及充分安全域由PR-01/04承接。')
revision_records=[
 dict(date='2026-09-21',finding='F13',change='ordinary_seeds改为物理种子容量1150/2150；新增ordinary_seeds_normal_recipe_slots保留850/1600；inventory_definitions列R13、17前件及见证。'),
 dict(date='2026-09-21',finding='F14',change='明确5833、277及217公式的正常槽位和正常缓存域；额外寄存另计。'),
 dict(date='2026-09-21',finding='F01/F16—F18',change='绑定18项处理与修订前独立否证范围；未证项给具体断点，作者修订待独立重核。')]

checks={
  'original_B_CSV_machine_and_channel_comparison':'219 machines and 315 feeds match',
  'candidate_A':audit(af),'candidate_B':audit(bf),
  'raw_graph_cycle_components_A':roots(af),'raw_graph_cycle_components_B':roots(bf),
  'capacities_219':capacities,
  'C82_adjacent_groups':{'plant_1_to_2':dict(sum=2,k=2,passes_numeric=True),
      'seed_2_to_2':dict(sum=4,k=2,passes_numeric=False),
      'buck_powder_2_to_2':dict(sum=4,k=2,passes_numeric=False),
      'sand_powder_3_to_3':dict(sum=6,k=3,passes_numeric=False)},
  'one_mixed_inlet_rate_upper':'1/3',
  'mixed_full_input_D_bounds':[-48,99],
  'three_channel_use_ratio':{'two_to_seed_one_to_crush':'2:1','one_to_seed_two_to_crush':'1:2'},
  'added_crusher_branch':{'total_machines':220,'extra_area':9,
      'remaining_sand_crusher_rates':['1/3','1/6'], 'new_plant_allocation_H_G1_G2':['1/2','1/3','1/6']},
  'scope':'算术、图分量与局部状态检查；不是内核轨迹或完整布局证书',
  'inventory_definitions':inventory_definitions,
  '修订记录':revision_records}
assert len(af)==314 and len(bf)==315
assert checks['candidate_A']['raw_plant_logical_feeds']==66
assert checks['candidate_B']['raw_plant_logical_feeds']==66
assert sum(c['seed_plus_plant_with_normal_cache'] for c in capacities.values())==5833
assert sum(c['ordinary_all_materials']+c['reachable_normal_cache_all_materials'] for c in capacities.values())==6711
assert [capacities[s]['ordinary_seeds'] for s in species]==[1150,2150]
assert [capacities[s]['ordinary_seeds_normal_recipe_slots'] for s in species]==[850,1600]

obligations=[
 ('PR-01','任务5','默认清缓存、填满、开机、末级最后的全部后置状态；每一根回路的可用物料与释放接收前缀'),
 ('PR-02','任务4及任务6','实际通行下的偏采种/偏粉碎拒收调节、最终完成率及全段最大净损失'),
 ('PR-03','任务6','M174/M195 从满首格到 C82 起点，全部离线顺序、失败扫描与逐种成功字序'),
 ('PR-04','任务5—7联合','本文局部安全集合与堵满释放、实际带长、下游服务之间的联合保持性'),
 ('PR-05','任务7','全部路径、格数、桥轴方向、自动通道、供电；A/B逐机逐口服务能力'),
 ('PR-06','任务4、6、7','A两路D高−2D低及Q全前缀界；B三首格与M150/M151共享同种输入的服务；220实际3:2:1路径与突发排出；217输入/输出清旧种字序'),
 ('PR-07','任务4—7','完整基地同总数产率命题、完整反例或充分证明；局部同N反例的独立审查见F12，分别相等种子/植株的加强命题仍开放')]
review=json.loads((HERE/'否证逐项处理.json').read_text())
finding_map={i:[f['id'] for f in review['findings'] if i in f['remaining_unproved']] for i,_,_ in obligations}
interface=dict(schema='plant-pilot-v2',date='2026-09-21',status='partial',
  evidence_scope='既有候选实际逻辑连接；局部充分条件；完整物理运行待证',
  L=0,U=1113,rate_unit='件或完成批次/tick，字段名区分',
  sources='证据/植物运行/输入当前指纹.json',
  source_changes='证据/植物运行/来源增量.json',
  current_rule_sha256='d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a',
  candidates=[dict(id='A219',source=str(OLD/'portmatch.py'),machines=am,feeds=af,audit=audit(af)),
              dict(id='B219',source=str(ROOT/'求解器/数据/候选B/contract.json'),machines=[bmachine(m) for m in B['machines']],feeds=bf,audit=audit(bf))],
  conditional_guarantees=[
   dict(id='SAFE-FULL-TREE',reference='植物运行试点.md §5.2',
     structures=['B荞花满速树','B砂叶满速树','A荞花五个满速分支','A砂叶十个满速分支'],initial_set='专用线已处于每tick搬一件的切面；逐机输入a∈[0,49]；取货0；一批在制；无共用物品格',
     parameters='每条路径整数长度≥1，合法嵌入，粉末边界逐路每tick可接1；全局tick平移任意',
     proven_actual_rates={'荞花':{'P':'10','H':'5','G':'5','powder':'10'},'砂叶':{'P':'20','H':'10','G':'10','powder':'30'}},
     candidate_realization_status='路径及默认起法尚未验收'),
   dict(id='SAFE-HALF-LOOP',reference='植物运行试点.md §5.3',
     structures=['M174-M201-M057','M195-M212-M068'],initial_set='P输入q粒种子，H/G及全部路径和缓存空；H/G有电开启后再开P',
     parameters='各私有路径整数长度≥1；l_H+l_S+3≤q≤50；粉末边界逐口每tick可接1',
     proven_actual_rates={'P':'1','H':'1/2','G':'1/2','荞花粉末':'1','砂叶粉末':'3/2'},
     candidate_realization_status='局部条件族，默认堵满到达该族待证'),
   dict(id='BATCH-EQUAL',reference='植物运行试点.md §3.3',
     structures=['2件双口','3件三口'],initial_set='无旧输出，首格全空，恰k件完成',
     parameters='k=2或3；各首格独占且下次批到来前腾空；连续批间隔≥1tick',
     proven_actual_rates={'per_port':'每个完成并排清的批次恰1件；若批率h已证，则每口h'},
     candidate_realization_status='数值和局部定理已自核，首格服务待核'),
   dict(id='MIXED-Z',reference='植物运行试点.md §4',initial_set='Z0+D(j)对所有前缀位于(-99,50)',
     parameters='单配方2A+B、单保序混线；供料和完成排货有限时间兑现',
     proven_actual_rates=None,guarantee='无限来料给无限批次，排除永久输入互等；指定平均批率需时间界')],
  inventory=capacities,inventory_definitions=inventory_definitions,
  local_geometry=dict(reference='证据/植物运行/局部结构.json',raw_transport_slots=23,
      buck_transport_slots=24,sand_transport_slots=26,latest_first_seed_return_tick=23,
      initial_seed_range_inclusive=[23,50],normal_seed_plus_plant_capacity=277,
      capacity_scope='P/H/G普通格满足normal_recipe_slots、缓存满足normal_cache时，N≤250+4+23=277；充分起动族另取P输入23…50、其余空。',
      full_factory_embedding=False),
  same_total_counterexample=dict(reference='植物运行试点.md §5.4',
      initial_N=50,initial_other_species_N=0,
      start_A={'P_input':'50种子','other_local_inventory':'0'},
      start_B={'G_input':'50植株','other_local_inventory':'0'},
      long_term_G_A='1/2',long_term_G_B='0',
      material_counts_by_form_equal=False,
      scope='同一三机开放粉末服务边界；完整基地成品率对照未证'),
  other_configurations=[
      dict(id='217',machine_counts={'种植':32,'采种':16,'粉碎':68},
           inventory_scope='植物仅位于P/H正常种子植株槽位、g台植物G输入、这些机器正常单批缓存及实际植物运输格；其他调试寄存另计。',
           seed_plus_plant_upper='4864+51*g+L植，g为实际加工植株的不同粉碎机数',
           g16_special_upper='5680+L植',status='混做清空与逐口实现待证',reference='植物运行试点.md §7.5'),
      dict(id='220',extra_area=9,remaining_sand_G_rates=['1/3','1/6'],
           root_plant_allocation_H_G1_G2=['1/2','1/3','1/6'],
           status='取消粉末扇出后的输入3:2:1分配待证',reference='植物运行试点.md §7.4')],
  open_items=[dict(id=i,owner=o,breakpoint=b,status='unproved',missing_category='缺构造与推导',review_findings=finding_map[i]) for i,o,b in obligations],
  for_owner=[],default_start_certified=False,full_layout_certified=False,
  review_status=dict(report='复核/否证-任务4.md',report_sha256=review['review_sha256'],
    reviewed_main_sha256='b50e587450c16b18a1f56603369364cd1a630ec46955c67333e8c2ef80dcfb3c',
    reviewed_interface_sha256='e0da9c19fca1833eedc17b5bb0de126dcf86748df73301c69caf073cf2e76abb',
    disposition_file='证据/植物运行/否证逐项处理.json',
    accepted_findings=18,revision_independent_recheck='pending'),
  修订记录=revision_records)
write(OUT/'送料与接口.json',interface)
write(HERE/'算术与图核验.json',checks)

lines=['# 候选 A/B 的植物机器与逐口送料清单','',
 '日期：2026-09-21。范围：从原始速率候选提取的逻辑连接。所有速率均为期望值；实际完整运行率尚未认证。端口编号是逻辑记录身份，不是坐标。',
 '', '现行来源见[输入当前指纹](输入当前指纹.json)，开工元数据见[输入指纹](输入指纹.json)，所有送料记录见[送料与接口](../../送料与接口.json)。','']
for label,ms,fs in [('A219',am,af),('B219',[bmachine(m) for m in B['machines']],bf)]:
    lines += [f'## {label}','', '| 机器 | 配方 | 期望批/tick |','| --- | --- | --- |']
    for m in ms:
        if any(x['name'].split('-')[0] in ('种植','采种') or x['name'] in ('粉碎-荞花','粉碎-砂叶') for x in m['recipes']):
            lines.append('| '+m['id']+' | '+','.join(x['name'] for x in m['recipes'])+' | '+','.join(x['expected_batches_per_tick'] for x in m['recipes'])+' |')
    lines += ['', '| 记录 | 出口 → 入口 | 物品 | 期望件/tick |','| --- | --- | --- | --- |']
    for f in fs:
        if f['item'] in plant_items:
            lines.append(f"| {f['id']} | {f['source_port']} → {f['target_port']} | {f['item']} | {f['expected_rate_per_tick']} |")
    lines += ['', '循环分量的外部收支：','', '| 种类 | 分量机器 | 跨入 | 跨出 |','| --- | --- | --- | --- |']
    for s,cs in roots(fs).items():
        for c in cs:lines.append(f"| {s} | {','.join(c['machines'])} | {','.join(c['incoming']) or '无'} | {','.join(c['outgoing']) or '无'} |")
    lines += ['']
write_text_if_changed(HERE/'逐机逐口清单.md','\n'.join(lines)+'\n')
print('PASS: A=314 B=315；各66条原株种子逻辑边；普通种子物理容量1150/2150，正常种子槽位850/1600；正常槽位和单批缓存域N≤5833+实际运输格，全部物料≤6711+实际运输格。')

# 修订记录
# 2026-09-21 F13：物理种子公式改为50*(P+H+G)，正常种子槽位另列50*(P+H)，同步两份JSON的定义和修订记录。
# 2026-09-21 F14：联合N及217/局部公式附正常存放域；F01、F16—F18：绑定独立否证与未证断点。
# 相同内容不再重写，保留未改动证据的字节与mtime；全部写入仍在本席路径。
