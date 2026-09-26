#!/usr/bin/env python3
"""Render the current numeric results as a Chinese report and per-run details."""
import collections,hashlib,importlib.metadata,json,os,platform,sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[2]
TITLES={'flow_all':'几何＋矿石子集层＋全体物品合计层','flow_ore':'几何＋矿石子集层','geometry':'1113 纯几何必要条件放松','residual75':'第 75 轮剩余供电格组全域放松（A 编码）'}
ALGO={'metis':'METIS','kahypar':'KaHyPar','manual':'人工四象限'}
MODES={'full':'完整约束','noglobal':'拿开全局行'}
def load(p):return json.loads(p.read_text())
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def fmt(v):return f'{v:,}'
def short(label):
    if label.startswith('非地域'):return '类别'
    if label.startswith('以地域'):return '地域'
    if label.startswith('只剩'):return '仅一组'
    return '混合'
def rel(source,base=OUT):return os.path.relpath(ROOT/source,base)
def fam(s):return s.replace('几何及选择／','').replace('矿石子集层／','矿石层：').replace('全体物品合计层／','全体层：')
def distribution(d):return '；'.join(f'{fam(k)} {fmt(v)}' for k,v in d.items()) or '无'
def pointbox(b):return '无坐标' if b is None else f'x={b[0]:g}…{b[2]:g}，y={b[1]:g}…{b[3]:g}'
def ident(d):return f"{d['dataset']}__{d['algorithm']}_{d['mode']}_k{d['k']}"
def explanation(d):
    cats=list(d['separator_summary']['families'])[:3]
    first='如果上层先定下列出的连接变量（主要包括'+'、'.join(map(fam,cats))+'），'
    if d['scope']=='window':first+='并把窗口外变量也作为已定输入，'
    first+=('完整约束' if d['mode']=='full' else '拿开全局行后的保留约束')+'就不会再同时用到两个下层组的未定变量。'
    groups=[]
    for b in d['blocks']:
        if not b['count']:groups.append(f"组{b['block']}为空");continue
        groups.append(f"组{b['block']}主要是"+'、'.join(fam(x) for x in list(b['families'])[:2]))
    second='下层'+ '；'.join(groups)+'。'
    if d['mode']=='noglobal':second+=f"另有 {d['removed_global_rows_still_spanning_blocks']} 条已拿开的全局行仍跨这些组，原模型须继续处理它们。"
    return first+'\n\n'+second
