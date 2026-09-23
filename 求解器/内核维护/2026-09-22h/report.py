from guard import ROOT,REPO,OUT,digest,save,guard,active_snapshot,difference
from helpers import dump
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re,subprocess,shlex
load=lambda p:json.loads(p.read_text())
audit=load(OUT/'audit.json');positive=load(OUT/'positive-validation.json')
commands=[json.loads(l) for l in (OUT/'commands.jsonl').read_text().splitlines()]
assert all(not any(c['active_diff'].values()) for c in commands)
selected=['cargo-build','cargo-check-final','cargo-clippy-final','kernel-lib-final','topology-lib',
    'kernel-reference-final','topology-validation-final','kernel-doc','topology-doc','catalog-verify','catalog-regressions',
    'positive-seed','positive-check','positive-run-delivery','positive-verify-record-delivery','stale-catalog-negative']
table=['| 步骤／日志 | 实际命令（cwd：求解器） | 返回码 | 结果 |','|---|---|---:|---|']
selected_rows=[];rust_passed=0;python_passed=0
for name in selected:
    c=next(r for r in commands if r['name']==name);log=(OUT/(name+'.log')).read_text()
    assert c['exit_code']==(2 if name=='stale-catalog-negative' else 0),(name,c)
    count=re.search(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored',log)
    result='通过'
    if count:
        c={**c,'passed':int(count[1]),'failed':int(count[2]),'ignored':int(count[3])}
        rust_passed+=c['passed'];result=f"{c['passed']} 通过，0 失败"
    if name=='catalog-regressions':
        python_passed=int(re.search(r'Ran (\d+) tests',log)[1]);result=f'{python_passed} 项通过'
    if name=='stale-catalog-negative':result='预期拒收：invalid_input；源文件指纹不符'
    argv=[p.replace(str(ROOT)+'/', '') for p in c['argv']]
    table.append(f"| [{name}]({name}.log) | `{shlex.join(argv)}` | {c['exit_code']} | {result} |")
    selected_rows.append(c)
assert rust_passed==142 and python_passed==8
history=guard('delivery')
diff=load(OUT/'delivery-history-diff.json');assert not any(diff.values())
comparisons=sorted(p.name for p in OUT.glob('*-history-diff.json'))
assert all(not any(load(OUT/p).values()) for p in comparisons)
changes=difference(load(OUT/'initial-active.json'),active_snapshot())
files=sorted(changes['changed']+changes['added'])
extra='求解器/crates/kernel/周期键读取审计.md'
if extra not in files:files.append(extra);files.sort()
rows=[{'path':p,'sha256':digest(REPO/p),'before_sha256':load(OUT/'initial-active.json').get(p)} for p in files]
save('changed-files.json',rows)
(OUT/'business.patch').write_bytes(subprocess.check_output(['git','diff','--',*files],cwd=REPO))
(OUT/'new-unit-tests.rs').write_bytes((ROOT/'crates/kernel/src/tests_bridge.rs').read_bytes())
(OUT/'final-status.txt').write_bytes(subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=normal'],cwd=REPO))
timestamp=datetime.now(ZoneInfo('America/New_York')).isoformat()
summary={'status':'pass','cutoff':timestamp,'head':(OUT/'initial-head.txt').read_text().strip(),
    'catalog_version':audit['catalog_version'],'catalog_sha256':audit['catalog_sha256'],'constraints':72,
    'business_files':len(files),'new_unit_tests':8,'rust_passed':142,'rust_failed':0,'python_cases':8,
    'relocked_inputs':54,'sample_inputs':45,'fixture_inputs':9,'bridge_inputs':12,'reference_documents':56,'reference_fields':114,
    'candidate_sources':16,'history_files':sum(history['counts'].values()),'history_counts':history['counts'],
    'history_bytes':sum(r['bytes'] for r in history['files'].values()),'history_ignored':len(load(OUT/'ignored-history-files.json')),
    'history_diff':diff,'recorded_comparison_files':len(comparisons),'latest_commands':selected_rows,
    'earlier_failed_commands':[c['name'] for c in commands if c['exit_code'] and c['name']!='stale-catalog-negative'],
    'unresolved_test_failures':[],'mismatches':[],'out_of_scope_issues':['T12旧断言','两处既有实现状态文字'],
    'record':str(OUT/'记录.md')}
save('summary.json',summary)
filetable=['# 本轮业务文件清单','',f'执行记录；截止 {timestamp}。共 {len(files)} 个新增／修改文件，未暂存、未提交。','',
    '| 文件 | 作用 |','|---|---|']
for p in files:
    rel=p.removeprefix('求解器/')
    if rel.startswith(('数据/样例/','crates/kernel/tests/fixtures/')) and rel.endswith('.json'):
        why='目录／参数源重锁；桥配置生命周期和状态按轴迁移，非相关字段审计相等'
    elif rel.startswith('crates/kernel/src/'):
        why='桥运行语义、状态编码、调度、来路守卫或库内回归'
    elif rel.endswith('/reference.rs'):
        why='旧参考记录的五条失效配置声明只在测试内存中迁移，轨迹仍严格比较'
    elif rel.endswith('/validation.rs'):
        why='桥双向端口数、永久端口型和每轴容量的独立断言'
    elif rel.startswith('规格/') or rel.endswith('周期键读取审计.md'):
        why='现行语义、接口、配置、来源或修订记录同步'
    else:why='正式目录投影、覆盖／来源清单或 Python 桥几何与参考接口同步'
    filetable.append(f'| [{rel}](../../{rel}) | {why} |')
(OUT/'changed-files.md').write_text('\n'.join(filetable)+'\n')
formal_table='\n'.join(f'| {name} | `{sha}` |' for name,sha in audit['protected_files'].items() if name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt'])
history_table='\n'.join(f'| {name} | {count} |' for name,count in history['counts'].items())
record=f'''# 桥接器现行规则同步与安全核验记录

史料／执行记录。日期：2026-09-22；截止：{timestamp}。开工 HEAD：`{summary['head']}`。状态：同步完成；指定安全集通过；历史证据零变化；未暂存、未提交。本文记录有限机制核验，不构成目标循环或全部游戏运行的证明。

## 结论和数目

正式规则提交 `743f18b` 的 L24、L59、L63 已同步到现行规格、目录、内核配置与实现。桥四边一直双向；相邻桥形成两个方向的 PC；物品不移回刚离开的单位；每对平行边独立存货分级、存取轮询、容量和滞留，每格上限1。

共 **{len(files)} 个业务文件**新增／修改；新增 **8 项库内单元测试**。安全 Rust 测试 **142 通过、0 失败**，Python 目录回归 **8 项通过**。目录仍含 **72 条约束**；重锁 **54 份输入（45 样例、9 fixture）**，其中 **12 份含桥**；核验 **56 份输入／参数赋值、114 个引用字段**和候选 B **16 项来源**。本轮同步不一致 **0 项**，未解决测试失败 **0 项**。

目录版本 `{audit['catalog_version']}`，SHA-256：`{audit['catalog_sha256']}`。

机器汇总见 [summary.json](summary.json)，逐项引用和非相关字段审计见 [audit.json](audit.json)，业务文件清单见 [changed-files.md](changed-files.md)，已跟踪文件补丁见 [business.patch](business.patch)。新增 Rust 测试原件为 [tests_bridge.rs](../../crates/kernel/src/tests_bridge.rs)，记录副本见 [new-unit-tests.rs](new-unit-tests.rs)；未跟踪文件不会混称已包含在 git diff 补丁里。

## 规格与实现

运行语义、T5/T14 选择点、参数轴、内核输入、受限转移、受限模型声明、两张规则覆盖表、四件前置义务、参数扫描的保守依赖说明、输出 schema 和周期键读取审计已同步。修订记录尾部追加 r25；旧修订节、旧评审／验证快照均作为史料保留。

配置 revision 为 `bridge-bidirectional-2026-09-22`。`bridge.scheduling_scope=per_axis`、`bridge.capacity=1` 已定；旧先接与桥并列接口保留名字，值均为 `not_applicable`，生命周期 F。配置共 99 轴：已定25、本版选值42、输入量化15、超出覆盖即停17。离线桥端口始终双向，一般离线回放仍在原工程停止域内。

| 部位 | 当前行为 |
|---|---|
| 正式目录与几何 | `formal_units.py` 投影四个 bidirectional 物理口，存取能力各4；单一永久端口型，桥两格各容量1。`bridge_axes=null`，显式拒收旧定向对象。 |
| 相邻桥 | `catalog.rs` 在相邻兼容端口间生成两个相反方向 PC，空桥也形成；两方向复用物理口预算。`input.rs` 取消先接定向和桥互依赖停止。 |
| 移动与来路 | `Content.last_unit` 随成功移入桥写源单位；离开／清格随物品移除，时间推进保持。装载核它是本轴真实邻接来路；`compute_physical` 在容量和授权之前拒绝立即返回。其它单位的单向几何本已排除退回。 |
| 分级与轮询 | 调度索引为 `(unit,side,axis)`，桥四条侧记录；级标签含本地轴。`group_levels`、缓存失效、授权、游标和图重建均按对应轴寻址。整单位缓存失效仍保守，未扩张参数扫描的约减域。 |
| 路径与持久化 | 阻尼和相关分支搜索同轴穿过桥并排除入口反向边；完整状态、闭包键、生产循环键保留来路，循环规范排序包含轴。Content 和 CycleKey schema 都允许 last_unit。 |
| Python 接口 | 几何与轮询参考改为双向、逐轴；生成器不再产生先接方向。`runtime_example.py` 排除桥轴对象误判为 Decision，按桥轴选择库存及检查来路。它仍是原有受限参考接口，不因此宣称支持全部 Python 运行场景。 |

## 新增单元测试

全部位于 `kernel/src/tests_bridge.rs`，通过 `cargo test -p kernel --lib` 执行；不依赖七个 CLI 测试目标。

| 测试 | 核验内容 |
|---|---|
| bridge_axis_straight_through | 一对边进料后同轴穿过，保留1 tick滞留，不串另一轴 |
| bridge_two_inward_belts_both_connect_and_trap_one_item | 两端向内送料均接通；格满后物品留桥，另一件在上游，物料守恒 |
| adjacent_empty_bridges_form_both_directions_for_all_rotations | 两座无其它邻接的桥即有两个方向，覆盖相邻桥四朝向 |
| adjacent_bridge_item_never_returns_after_checkpoint | 两个来路方向均前进后不退回；跨旋转轴寻址、检查点恢复后仍阻止退回 |
| adjacent_bridges_pass_forward_and_damping_ignores_reverse_edge | 桥串继续向前；阻尼走对边，悬空末端按无终点报告，反向边不误作多出口 |
| direct_splitter_on_one_bridge_axis_does_not_block_other_axis | 一轴直连分流器，四条调度侧独立，另一轴同时收发不受其分级和轮询影响 |
| bridge_capacity_and_legacy_direction_are_rejected | 每轴拒绝2件；同种双轴允许；旧定向声明拒收 |
| bridge_previous_unit_is_preserved_in_cycle_key_and_validated | 不同来路生成不同生产键；非本轴邻接的来路拒收 |

## 正式重锁与引用

| 正式来源 | SHA-256 |
|---|---|
{formal_table}

通过 `formal_catalog.py` 的 `source_snapshot/formal_projection/recipe_projection/unit_projection/verify` 回源重建，独立再次重建与落盘字节相等。相对 r24：规则来源只改变 L24/L59/L63 和规则 SHA；单位对象仅桥接器改变；配方、任务、72条约束、静态常量及物料流量逐对象不变。版本及桥的端口型、端口能力数、容量状态、说明同步。

54份活动输入更新目录和轴表指纹，迁移5个相关配置项及当前参数生命周期；12份含桥输入将旧方向对象置null，桥记忆和仲裁标签按轴拆开。去除这些明确允许字段后，与本轮原字节备份解析对象逐项相等；几何通道、库存初值、配方、设置及其它输入字段不变。两份参数赋值重新核声明／配置／轴表来源。候选B报告只同步目录版本及维护入口，其既有检查计数不冒称本轮重跑。

旧目录 SHA `b573a299c5853dada4189f53b629733f826a535ca011c969c6d658256d9af74c` 的全仓 `rg --hidden --no-ignore` 结果见 [final-old-sha-inventory.json](final-old-sha-inventory.json)。只排除 `.git`、target、Python缓存；余项均为旧维护记录、本轮备份／日志／负例和规格修订历史节，活动输入残留0。

## 安全集实际结果

所有任务脚本均落为文件后经 `bash .../task.sh`、`bash .../run.sh` 或 bash 套件启动。cargo 使用 `-j 4` 和共享 `求解器/target`；六个测试目标均加 `-- --test-threads=1`。完整 argv、环境、耗时、退出码和每条命令前后文件差异见 [commands.jsonl](commands.jsonl)。下表只列最终有效结果；早期失败原日志保留。

{chr(10).join(table)}

Rust计数为108库测试 + 1 topology库测试 + 3参考测试 + 30 validation；两个doc目标各0。Python8项中的单位1174叶、配方154叶及集合变异是子检查，不重复加进用例数。Clippy无警告。最终 build 的二进制 SHA-256 为 `{positive['binary_sha256']}`。

正向链用桥双通路，源箱各4件，6 tick后北箱、东箱各4件；运行记录复验通过，完整输出 schema 使用仓库内无依赖严格验证函数通过。最终记录为 [positive-run-delivery.json](positive/positive-run-delivery.json)。旧SHA负例仅替换catalog.sha256，返回2、invalid_input，明确报目录“源文件指纹不符”，见 [positive-validation.json](positive-validation.json)。前两份正向运行输出保留为执行中间档；最后的delivery记录绑定交付规格/schema。

## 测试失败、判读与修正

| 首次发现 | 判断 | 处置及最终结果 |
|---|---|---|
| 原 config_axes_and_all_stop_values 断言停止轴18 | 旧桥互依赖停止被移除，旧计数失效；执行前已识别 | 改为17；库测试通过 |
| 原 topology目录断言为2存2取、桥容量null、四种定向型 | 旧规则预期；执行前已识别 | 改为四口各具存取能力、两格各1、单一双向型 |
| [topology-validation](topology-validation.log) 1项失败，计数[0,4]而期望[4,4] | 测试辅助计数把所有非input都算output，未识别bidirectional；非内核故障 | 显式三种角色计数，未知角色拒绝；30项通过 |
| [kernel-reference](kernel-reference.log) 3项失败 | 固定历史参考中的bridge.scheduling_scope等声明仍为旧规则，最先差在parameter_values的basis；不是历史目录指纹拒收 | 两个无桥、无离线场景的5条失效配置声明仅在测试内存中迁移，先断言旧值/生命周期，再换当前已校验声明；历史记录不写回，库存、事件、轮询、预算、黄金摘要仍逐字段严格比较；3项及实时Python差分通过 |
| [kernel-lib-bridge](kernel-lib-bridge.log) 新增2项失败 | 测试前提错误：总库存漏算仓库80000；生产键测试未给sufficient且未到after_closure | 守恒改为前后总量比较；显式补齐生产键准入并推进到闭包后；8项新增测试全部通过 |

实现复查另修正了新轴标签对非桥侧带上 `:None` 的无关表示变化：非桥沿用原标签，桥才追加axis，参考差分确认一致。未发现需要保留的实现错误或测试失败。

维护脚本组装过程中出现过可恢复中断：桥记忆派生一度请求了不相关仓库口，随后限定为桥辖域；重复迁移标签的幂等判断与缺失Path导入已补齐。附加schema核验先遇本机未装jsonschema，改用现有严格函数；临时清除description注解时误碰同名属性定义，最终改为直接验证未经投影的完整schema。读者自审纠正了覆盖表不同分节同号行的误匹配，最终114/16源行和72约束映射全部独立通过。以上仅为本轮脚本／测试迭代，不记作现存不一致。

## 历史证据保护和范围

| 历史目录（相对求解器） | 文件数 |
|---|---:|
{history_table}

共 **{summary['history_files']} 文件、{summary['history_bytes']} 字节**，包含 **{summary['history_ignored']} 个忽略文件**。全量遍历路径、字节数和SHA-256；每条构建／测试／CLI命令前后均与初始基线比较。保存 **{len(comparisons)} 份比对结果文件**，新增0、删除0、修改0；重复执行的维护阶段有同名检查标签，不把文件数冒称总执行次数。基线见 [initial-history.json](initial-history.json)，交付见 [delivery-history.json](delivery-history.json)，差异见 [delivery-history-diff.json](delivery-history-diff.json)。本轮未遇历史目录旧指纹导致的安全集失败，未做历史原件重锁、还原或重写。

三份正式文件及游戏理解、候选约束、候选简化、候选充分条件均与开工HEAD字节相同。既有两类范围外问题保留：`规格/check_revision.py:115` 的T12断言未改（仅只读快照路径更新）；配置与受限声明中 `transfer.partial_acceptance`、`gate.identity_recovery` 对应状态文字原样。桥轴Decision问题则在本轮必要接口迁移中处理，未据此登记整个规格总自查通过。

未运行cargo test --workspace、七个CLI测试目标或写三个历史目录的脚本；未调用git add/commit/checkout/restore/stash。原有未跟踪 `求解器/老项目/` 不属本轮。所有本轮运行产物、脚本和记录位于本目录，提交由主会话处理。

## 不一致清单

本轮未解决不一致：**0项**。指定安全集最终失败：**0项**。前述范围外既有问题没有登记为修复。本轮交付限于现行桥行为同步和指定安全核验，不代表一般离线、全参数或达标循环认证。
'''
(OUT/'记录.md').write_text(record)
print(dump({k:summary[k] for k in ['status','business_files','new_unit_tests','rust_passed','python_cases','history_files','history_diff','record']}))
