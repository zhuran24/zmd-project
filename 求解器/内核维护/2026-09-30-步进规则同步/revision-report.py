"""从已完成回执整理修订处置与追加记录，不改历史段落。"""
import json,re
from guard import OUT,ROOT,guard,digest,save

def read(name):return json.loads((OUT/name).read_text())
commands=[json.loads(l) for l in (OUT/'commands.jsonl').read_text().splitlines() if json.loads(l)['name'].startswith('revision-')]
final=[c for c in commands if c['name'].startswith('revision-final2-')]
assert len(final)==11 and all(c['exit_code']==0 and not any(c['active_diff'].values()) for c in final)
assert 'warning:' not in (OUT/'revision-final2-clippy.log').read_text()
suite=read('差分/revision-differential-final.json');diag=read('差分/revision-diagnose-final.json')
assert len(suite['cases'])==96 and sum(c['steps'] for c in suite['cases'])==33484 and not suite['errors']
assert len(suite['mismatches'])==2
assert {c['name'] for c in suite['mismatches']}=={c['name'] for c in diag['findings']}
assert diag['required_cases']==72 and diag['required_steps']==31200
assert all(c['projection_poll_gate_layers_equal'] for c in diag['coverage'])
assert all(c['diagnostic_fix']['all_projection_poll_and_gate_equal'] for c in diag['findings'])
assert read('revision-audit02.json')['status']=='pass'
config=digest(ROOT/'规格/内核配置-v2.json');catalog=digest(ROOT/'数据/正式静态目录.json')
guard('revision-report-before')
report='''# 步进规则同步：修订处置

日期：2026-09-30。状态：审查五项发现已处置，现行内核、规格与30份输入已同步；安全集通过，差分没有未定位分歧。本文件针对[审查](审查.md)的五项发现及[差分](差分.md)的两处参照侧问题，不替代独立终审。

## 1. 审查逐项处置

| 发现 | 判定与最终处置 | 实现、规格及验证 |
|---|---|---|
| 1 接通并列序与逐个建成不相容 | 成立。保留输入全排列；同一步内，通道在 connection.tie 中的 cause 建造位次必须不递减，否则返回 invalid_input，axis=connection.tie。同一次建成引起的数条通道可任意排序，不同接通步之间不增加 tie 限制。 | [input.rs](../../crates/kernel/src/input.rs)、[step_graph.py](../../数据/工具/step_graph.py)；[内核输入§5.1](../../规格/内核输入.md#51-接通序与层数输入)。Rust 同步不同建成的正例/反向负例、同一次建成两种并列序正例，以及 Python 拒收测试通过。依据规则 L9、L16、L30。 |
| 2 配置旧读法、供电错行号 | 成立。修正 warehouse.acceptance 的旧级/授权措辞、power.cell_rule 的 L76—L77，并同步 other_inventory、external_supply、periodic_lift 三处；保留回矿在容量读取前检查和显式有限历史不认证无限重复的原有边界。connection.tie 的说明同时补足同一步内的建成先后。 | [配置v2](../../规格/内核配置-v2.json)、[受限模型声明](../../规格/受限模型声明.md)、[选择点参数轴](../../规格/选择点参数轴.md)。66轴名、值、处置数不变；30份现行输入重生成并核除配置SHA外对象相等。 |
| 3 整族误报 exercised | 成立。删除全部族前缀取证；12条轴按独立事件判据取证，其余保守记 input_checked / not_exercised / stop_not_triggered / proof_pending。首次轮询从种子游标逐移动更新；singleton 只由分流器送货侧/汇流器收货侧的单通道实际移动触发；partial_acceptance 要求同次 sent、retained 均非空。普通开工只给 recipe_completeness 取证，不为 output_blocked、input_mixing、empty_slot_identity 背书。 | [output.rs](../../crates/kernel/src/output.rs)、[输出规格§3](../../规格/内核输出.md#3-内容核验与轴覆盖)、[设计§5.1](设计.md#51-运行记录与事件)。[tests_output.rs](../../crates/kernel/src/tests_output.rs)核首次/已成功游标、普通循环侧、单/多通道、空箱/全收/全拒/部分接收和普通制造误报。 |
| 4 环与桥轴身份碰撞 | 成立。Rust 建索引前断言身份唯一；碰撞返回 invalid_input，位置为冲突身份。Python 图和生成器也拒绝覆盖已有元件。保留现有身份格式，碰撞输入须换用不冲突的单位id。 | [graph.rs](../../crates/kernel/src/graph.rs)、[step_graph.py](../../数据/工具/step_graph.py)、[step_inputs.py](../../数据/工具/step_inputs.py)；真实四格带环 horizontal/z1/z2/z3 加桥 ring 的负例，在 Rust 和 Python 均被拒绝。 |
| 5a 旧 kernel_regression.py 未标历史 | 成立。将绑定已删除 --no-cache 参数的旧回归入口加入[历史说明](../../数据/样例/历史说明.md)，脚本原字节保持，不运行旧入口。 | 新入口为安全集、reference 与步进工具；审计确认旧脚本未改。 |
| 5b 设计中缓存闸方向倒置 | 成立。[设计§1.10](设计.md#110-制造)正文改为“存货物品格通往缓存格”，与规则 L18、代码及现行运行语义一致。 | 修正设计文字；无需改变已正确的制造转移。 |
| 5c 旧 check_examples.py 来源表 | 采纳审查“保留旧来源”的理由。任务书§2的刷新要求由现行 step_samples.py 的 SOURCE_HASHES 和30份新格式输入承担；旧 check_examples.py 及其旧样例按设计§6.3保留原字节和历史标签，避免给旧语义样例换上新来源背书。 | 三份当前正式源全文/SHA回源通过，旧校验器原字节核等；这不是略过现行来源校验。 |

五项发现无驳回项。覆盖状态的保守降级是审查明确允许的处置，不以新增事件或猜测补足缺少的触发证据。

## 2. 差分逐项处置

最终原始套件见[revision-differential-final.json](差分/revision-differential-final.json)，归因汇总见[revision-diagnose-final.json](差分/revision-diagnose-final.json)。96例、33484步，含必核九类的72组、31200步；后者的状态投影、轮询、门计数、层数和可观察先后均一致。另有两处已定位差异：

| 差异 | 判定与处置 | 当前字节的重跑证据 |
|---|---|---|
| 制造普通格同种唯一性 | 差分结论成立，无需改内核。规则 L13 的缓存例外不允许同一种产物占据两个普通格；内核把完成批留在缓存正确，sim2.flush 漏查存货格占种。sim2 原件保持只读。 | [最小反例](差分/revision-diagnose-final-sim2-普通格同种唯一性.json)；只在 Python 进程内加该守卫，48步的投影、轮询与门计数全部一致。 |
| 单位与元件混淆 | 差分结论成立，无需改内核。规则 L24 禁止回到刚离开的物理单位；同一带段内的不同传送带仍是不同单位。准入口返回带段另一格不构成回头，内核行为正确，sim2 按元件名拒绝过度。 | [最小反例](差分/revision-diagnose-final-sim2-单位与元件混淆.json)；只在 Python 进程内修正该判断，80步的投影、轮询与门计数全部一致。 |

旧差分结果及两个旧反例未覆盖；归因脚本按本次标签另存证据，并记录本次 reference 日志。sim2/simulator.py 的SHA仍为 `08a83262a5ca2651a3dc06b4fed83bc3f6e957379e5eec7b63094788f0d0bac8`。

## 3. 审查其余核对边界

- 同层且身份字典序与接通先后相反的用例已补：C|z 早于 C|a 接通，在同层先触发收货组；汇流器首次按第二条接通的通道收货。Rust 的图顺序和实际判定事件均断言通过。
- 桥轴双出口收货闭包沿用设计的 L31 本版读法；共同域不支持该构型，不能用本次差分声称获得独立全域证明。协议核心送货、纯带环、跨格部分残留也仍在共同域之外；已有相应内核测试或 unsupported 边界保持。
- 可归一化的非规范种子不判为新缺陷：第一步归一化与诊断周期可能延后一拍的既有边界保持；本次未宣称种子可达性或全部周期覆盖。

## 4. 验证、来源与未解决事项

最终安全集为[revision-safe-suite.sh](revision-safe-suite.sh)以参数 `revision-final2` 执行：build/check/clippy通过，Clippy无告警；kernel库73项、reference14项（含九例4000步）、topology库1项、validation30项、两个doc目标各0项、目录回源及9项目录测试通过。逐条命令、首次失败与纠正、哈希回执见[记录·修订](记录.md#修订)。

当前配置SHA：`CONFIG_SHA`；目录SHA：`CATALOG_SHA`。正式规则115行、任务15行及约束77条的锁与覆盖表核等；66轴投影、30输入引用及候选B的16项来源核等。两张覆盖表与目录本轮无需改字节，因为正式源未再次变化。

历史证据三目录的3481个文件（含被忽略文件）在每次测试/差分前后均与原始initial-history.json相同；清单SHA为 `f6f6772a547e5a4bf4396e777f4823bf00e7dea81d7c3a416a9475f75a9d377e`。旧样例、旧fixtures、旧校验器及配置v1保持原字节。没有Git操作，没有运行workspace测试、旧CLI目标或批量证据写入入口。

本轮范围内仍未解决事项：无。上述两处sim2参照侧缺陷已定位并留下反例，参照源码不属于本轮修订对象；共同域和认证边界继续明确保留。
'''.replace('CONFIG_SHA',config).replace('CATALOG_SHA',catalog)
assert not (OUT/'修订处置.md').exists();(OUT/'修订处置.md').write_text(report)
append=f'''\n\n## r30 审查修订（2026-09-30）

同一步内接通全序须与逐个建成一致，元件身份碰撞在建索引前拒绝；轴覆盖改为逐轴事件取证，未辨识的轴保守降级。修正配置五处旧措辞/依据及connection.tie说明，同步66轴投影与30份现行输入；除配置SHA外输入对象不变。配置SHA为 `{config}`，目录及三正式源SHA保持r30原值。新增7项库测试和1项reference测试；安全集通过，差分96例33484步仅保留已定位的两处sim2缺陷。逐项处置、验证日志和边界见[修订处置](REPORT_LINK)。旧版本段落和历史证据不改写。
'''
for rel,link in [('规格/修订记录.md','../内核维护/2026-09-30-步进规则同步/修订处置.md'),('crates/kernel/修订记录.md','../../内核维护/2026-09-30-步进规则同步/修订处置.md')]:
 p=ROOT/rel;s=p.read_text();assert '## r30 审查修订' not in s;p.write_text(s+append.replace('REPORT_LINK',link))