def details(d):
    id=ident(d);name=TITLES[d['model']];scope='全场' if d['scope']=='whole' else '14×14 变量窗口';path=OUT/'明细'/f'{id}.md';path.parent.mkdir(exist_ok=True)
    raw=f"../raw/{d['dataset']}";s=d['separator_summary'];brows=[]
    for b in d['blocks']:
        brows.append([b['block'],fmt(b['raw_variables']),fmt(b['count']),pointbox(b['xy_bbox']),distribution(b['families']),f"{b['components']['count']} 个；最大 {b['components']['largest']}、最小 {b['components']['smallest']}"])
    parts=[f"# {name} · {scope} · {ALGO[d['algorithm']]} · {MODES[d['mode']]} · k={d['k']}","日期：2026-09-25。状态：划分完成，保留约束的逐行分隔检查通过。",'## 结论和条件',explanation(d),f"原始分组的描述：**{d['raw_partition_signature']['label']}**。固定连接变量后的描述：**{d['remaining_partition_signature']['label']}**。这些名称描述变量出现关系；没有检查被固定变量能否取到相容值，也没有传播其余变量。",'## 数字',table(['量','数值'],[['变量数',fmt(d['variables'])],['约束总数',fmt(d['constraints'])],['参与本次划分的约束数',fmt(d['active_constraints'])],['全局约束数',fmt(d['global_constraints'])],['连接变量 S',fmt(d['separator_variables'])],['连接约束 L',fmt(d['linking_constraints'])],['取 S 前的跨组约束 C',fmt(d['raw_cut_constraints'])],['仅涉及 S 的约束数',fmt(d['master_only_constraints'])],['取 S 前各组大小',' / '.join(map(fmt,d['raw_block_sizes']))],['取 S 后各组大小',' / '.join(map(fmt,d['remaining_block_sizes']))],['剩余最大组 / 最小组',f"{fmt(d['remaining_max_block'])} / {fmt(d['remaining_min_block'])}"],['实际连通分量数',fmt(d['actual_connected_components'])],['实际最大 / 最小连通分量',f"{fmt(d['actual_largest_component'])} / {fmt(d['actual_smallest_component'])}"],['单变量连通分量数',fmt(d['actual_singleton_components'])],['固定 S 后仍跨组的保留约束','0'],['拿开后仍跨剩余组的全局约束',fmt(d['removed_global_rows_still_spanning_blocks'])],['划分工具用时（秒）',f"{d['partition_seconds']:.3f}"]]),'## 每组分别是什么',table(['组','原变量数','剩余变量数','代表点范围','剩余变量含义（全量）','组内连通分量'],brows),'## 连接变量按含义归类', '区域名称以全场 x=35、y=35 为界。代表点不是物理范围；供电桩二维前缀和的代表点只是数组索引。方向列对相邻运输格流量表示流向；对端口流量表示从运输格指向单位的方向，不一定是流向。',table(['类别','数量','代表点范围','分布区域','方向 / 存货边','变量名例子'],[[fam(f),fmt(n),pointbox(s['family_details'][f]['xy_bbox']),distribution(s['family_details'][f]['regions']),('方向 '+distribution(s['family_details'][f]['directions'])+'；存货边 '+distribution(s['family_details'][f]['input_sides'])), '<br>'.join('`'+v['name']+'`' for v in s['examples'][f])] for f,n in s['families'].items()]),'## 连接约束按含义归类',table(['类别','数量','原约束编号例子','建模位置'],[[f,fmt(n),d['linking_constraint_examples'][f]['constraint_id'],f"[{Path(d['linking_constraint_examples'][f]['file']).name}:{d['linking_constraint_examples'][f]['line']}]({rel(d['linking_constraint_examples'][f]['file'],path.parent)})"] for f,n in d['linking_constraint_categories'].items()]),'## 复查入口',f"- [工具原始分组 JSON]({raw}/partitions/{d['algorithm']}_{d['mode']}_k{d['k']}.json)：每个局部变量的组号、种子、工具目标值。\n- [结构结果 JSON]({raw}/analyses/{d['algorithm']}_{d['mode']}_k{d['k']}.json)：S 全部原变量编号、L 全部原约束编号、类别、方向、连通分量统计。\n- [全部变量名称及含义](../models/{d['model']}/variables.json)。\n- [输入范围]({raw}/input.json)。\n- [全局约束逐条清单](../models/{d['model']}/global_constraints.json)。",'连接变量是从工具切分按确定规则取出的点分隔，不是最小点分隔。L 是涉及 S 和剩余组的约束，再并入所有被拿开的全局行；C 是取 S 前跨工具分组的约束。这三列不能相互替代。']
    if d['scope']=='window':
        meta=load(OUT/'raw'/d['dataset']/'input.json');outside=meta['original_variables']-meta['variables'];parts.insert(5,f"此结果只覆盖代表点在 `[16,30)×[16,30)` 内的变量和无坐标变量；每条原约束只保留这组变量的引用。窗口外还有 {fmt(outside)} 个变量。完整约束版若要当作原模型的纯变量分隔，需同时固定这些窗口外变量，合计为 {fmt(outside+d['separator_variables'])} 个；本页 L 等数字仍是窗口口径。拿开全局行版还须处理全局行。")
    path.write_text('\n\n'.join(parts)+'\n');return id

