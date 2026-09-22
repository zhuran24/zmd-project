"""任务书7规格汇入；只写顶层规格，来源稿保持原字节。"""
from pathlib import Path
import json, re, hashlib
from collections import Counter

ROOT = Path('/home/zhuran24/zmd-research-fresh')
SPEC = ROOT / '求解器/规格'
TASK = ROOT / '求解器/会议成果/任务书7执行'
EVIDENCE = TASK / '证据/规格/汇入'
DOCS = ['运行语义.md', '选择点清单.md', '选择点参数轴.md', '受限模型声明.md',
        '受限转移定义.md', '内核输入.md', '内核输出.md', '四件前置义务对照.md', '参数扫描约减.md']
original = {n: (SPEC/n).read_text() for n in DOCS}
docs = dict(original)
rule_hash = hashlib.sha256((ROOT/'《明日方舟：终末地》游戏规则.txt').read_bytes()).hexdigest()
assert rule_hash == 'd150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a'

def section(text, start, end, value):
    a = text.index(start)
    b = text.index(end, a) if end else len(text)
    return text[:a] + value.rstrip() + '\n\n' + text[b:]

for n in DOCS:
    docs[n] = docs[n].replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', rule_hash).replace('31ced2a24fef', rule_hash[:12])
    docs[n] = docs[n].replace('状态：任务书7任务1规则回填；已定规则与工程支持范围分开登记，完整语义与全称认证仍待后续推导、实现和复核。',
        '状态：任务书7任务2、6规格汇入完成。已定规则、带前件的证明接口和工程停止分别登记；新增条件证明待独立复核，Rust实现与运行验收由任务8承接。')

config_path = SPEC/'内核配置-v1.json'
config = json.loads(config_path.read_text())
config['revision'] = 'task7-merge-2026-09-21'
axes = config['axes']

def axis(name, **fields):
    axes[name].update(fields)

axis('judgment.order_scope', disposition='已定', value='fixed_run_order', lifetime='F',
     meaning='判定比较规则整场固定，贯穿各时刻、失败重试和离线接续；global模板扫描是其一种工程表示',
     coverage_loss='固定性已定；重复实例嵌入和全部固定排序的覆盖仍须证明',
     extension_gate='任务8拒绝运行中改写排序；重复实例嵌入按具体支持域复核', basis='任务L15；约束L3、L10；任务6 SP-02/PA-08')
axis('judgment.order', lifetime='F', meaning='输入给整场固定的事件身份、比较序和重复实例嵌入；本配置以global/event-order-v1表达',
     coverage_loss='其它合法固定排序及重复实例嵌入待覆盖；per_instant改变相对序仅作诊断', basis='规则L25；任务L15；约束L10；任务6 SP-02')
axis('transfer.failure_cooldown', disposition='已定', value='every_attempt', lifetime='F',
     meaning='空箱、全拒收、部分送出、全部送出每次尝试均开始箱级5 tick冷却',
     coverage_loss='零传输冷却事实已定；断电恢复和部分扣格后态另核',
     extension_gate='任务8检查空箱及全拒收均起5 tick冷却', basis='规则L25、L36；主会话三审§6；任务6 SP-01')
axis('damping.no_terminal', meaning='仅在非运输取货侧有两个以上非空级需比较阻尼而所选路径无终点时停止；零级/单级按规则短路',
     coverage_loss='多级所需无终点数值及完整分支历史未覆盖；逐单位零级/单级消去见PA-01',
     extension_gate='先核全部实际通道和级数；需阻尼比较时给有据数值或完整覆盖证明', basis='规则L27、L30—31；任务6 SP-03/PA-01')
axis('warehouse.acceptance', disposition='已定', value='receivable_products', lifetime='F',
     meaning='环境前提为仓库收得下成品；供电、路径、端口与冷却随生产状态另核',
     coverage_loss='实际接收检查和接收恢复后的状态集合须逐证书覆盖',
     extension_gate='核核心候选、最高可动级、授权和无线实际接收的完整区间', basis='任务L2、L9；规则L36；任务2§6.5.1；三审§6')