results={'build':'通过','check':'通过','clippy':'通过，无告警','kernel-lib':'73项通过','topology-lib':'1项通过','reference':'14项通过，含九例4000步','validation':'30项通过','kernel-doc':'通过，0项','topology-doc':'通过，0项','catalog':'三正式源回源通过','catalog-tests':'9项通过，单位1173/配方154逐叶变异拒收'}
table='\n'.join(f'| [{c["name"]}]({c["name"]}.log) | `{" ".join(c["argv"])}` | {c["exit_code"]} | {results[c["name"].removeprefix("revision-final2-")]} |' for c in final)
record=f'''\n\n## 修订

### 处置结果

异源审查五项发现全部成立并处置；包含接通并列序约束、元件身份唯一守卫、逐轴覆盖判据、配置/规格/样例重锁与历史入口说明。同层先后与名字序相反的建议用例补入库测试。逐项依据、差分问题与保留边界见[修订处置](修订处置.md)。本节仅记录此次执行，不改包一至包三及审查/差分原文，不冒充独立终审。

配置SHA：`{config}`；目录SHA：`{catalog}`。正式源不变，目录及两张覆盖表已回源核等；现行30份输入仅配置SHA改变，原布局、种子、参数值与场景均保持。生成清单见[revision-samples-final.json](revision-samples-final.json)。旧check_examples.py的历史来源锁保留，现行来源由step_samples.py与正式目录回源验证。

### 最终安全集

完整命令为 `bash 内核维护/2026-09-30-步进规则同步/revision-safe-suite.sh revision-final2`。共享CARGO_TARGET_DIR为求解器/target，默认profile，-j 4，单测试线程。下列11条命令每条由run.sh在执行前后全量哈希比对历史目录，全部退出0，active_diff均为空。

| 日志 | 命令 | 退出码 | 结果 |
|---|---|---:|---|
{table}

新增库测试7项（总数66→73）：不同建成同一步的接通正/负例、同一次建成两种合法tie、环/桥身份碰撞、同层反字典序、三类覆盖误报测试；reference新增Python图/生成器拒收测试（13→14）。原有完整状态/增量记录、周期重放、独立Python账审、schema、迁移与现象断言均保留。

### 差分与归因重跑

最终执行：

```text
python3 -B 内核维护/2026-09-30-步进规则同步/差分/run.py --scratch /home/zhuran24/zmd-research-fresh/求解器/target/revision-differential --label revision-differential-final --mode all
python3 -B 内核维护/2026-09-30-步进规则同步/差分/diagnose.py --scratch /home/zhuran24/zmd-research-fresh/求解器/target/revision-differential --suite /home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-30-步进规则同步/差分/revision-differential-final.json --label revision-diagnose-final --reference-log /home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-30-步进规则同步/revision-final2-reference.log
```

均设置PYTHONDONTWRITEBYTECODE=1；日志为[差分](revision-differential-final.log)、[归因](revision-diagnose-final.log)，结果为[原始套件](差分/revision-differential-final.json)、[归因汇总](差分/revision-diagnose-final.json)。观察器仅链接共享target下已构建的库，二进制留在target/revision-differential，无新增profile、无复制target或registry。

96例共33484步；九个必核构型72组31200步全等，扩展边界仅两处原有sim2分歧，无错误或未定位分歧。按L13与L24分别在Python进程内单点修正后，48步和80步状态、轮询、门计数逐步全等；sim2原件不改。差分与归因每次前后历史差异、被核来源差异均为空。最终原始套件SHA：`{digest(OUT/'差分/revision-differential-final.json')}`。

### 开发期失败与纠正

- [revision-lib01.log](revision-lib01.log)退出101：新增测试少导入serde_json::Value，编译未通过；补导入后的[revision-lib02.log](revision-lib02.log)73项通过。失败回执的历史前后比对相同。
- [revision-reference01.log](revision-reference01.log)14项通过；第一次完整安全集revision-final-*全部通过，日志保留。
- [revision-audit01.json](revision-audit01.json)失败：base fixture用了step_inputs默认核心单体描述，改变了原有纯链布局；审计的“仅SHA变化”断言拒绝。随后从开工保存的单位、建造次序重生成base，并断言除配置SHA外逐字段相等，未降低判据；[revision-audit02.json](revision-audit02.json)通过。修正后再跑本节最终安全集和完整差分，旧结果不充作最终字节的验收。
- 初次差分revision-differential及revision-diagnose也完成96例、两处同样归因，结果保留；最终以带-final标签的结果为准。

### 保护、重锁与交付自审

开工全量历史快照[revision-start-history.json](revision-start-history.json)与包一initial-history.json相同；历史目录合计3481文件、1018807436字节，清单SHA `f6f6772a547e5a4bf4396e777f4823bf00e7dea81d7c3a416a9475f75a9d377e`。每条测试（含编译失败）及两轮差分/归因均有前后快照并核原始基线；不存在用新快照替换原基线的操作。25条run.sh命令及4次差分/归因共58份测试前后快照全相同，另有写入及审计守卫。

原字节备份在revision-before/；修改前后活动清单、全部回执、历史快照索引与文件SHA统一见[revision-summary.json](revision-summary.json)。现行回源审计为revision-audit.py，沿用包三的源文/覆盖表/66轴投影/链接判据，仅将修改允许域限定到本轮文件，并额外核30份输入除配置SHA外不变。无Git操作；未跑workspace测试、七个旧CLI测试、批量证据核验或内核CLI写入。

交付前复读处置、设计相关小节及当前规格：缓存闸方向、接通顺序限制、覆盖状态的证据含义、配置SHA和版本均一致；旧来源锁与旧失败按时点标注；已实现、共同域之外及未证全称分开陈述。最终链接/来源/哈希核验及文件清单以revision-summary.json所列审计为准。本轮范围内未解决事项：无。
'''
p=OUT/'记录.md';assert '\n## 修订\n' not in p.read_text();(OUT/'revision-record-before.md').write_bytes(p.read_bytes());p.write_text(p.read_text()+record)
guard('revision-report-after')
print('disposition and revision records written')