def main():
    result=[]
    for p in sorted((OUT/'raw').glob('*/analyses/*.json')):result.append(load(p))
    for d in result:details(d)
    lookup={ident(d):d for d in result};metas={n:load(OUT/'models'/n/'metadata.json') for n in TITLES};structs={n:load(OUT/'models'/n/'structure_summary.json') for n in TITLES}
    complete=len(result)==74
    parts=['# 70×70 基地模型的结构检测',f"日期：2026-09-25（America/New_York）。状态：{'已完成' if complete else '进行中'}。{'74' if complete else len(result)} 组划分已保存；只构建和检查变量出现关系，没有调用模型求解。",'## 结论',
    '**有非按地方分开的候选，但它们主要是建模变量类别的分组。** 纯几何模型的全场普通图，以及第 75 轮的全域普通图，出现了把结构占格、供电相关量等分到不同组的例子。两个流量模型的 14×14 窗口也出现了机型选择、端口流量、逐台收出量分别成组的例子。不能将这些例子称为独立生产链。',
    '`layer="all"` 实际含两个网络：把源矿、蓝铁矿合并的矿石子集层，以及把所有物品相加的全体物品层；两层共用摆位、机型、运输格和桥接器状态。模型没有逐种物品的弧流量，也没有把每台制造单位收出量按配方比例连接。因此，本次没有得到“按单独物品或配方生产链分开”的检测结果。',
    '全局台数、运输总数、物料收出总量和面积账会把各处变量连起来。把这些行拿开后看到的分块，只对保留的约束成立；每份明细另报仍跨剩余组的全局行。完整约束版则逐条检查了固定 S 后全部约束至多涉及一个剩余组。',
    '**这里的独立是原始编码的变量出现关系。** 候选摆位变量数不是实际机器台数；固定 S 之后，一些辅助变量可能随之被确定。本次没有做预处理、取值传播、可行性搜索或约束推导，未检查下层还有多少有效自由度。',
    '## 模型和范围',table(['模型','原变量数','原约束数','全局行','构建用时'],[[TITLES[n],fmt(metas[n]['variables']),fmt(metas[n]['constraints']),structs[n]['global_constraints'],f"{metas[n]['build_seconds']:.2f} 秒"] for n in TITLES]),
    '- 全体流量与矿石流量：直接调用 `flow_model_global.build(position, layer, cut_mode="formal")`，空矩形左下角 `(49,17)`、尺寸 `21×53`；保留全部 47 个仓库取货口联合边带模式和 P=10、11、12，`boundary_cuts=False`。没有调用 `run()` 或 `main()`。\n- 纯几何：按 `1113放松/positions.json` 取 `(49,17)`，直接调用 `solve_relaxation.build(position, boundary_cuts=False)`；未使用 `(49,13)` 的旧导出文件。其 J 域是 0…6；流量目录几何编码的 J 域是 0…12，沿用各自原脚本。\n- 第 75 轮：采用 `residual_model75.py` 的 A 编码，`cap=187`、偏移 `(0,1)`，3376 个中心、403 个格组，不固定旧见证，不固定 J 或 S 分支。只执行其已有建模语句，到 `if a.fixed` 之前停止。底座 `cp72.build(groups=False)` 显式保留触及四条边段的制造单位／协议核心候选和全域供电桩，再加剩余中心、格组；这本来就是该模型的范围，并非本次另删掉内部机器。',
    table(['检测工具','全体流量 / 矿石流量','纯几何','第 75 轮'],[['KaHyPar 超图，完整／拿开全局行','均为全场，k=2、4、8','均为全场，k=2、4、8','均为全域，k=2、4、8'],['METIS 普通图，完整约束','14×14 变量窗口，k=2、4、8','全场及 14×14 窗口，k=2、4、8','全域，k=2、4、8'],['METIS 普通图，拿开全局行','全场及 14×14 窗口，k=2、4、8','全场及 14×14 窗口，k=2、4、8','全域，k=2、4、8'],['人工四象限参照','全场和窗口，各两种全局行口径','全场和窗口，各两种口径','全域，两种口径']]),
    '### 两个流量模型的普通图缩了什么',
    '完整全体流量、矿石流量按每条约束展开点对，分别产生 **2,453,280,448**、**896,007,522** 次无向点对（包含重复，不是去重边数）。这两项完整普通图没有展开并存下；用同一个 `[16,30)×[16,30)` 变量窗口控制内存。制造单位按候选机身中心选变量；格状态和弧流量按格代表点；供电桩二维前缀和按索引代表点；相关机型、逐台收出量跟随候选摆位；无坐标账目变量保留。然后对每条原约束取变量引用与窗口变量集合的交集。它是原图的诱导子图，不是一个新建的 14×14 游戏模型。',
    '窗口保留的候选机身可能伸出窗口，外部变量也可能继续连接内部组。因此窗口里的 S 不能直接当作全场 S；各份明细给出同时固定全部窗口外变量后的总数。完整约束普通图和拿开全局行普通图都有同窗口结果，另有拿开全局行的全场结果，不混为同一规模。',
    table(['变量窗口','变量数','接触该窗口的约束数','全局行'],[[TITLES[n],fmt(load(OUT/'raw'/f'{n}_window/input.json')['variables']),fmt(load(OUT/'raw'/f'{n}_window/input.json')['constraints']),load(OUT/'raw'/f'{n}_window/input.json')['global_constraints']] for n in ('flow_all','flow_ore','geometry')]),
    '## 怎么量',
    '每个 CpModelProto 变量都是一个点，每条约束引用的变量集合是一条超边。引用包括 enforcement literal；负 literal 按 `-i-1` 还原变量编号。线性约束取变量表，布尔约束取 literal 表，表约束取表达式中的变量。脚本还实现了区间引用等类型的提取，并对未支持类型报错；本次实际出现的是 linear、bool_or、bool_and、exactly_one、table。不按系数大小加权，不先删除固定域变量。',
    '普通图使用布尔稀疏矩阵 `B.T @ B`，去掉对角线并去重：同处一条约束就连一条无向边，不把一条超边换成星形图来交给 METIS。超图保留每条约束作为独立超边；只有空边和单点边不送进 KaHyPar，因为其跨组代价恒为零，统计及逐行复查仍保留它们。',
    '两种表示计算切分代价的方式不同。例如，一条小制造单位总数等式，在普通图里会把全场所有小制造单位候选两两相连；在超图里仍是一条超边。普通图出现同类变量遍布全场却归为一组的结果，可以直接从这种连边方式理解，不需要把它解释成一条独立生产链。',
    'METIS 做直接 k 路划分，KaHyPar 使用连接度减一（km1）目标；随机种子固定 20260925，不平衡参数 3%，变量和边权均为 1。完整全体流量 k=2 使用官方标准配置；其 k=4、8 使用 `km1_kKaHyPar_fm_4runs.ini`，从官方 eco 配置改为 FM 细化、初始划分 4 次；其余超图结果使用官方 eco 配置。各配置文件保存在 `tools/`，实际参数见原始 JSON。工具文档见 [PyMETIS](https://documen.tician.de/pymetis/functionality.html) 和 [KaHyPar 官方项目](https://github.com/kahypar/kahypar)。',
    '人工参照按代表点切四象限：全场以 x=35、y=35 为界，窗口以 x=23、y=23 为界；无坐标变量放在西南组。没有按变量数配平。空矩形贴右上边界，不能把其四周机械分成四个非空边带，因此采用此四象限参照。',
    '### S、L、C 与“块”',
    '下文 S 指连接变量集合；第 75 轮模型另有一个名字也叫 `S` 的面积缺口总账变量，含义不同。',
    '- **S（连接变量）**：从工具的跨组边取一个可验证的点分隔。把跨组超边按原变量数从大到小处理，同大小按原约束编号；每条边只保留当前剩余变量最多的一个组，把其他组变量放进 S，同数时保留组号小者。这覆盖了所有跨组普通图边；不是最小点分隔。\n- **C（原跨组约束）**：取 S 以前，涉及至少两个工具分组的保留约束数。\n- **L（连接约束）**：同时涉及 S 和至少一个剩余组的约束，并入所有被拿开的全局行。同一行只计一次。只涉及 S 的行另记为上层内部约束；若它同时是被拿开的全局行，也属于 L。\n- **剩余组大小**：删去 S 后每个工具组的变量数；最小值包含空组。工具的 3% 平衡条件只管取 S 以前，不能用于这些剩余大小。\n- **实际连通分量**：固定 S 后，在保留约束的变量—约束二部图中实际计算；单变量分量保留。它们可能远多于 k，因此另报数量和最大／最小值。',
    '“地域／类别／混合”根据代表点分布、每组变量含义、同格变量是否同组共同描述。原始 JSON 还保存同格多数一致率及分组与类别、7×7 地域格的归一化互信息；这些只辅助描述，不作为选择优劣的分数。前缀和的数组索引不代表它只依赖那个地方，不能把图上的代表点当成完整物理作用范围。',
    '## 全局约束单列',
    '全局清单按源码语义确定，不根据划分结果反推：制造单位总台数、协议核心总数、供电桩总数和亏额预算、运输格合计、面积账、机型总收出量等。仓库取货口模式选择及少量只涉及 P/J 的总账也单列，尽管它们的变量数较少。局部逐格占用行即使有数百个候选变量也保留。每条全局行的编号、变量数、变量类别、代表点范围、源码位置见对应 JSON。']
    for name in TITLES:
        rows=load(OUT/'models'/name/'global_constraints.json');group=collections.defaultdict(list)
        for r in rows:group[r['source']['category']].append(r['variables'])
        parts += [f"### {TITLES[name]}：{len(rows)} 条",table(['全局行含义','条数','每条引用变量数（最小…最大）'],[[cat,len(v),f'{min(v)}…{max(v)}'] for cat,v in group.items()]),f"[逐条原始清单](models/{name}/global_constraints.json)。"]
    parts += ['## 数字总表','每行可点击进入该结果的中文明细，那里列出 S 全部类别及方向、L 全部类别、每个剩余组的含义和两句条件说明。`地/类/混/单` 分别表示地域、类别、混合、只剩一个非空组；箭头前后分别是取 S 前与取 S 后。实际分量一列为“数量；最大/最小”。']
    for name in TITLES:
        for scope in ('whole','window'):
            ds=[d for d in result if d['model']==name and d['scope']==scope]
            if not ds:continue
            parts.append(f"### {TITLES[name]} · {'全场' if scope=='whole' else '14×14 变量窗口'}")
            ds.sort(key=lambda d:({'metis':0,'kahypar':1,'manual':2}[d['algorithm']],d['mode']!='full',d['k']))
            parts.append(table(['方法 / 全局行口径 / k','变量 / 保留约束','S','L','C','剩余最小…最大组','实际分量：数；最大/最小','分组含义'],[[f"[{ALGO[d['algorithm']]} / {MODES[d['mode']]} / {d['k']}](明细/{ident(d)}.md)",f"{fmt(d['variables'])} / {fmt(d['active_constraints'])}",fmt(d['separator_variables']),fmt(d['linking_constraints']),fmt(d['raw_cut_constraints']),f"{fmt(d['remaining_min_block'])}…{fmt(d['remaining_max_block'])}",f"{fmt(d['actual_connected_components'])}；{fmt(d['actual_largest_component'])}/{fmt(d['actual_smallest_component'])}",short(d['raw_partition_signature']['label'])+'→'+short(d['remaining_partition_signature']['label'])] for d in ds]))
    parts+=['## 结构例子']
    examples=[('flow_all_window__metis_full_k4','全体流量窗口：按机型、端口与收出量类别分'),('flow_all_whole__metis_noglobal_k2','全体流量全场：拿开全局行后按地域分'),('geometry_whole__metis_full_k4','纯几何全场：辅助量与空间变量分组'),('residual75_whole__metis_full_k4','第 75 轮全域：供电相关量与占格量分组')]
    for key,title in examples:
        if key not in lookup:continue
        d=lookup[key];parts.extend([f'### {title}',explanation(d),f"数字：S={fmt(d['separator_variables'])}，L={fmt(d['linking_constraints'])}；剩余各组为 "+'、'.join(map(fmt,d['remaining_block_sizes']))+f" 个变量。[完整明细](明细/{key}.md)。"])
        if (OUT/'figures'/f'{key}.png').exists():parts.append(f"![{title}](figures/{key}.png)")
    parts+=['## 复查、限制与文件',
    '所有构建导出的 CpModelProto 都通过 `validate()`，这只检查编码合法性。`verify_outputs.py` 另从原始 protobuf 逐行重新提取实际约束引用，不复用提取函数，核对 signed literal、窗口引用、每组 S/L 全量编号与固定 S 后的跨组行数。METIS 的切边数、KaHyPar 的切超边数和 km1 也从原始输入重新计算。检查结果见 [verification.json](verification.json)。',
    'GCG 未运行：环境没有 GCG/SCIP；PyGCGOpt 没有适用的二进制 wheel，源码安装又因缺少 `scip/type_retcode.h` 失败。两次安装尝试均在 15 分钟限额内停止，日志见 [二进制安装](logs/gcg_install.log)、[源码安装](logs/gcg_source_install.log)。',
    '全体流量完整超图的 k=4 标准配置、k=4 eco 配置和 k=8 eco 配置均达到 360 秒未结束。随后 k=4、8 的 FM 配置分别在约 342 秒完成，完整超图未缩小。原始超时日志保留在 `logs/`；超时不表示不存在分隔。',
    '- `models/<模型>/model.pb`：原始构建模型；`metadata.json`：参数、规模、输入散列；`variables.json`：全部变量名、含义和代表点；`incidence.npz`：精确超边引用。\n- `raw/<模型>_<范围>/input.npz`：划分用的引用、原编号映射、全局行掩码；`partitions/*.json`：工具原始分组；`analyses/*.json`：完整 S/L 编号、分类及检查结果。\n- `raw/*/graph_*.npz`：实际用于 METIS 的去重普通图；配套 JSON 记录边数。\n- [全部结果索引](result_index.json)、[依赖版本](requirements.txt)、[环境与工具状态](environment.json)、[原建模源码及输入快照](source_snapshot/manifest.json)、[证据文件散列](manifest.json)。\n- `scripts/build_extract.py`、`prepare.py`、`partition_run.py`、`analyze.py`、`verify_outputs.py`、`write_report.py`：构建、分类、工具执行、分隔核验、报告生成。构建脚本禁用字节码并拦截输出目录外写入；它把 CpSolver.solve 替换成报错函数。',
    '复查已有结果（不建模、不划分、不求解）：\n\n```bash\nPYTHONDONTWRITEBYTECODE=1 求解器/结构检测/2026-09-25/.venv/bin/python -B 求解器/结构检测/2026-09-25/scripts/verify_outputs.py\n```',
    '本次未改任何已有建模文件，未操作模拟器，未执行 git 命令。依赖、编译临时文件、缓存、日志和交付物均放在本目录。']
    (OUT/'报告.md').write_text('\n\n'.join(parts)+'\n')
    index=[{k:d[k] for k in ('dataset','model','scope','algorithm','mode','k','variables','constraints','active_constraints','separator_variables','linking_constraints','raw_cut_constraints','remaining_block_sizes','actual_connected_components','actual_largest_component','actual_smallest_component','raw_partition_signature','remaining_partition_signature')}|dict(detail=f'明细/{ident(d)}.md',raw=f"raw/{d['dataset']}/analyses/{d['algorithm']}_{d['mode']}_k{d['k']}.json") for d in result]
    dump(OUT/'result_index.json',index)
    versions={pkg:importlib.metadata.version(pkg) for pkg in ('ortools','pymetis','kahypar','numpy','scipy','protobuf','psutil','matplotlib')}
    dump(OUT/'environment.json',dict(python=platform.python_version(),platform=platform.platform(),versions=versions,seed=20260925,epsilon=.03,solver_invocations=0,model_count=4,result_count=len(result),gcg=dict(status='not_installed_not_run',binary_wheel='unavailable',source_build='missing scip/type_retcode.h',installation_attempts_within_minutes=15),global_classification='fixed source semantic categories',normal_graph='exact boolean clique expansion',subregion=[16,16,30,30]))
    print(json.dumps(dict(results=len(result),report=str(OUT/'报告.md')),ensure_ascii=False))

if __name__=='__main__':main()