axis('warehouse.acceptance_quantifier', disposition='已定', value='all_candidate_and_actual_checks', lifetime='F',
     meaning='证书声明区间内两成品的所有候选及实际入库检查均满足接收响应',
     coverage_loss='端点容量报告只作观测；中断后的恢复状态覆盖另附证明',
     extension_gate='逐事件或不变量证明整个区间，恢复后重核支持集合', basis='任务L2、L9—10；任务2§6.5.1、§6.5.6')
axis('warehouse.periodic_lift',
     value={'policy':'stop','trigger':'请求缺少逐项复原证据的完整基地周期或缺少覆盖证明的全称认证'},
     meaning='正式循环到生产投影按受限转移§6.5核前件；反向完整周期须复原真实仓库、外部过程及全部有效状态',
     coverage_loss='一般拿取/矿库存复原、恢复后状态覆盖及全部起点和固定参数覆盖仍待具体证明',
     extension_gate='提供§6.5.5逐项证据与独立复核；任务8实现证书新契约',
     basis='任务L2、L7—10、L13；规则L14；任务2§6.5；任务6 SP-11')
offline_fields = {
    'inventory_effect':'全部物品种类、数量和年龄', 'progress_effect':'批次、剩余制造时长和箱冷却',
    'direction_effect':'已建桥的端口方向', 'gate_total_effect':'真实累计已收数',
    'gate_window_effect':'当前窗口计数', 'gate_window_start_effect':'窗口起点或idle标记',
}
for short, value in offline_fields.items():
    axis('offline.'+short, meaning=f'纯接通重排为零耗时关系，保持{value}；正时长演化单列。本配置尚未实现离线回放时返回unsupported',
         coverage_loss='保持关系已按任务6 PA-08给出；一般指针接续、可达排列族及实现仍待完成',
         extension_gate='实现纯重排保持关系，独立核环/级重算和指针接续', basis='任务L14；规则L20、L23、L28—32、L36、L63—64；任务6 SP-07')
axis('offline.cursor_effect', meaning='指针记录通道身份；纯重排后须给新环上的接续关系，完整关系未实现则unsupported',
     coverage_loss='一般指针接续和精确可达排列族缺推导；扩大到所有候选成员只用于充分方向', basis='任务L14；规则L29—32；任务6 PA-08/PC-04')
axis('initialization.other_inventory', meaning='完整StateSeed及任务5§3.1程序的可达谓词、可靠包络；准备截面与串行释放后态分别表示',
     coverage_loss='exact_reachable_set_enumerated=false；关闭时intake与任务5空缓存后态须联合核，串行释放后保留全部相对进度',
     extension_gate='核专线、单配方、无R89回转/非成品外流前件及全部有限迟延；任务5/6 PC-06接口', basis='规则L18、L20、L35；任务L12—13；任务6 SP-05')
axis('time.retry_schedule', meaning='固定规则下反复重试被源货、目标空位、物种、批次、门原因和级变化唤醒的候选；ordered_sweeps为受限工程实现',
     coverage_loss='一般双端调度和失败环真实唤醒接续未证；直接链工作表闭包见PA-10', basis='规则L24—25、L29—30；任务6 SP-09')
axis('time.instant_end', meaning='完整失败控制状态重复可定义受限工程函数的截断；真实时间唤醒出口须另证',
     coverage_loss='函数终止与确定输出的条件证明；一般真实唤醒对应未证', basis='规则L24、L29；任务6 SP-09/PC-06')
axis('warehouse.withdrawal_policy', meaning='普通有限执行尚不回放玩家拿取；§6.5环境证明可采用满足接收前提的合法拿取过程，具体完整周期须补程序及复原证据',
     coverage_loss='具体拿取程序、非精确操作后果和完整周期回放未实现', basis='任务L8—10、L13；受限转移§6.5')
config['axis_count'] = len(axes)
counts = dict(Counter(v['disposition'] for v in axes.values()))

# 同一字段在轴表、模型声明和输入镜像中只登记一次。
axis_text = docs['选择点参数轴.md']
axis_rows = {}
for line in axis_text.splitlines():
    m = re.match(r'\| `([^`]+)` \| ([^|]+) \| ([^|]+) \| (.*) \|$', line)
    if m and m[1] in axes:
        axis_rows[m[1]] = [m[2].strip(),m[3].strip(),m[4]]
assert len(axis_rows)==99
changed_axes = [k for k,v in axes.items() if v != json.loads(config_path.read_text())['axes'][k]]
for k in changed_axes:
    v=axes[k]
    state = 'known' if v['disposition']=='已定' else ('obligation' if k=='warehouse.periodic_lift' else '输入/工程接口')
    detail = f"{state}：{json.dumps(v['value'],ensure_ascii=False)}；{v['meaning']}。范围：{v['coverage_loss']}。据：{v['basis']}"
    axis_rows[k] = [v['choice'],v['lifetime'],detail]
    axis_text = re.sub(r'^\| `'+re.escape(k)+r'` \|.*$', lambda m:f"| `{k}` | {v['choice']} | {v['lifetime']} | {detail} |",axis_text,flags=re.M)
axis_text = re.sub(r'生命周期列：.*', '生命周期列：`F`＝整场固定；`O`＝离线后可变；`U`＝运行规律或固定性仍须按所列前件核查。判定次序的机制固定性已定，输入排序全程保持；状态字段的U标签只登记演化义务。纯离线重排的保持量已写入对应行，工具尚未回放时仍保留工程停止。据：任务L14—15；任务6 PA-08。', axis_text)
axis_text = re.sub(r'^\| A3 \|.*$', '| A3 | T2 judgment.order_scope/order；T10 | 整场固定判定规则；时间函数改序只作史料/诊断。任务L15，任务6 SP-02。 |',axis_text,flags=re.M)
docs['选择点参数轴.md']=axis_text
model=docs['受限模型声明.md']
for k in changed_axes:
    v=axes[k]
    row=f"| `{k}` | {v['disposition']} | `{json.dumps(v['value'],ensure_ascii=False,separators=(',',':'))}`：{v['meaning']} | 据：{v['basis']} | {v['coverage_loss']} | {v['extension_gate']} |"
    model=re.sub(r'^\| `'+re.escape(k)+r'` \|.*$',lambda m:row,model,flags=re.M)
model=model.replace('当前报告生产部分周期及其适用域；生产投影到正式基地循环的对应是独立证明义务，任务2有效替换稿待汇入§6.5。旧级二名目撤下。','生产周期默认报告实际种子、固定参数、接收域和率。正式完整循环的前向投影与反向复原分别按受限转移§6.5验收，全部可达循环覆盖另附证明。任务6条件证明的独立复核状态为pending。')
model=model.replace('§5保留旧算法的条件证明作史料，当前只核所声明支持域和实际执行范围。','§5列工程函数与真实唤醒的边界；一般失败环接续仍待证明。')
model += '\n## 5. 当前停止项与依据\n\n停止项按[四件前置义务对照§6](四件前置义务对照.md)逐项登记。零传输冷却已定为every_attempt；纯重排保持关系已有条件推导；工程尚未支持的回放仍返回unsupported。需阻尼比较的多级无终点、部分传输跨格扣减、指针接续、完整循环复原和有限化分别保留具体义务。\n\n当前99轴处置计数：'+ '、'.join(f'{k}{v}项' for k,v in counts.items())+'。该计数只描述配置登记。\n'
docs['受限模型声明.md']=model
inp=docs['内核输入.md']
for k,(choice,life,detail) in axis_rows.items():
    bucket='fixed' if life.startswith('F') else ('offline_mutable' if life.startswith('O') else 'fixedness_unproven')
    inp=re.sub(r'^\| `'+re.escape(k)+r'` \|.*$',lambda m:f'| `{k}` | `{bucket}`；{life} | {choice}；{detail} |',inp,flags=re.M)
inp=re.sub(r'[^\n]*F\(global\)/U\(per_instant\)[^\n]*', '判定作用域与判定排序均放fixed；固定规则贯穿全部时刻和离线接续。其它生命周期按逐轴表映射。',inp)
inp=section(inp,'### 3.3 离线及接续','## 4.', '''### 3.3 离线及接续

一次纯接通重排是零耗时环境关系，前后保持几何、设定、供电、已建桥定向、库存物种/数量/年龄、批次及剩余时长、箱冷却、准入口累计和当前窗、固定判定规则。正时长离线段另记物料与计时事件，按规则L20、L23、L35—36、L64推进。依据任务L14及任务6 PA-08。

重排后按规则L29、L31—32更新环序、级内最早接通、级排序和最高可移动级；保存指针的通道身份。精确可达排列族、并列关联和指针接续关系仍须提交证明（PC-04）；工具未实现时返回unsupported。扩大到全部候选指针成员的探索须声明充分方向，低产路径另核真实可达性。
''')
start=inp.index('### 5.2 判定排序规则 EventOrder')
anchor=inp.index('judgment_context', start)
# 保留完整中途种子/continuation编码，从其所在段落开始。
para=inp.rfind('\n\n',start,anchor)
inp=inp[:start]+'''### 5.2 判定排序规则 EventOrder

`judgment.order_scope=fixed_run_order`、`judgment.order`均为F。事件身份、比较序和重复实例嵌入整场固定，含各时刻、失败重试和离线接续；依据任务L15、约束L10。`event-order-v1`的封闭对象为`{schema,scope,template_order,repeat_embedding,instant_overrides}`，其中scope=global、instant_overrides=[]；template_order恰覆盖全部几何可能PC的move、制造单位manufacture及箱transfer。BC按所选事件归类保留内部动作，完成事件仍为非判定事件（规则L18、L25、L35）。

`repeat_embedding=scan_round_then_template`使用固定模板序，实例按(instant,round,template_index)登记。新启用模板已越过时须在后续轮重新尝试；源货、目标空位、门原因或级变化都重新激活相关候选。该表示是工程日程，完整失败环到未来唤醒的出口按受限转移§5另证。

旧event-order-v2/v3的per_instant时间函数改序编码保留在历史记录中。当前游戏证书准入拒绝改变相对判定序的时间函数；扩大探索所得坏路径须还原同一固定规则，才可作真实反例。其它固定排序表示需新版本和重复实例保持证明。

'''+inp[para:].lstrip()
inp=inp.replace('默认程序的后置状态集合及释放过程缺任务5证明', '默认程序后态按任务5§3.1的条件可达谓词及可靠包络输入，精确集合未枚举')
inp=inp.replace('状态集合与释放后果缺任务5推导', '状态集合的条件包络见任务5，联合释放后果继续核查')
inp=inp.replace('不允许在种子参数中切换新排序', '固定判定规则在种子及后续回放中保持')
inp += '''
## 10. 默认后态与状态投影准入

默认后态采用[调试与释放§3.1](../会议成果/任务书7执行/调试与释放.md)的程序、实际接线和全部有限操作迟延。专线、单配方、无规则L89回转、无非成品外流等条件满足且充分等待时，准备截面无在制批次，非末级缓存为空或一批完成，六末级清空后一直关闭的缓存为空。串行开启末级后保存全部空/在制/完成阶段、运输成熟、窗口及相对进度。`exact_reachable_set_enumerated=false`；范围箱的笛卡尔积只作覆盖包络。（任务6 SP-05、PC-06；任务L12—13。）

受限制造接口在关闭时仍可先入料形成intake；使用该接口的输入将intake及扣料量纳入后态包络并重算释放账。采用任务5空缓存后态的证书须先证明接口满足其程序条件。任务5指定条件结论已有一次独立否证，任务6新增状态删减的独立复核为pending。

完整StateSeed用于恢复和审计。`phase-cycle-key-v1`只在受限转移§6.1准入和§6.2逐字段读取前件核查后生成：成熟运输年龄截断、无读取的非运输时标删除、固定C时累计数饱和、时间原点平移；真实累计n仍保存供调试改阈值。门窗表示idle或active(j,w)，到期未维护的阶段另存。中途状态保留continuation、端口额度及已办事件。零干预后固定参数按完整内容绑定；hash仅作索引。（规则L20、L23、L29、L36、L64；任务6 SP-06/08。）
'''
docs['内核输入.md']=inp

# 其余正文由同目录的merge_bodies.py接续；此脚本只提交共享轴和镜像。
for n in ['选择点参数轴.md','受限模型声明.md','内核输入.md']:
    (SPEC/n).write_text(docs[n])
config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
(EVIDENCE/'axis-changes.json').write_text(json.dumps({'changed_axes':changed_axes,'axis_count':len(axes),'dispositions':counts,'implementation_status':'task8_pending'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'changed_specs':4,'axis_count':len(axes),'changed_axes':len(changed_axes),'dispositions':counts},ensure_ascii=False))
