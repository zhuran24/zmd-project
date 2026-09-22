"""追加汇入台账、保存实际自核命令和最终指纹。仅在规格席写入范围执行。"""
from pathlib import Path
import hashlib,json,subprocess,sys
R=Path('/home/zhuran24/zmd-research-fresh'); S=R/'求解器/规格'; T=R/'求解器/会议成果/任务书7执行'; E=Path(__file__).resolve().parent
before=json.loads((E/'before.json').read_text())['files']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
entries=[
 ('受限转移定义.md','§2—5、§6.1—6.5','任务2正文及配套清单；任务6 SP-01—03、SP-06—09、SP-11','§6.5整节落地；同步部分接收、所有尝试冷却、候选接收读点、I−O−P账、标签非干扰、前向投影/反向复原；新键及失败环按支持条件登记。'),
 ('内核输出.md','§1—2、§4—5','任务2证书清单；任务6 SP-08、SP-10—12','无线实际入库与玩家/代表账分列；区分生产周期、具体完整周期、诊断和直接证明；逐项列接收域、固定参数、初态覆盖、对应义务及重放检查。'),
 ('内核输出.schema.json','$defs.RunRecord/CycleKey/Cycle/CycleResult/Parameters及新增证明类型','任务2schema修改请求；任务6 SP-02、SP-08、SP-11—12','运行/周期升版v4/v3，增加kernel-proof-v1；环境句固定，新键phase-cycle-key-v1，撤旧full_base/lift分支；新增逐项correspondence与证据范围，正负例验收。'),
 ('内核配置-v1.json','revision、axes及99轴处置','任务2配套轴与停止项；任务6 SP-01—02、SP-05—09、SP-11—12','every_attempt、fixed_run_order及全区间接收响应写入；纯重排保持关系与工程停止分栏，正式循环停止改为缺少具体复原/覆盖证据时触发。'),
 ('选择点参数轴.md','§1—2及§3 A3','任务2配套清单；任务6 SP-01—02、SP-05—09、SP-11—12','保持99轴恰集；固定判定作用域和排序移F；清除零传输未定和离线清零候选，登记后态/状态投影的支持条件。'),
 ('受限模型声明.md','§2、§4—5','任务2支持域与停止项；任务6 SP-01—12','同步所有配置值、停止触发与覆盖损失；22已定、44选值、18停止、15输入量化；真实周期与全称覆盖分别验收。'),
 ('内核输入.md','§3.3、§5轴镜像/§5.2、§10','任务2真实拿取/代表分账接口；任务6 SP-02、SP-05—08','整场固定判定与99轴生命周期镜像；纯重排保持关系、事件实例嵌入、默认程序可达谓词/包络和关闭intake接口断点。'),
 ('运行语义.md','源表、§2—5、§7','任务2§6.5及清单；任务6 SP-01—11','更新现行源指纹、冷却、固定次序与离线派生量；三条设计律逐单位范围、六类连续制造的台数前件和PA-11完整D域、共同状态充分证明。'),
 ('选择点清单.md','T2、T6、T10—12及设计律条件接口','任务2 T6/T12请求；任务6 SP-01—05、SP-07、SP-11','已定事实与具体后效分开；默认后态衔接、接收/循环义务、逐单位阻尼短路及末端箱前件落地。'),
 ('四件前置义务对照.md','§1—6','任务2周期/恢复义务；任务6 SP-01—12、PC-01—09','九项具体断点逐项带规则原句与推导终点，分构造/推导/复核承接；零传输for_owner结清，实际时间有限化继续开放。'),
 ('参数扫描约减.md','头部史料状态及§8','任务6 SP-03、SP-08—11','旧§1—7限原版本史料，当前新增单级阻尼短路、恢复后交换证明重核、真实耗时与失败环出口及探索方向约束。'),
]
record=T/'规格回填.md'
assert record.stat().st_size==before[str(record)]['bytes'] and sha(record)==before[str(record)]['sha256'], '原回填记录变动，须先人工核对，避免覆盖并发追加'
lines=['\n\n## 汇入记录（2026-09-21）\n',
 '本节为任务书7规格执行席的汇入执行记录。截止本次，任务2、任务6两份指定修改稿已落地顶层规格、证书schema及配置；前文任务1与主会话补记按当时状态保留。当前规则指纹为`d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a`，任务为`1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac`，约束为`f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6`。三份正式文件、候选约束及两份输入稿原字节保持。\n',
 '### 汇入依据与冲突处置\n',
 '任务2稿[受限转移定义-§6.5替换稿](受限转移定义-§6.5替换稿.md)和任务6稿[规格修改稿-任务6](规格修改稿-任务6.md)的完整输入指纹见[before.json](证据/规格/汇入/before.json)。规则L36现文恢复了“即使那个物品格中没有物品也一样”，规则及主会话三审§6的现行事实优先。任务2沿用的31ced2a24fef及零传输冷却未决，与任务6 SP-01发生明确冲突：按任务6修订后的口径，空箱、全拒收、部分及全部送出每次尝试均进入5 tick冷却，T6/配置/正文同时结清。\n',
 '任务2对旧生产键保守保留年龄、累计和审计期限的覆盖提醒，与任务6 SP-08的新条件投影衔接：采用任务6所列未来读取前件与phase-cycle-key-v1；保留详细旧键或未通过删字段前件的输入继续承担循环覆盖证明。两稿的接收环境、实际入库账、正式循环前向对应及反向复原方向一致。所有新增条件证明的独立复核状态保持pending；本次完成规格汇入。\n',
 '### 逐文件、逐节记录\n',
 '| 文件 | 修改位置 | 依据稿 | 落地结果 |\n|---|---|---|---|\n']
for n,sec,source,result in entries:
 lines.append(f'| [规格/{n}](../../规格/{n}) | {sec} | {source} | {result} |\n')
lines += [
 '\n### 证书版本与停止项\n\n',
 '当前schema为kernel-output-v4、kernel-cycle-v3、kernel-proof-v1，键为phase-cycle-key-v1。生产部分周期、具体完整周期、低产诊断和直接充分证明各有明确字段；完整周期与真实反例须逐项核实际起点、固定参数、耗时、拿取前缀合法、仓库及全部有效状态复原和操作精度。全称覆盖另核全部起法、参数、离线/恢复和可达循环。环境前提只写“仓库收得下成品。”，候选与实际接收域另列。\n\n',
 'warehouse.periodic_lift保留原轴名作证明义务入口，旧级二命题及full_base/lift接口退出当前证书。零传输冷却已有事实，for_owner为空。无线部分扣格、可观察匿名格竞争、关闭intake后态衔接、一般指针接续与失败环唤醒、实数时间有限表示和具体完整周期复原按[四件义务§6](../../规格/四件前置义务对照.md)承接。资源耗尽为inconclusive，实现缺失为unsupported，缺推导为unresolved。\n\n',
 '### 作者检查、证据与交接\n\n',
 '自核入口为`python -B 求解器/会议成果/任务书7执行/证据/规格/汇入/audit_merge.py`，cwd为仓库根。实际命令、退出码及输出见[commands.json](证据/规格/汇入/commands.json)与[audit.log](证据/规格/汇入/audit.log)，完整结果见[audit-results.json](证据/规格/汇入/audit-results.json)。核99轴恰集/生命周期/配置镜像、当前条款扫描、来源指纹、链接、Draft 2020-12元校验与25个schema正反例。合成样例只用于形状检查，未作为真实游戏证书保存。\n\n',
 '读者自审已核终态、来源与支持条件、固定参数含义、前向/反向/全称证据分列、数字口径及交叉引用。修正了残留零传输未定、旧生产键史料指向和窗口时间取模的过宽表述。旧参数扫描证明分区为史料，新规则下的交换与失败环义务明确列出。结构通过与内核运行验收分别报告。\n\n',
 '本次未运行git，未写Rust/数据/模拟器，未编译内核。任务8须按最终规格实现参数迁移、部分传输/门恢复、规范键及新证书生成与语义验收，并重核受影响样例；独立席复核任务2/6条件证明及汇入接口。PC-01—09保持各自承接，L=0、U=1113。\n\n',
 '本次实际新增/修改文件的绝对路径、字节数、完整SHA-256及覆盖说明见[manifest.json](证据/规格/汇入/manifest.json)；manifest不自列哈希。证据目录仅含脚本、日志、JSON、Markdown。\n',
]
record.write_text(record.read_text()+''.join(lines))

command=[sys.executable,'-B',str(E/'audit_merge.py')]
p=subprocess.run(command,cwd=R,text=True,capture_output=True)
(E/'audit.log').write_text(p.stdout+p.stderr)
cmdrec={'commands':[{'argv':command,'cwd':str(R),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'interpretation':'作者规格一致性及schema形状验证；无内核装载或步进'}],
 'implementation_attempts':[
  {'command':'python -B .../merge_bodies.py','exit_code':1,'error_excerpt':"ValueError: substring not found",'resolution':'T12下一节为T14，修正章标题；已写受限转移的步骤按已落地标记跳过，其余正文完成'},
  {'command':'python -B .../audit_merge.py','exit_code':1,'error_excerpt':'SyntaxError: unterminated string literal (detected at line 71)','resolution':'修正测试脚本字面量并重跑'},
  {'command':'python -B .../audit_merge.py','exit_code':1,'error_excerpt':'schema:缺反向复原完整周期拒收','resolution':'负例构造被后续正例原地修改；改为深拷贝后再核，拒收门槛通过'}]}
(E/'commands.json').write_text(json.dumps(cmdrec,ensure_ascii=False,indent=2)+'\n')
assert p.returncode==0,p.stdout+p.stderr
report=json.loads((E/'audit-results.json').read_text())
assert hashlib.sha256(record.read_bytes()[:before[str(record)]['bytes']]).hexdigest()==before[str(record)]['sha256']

(E/'执行核查.md').write_text(f'''# 规格汇入执行核查

日期：2026-09-21。性质：作者执行记录与证据索引；规格汇入完成，新增条件证明的独立复核及任务8内核运行验收仍待执行。

输入版本见before.json，最终版本见manifest.json。规则第36行现行为d150b86b398f，任务2稿中的旧指纹与零传输未决已按任务6 SP-01及三审§6修订。两稿其余衔接与逐文件处置见../../../../规格回填.md的“汇入记录”（实际相对链接见下文）。

实际运行`{sys.executable} -B {E/'audit_merge.py'}`，cwd=`{R}`，退出{p.returncode}。输出：

```text
{p.stdout.strip()}
```

检查包括99轴三份表与配置的恰集、处置及生命周期；旧口径扫描；保护文件及源稿原字节；链接；AJV 8.20.0 Draft 2020-12元校验与25个正反例。共{report['passed']}项作者检查通过、{report['failed']}项失败。多项属于逐轴核对，数量不表示独立游戏行为样例数。

schema合成材料只存在于自核进程内。旧环带证书作为形状脚手架的来源按audit-results.json锁定，其内容和文件均未修改。合成proof路径和全零摘要只是校验占位，语义验收会要求真实文件与内容；本次未发出生产或完整基地周期证书。真实入库、玩家拿取与数学代表调整分别有字段与守恒义务；形状互相冒充的负例拒收。

读者自审核了：当前事实与史料分区、头部状态、已定和待证范围、22/44/18/15处置计数、正式行号、链接、条件前件、代码实现边界。修订脚本保留在本目录供审阅，按汇入前版本顺序执行；完成后只重跑audit_merge.py。脚本中的早期错误及修复见commands.json的implementation_attempts，最终自核已重跑。

本轮仅写11份顶层规格、规格回填.md末尾和本证据目录；规格回填.md原前缀字节哈希与before.json一致。未调用git，未触碰模拟器，未改正式文件、候选约束、Rust或数据，未运行cargo。仓库恢复安全、精确时间有限化、真实唤醒、默认后态接口和独立复核按PC-01—09及任务8承接；for_owner=[]。

[汇入记录](../../../规格回填.md)；[完整检查结果](audit-results.json)；[命令](commands.json)；[最终清单](manifest.json)。
''')
# 去掉不必要的可误读相对文本指向，只保留已核链接。
p=E/'执行核查.md';p.write_text(p.read_text().replace('见../../../../规格回填.md的“汇入记录”（实际相对链接见下文）','见下文链接的规格回填.md“汇入记录”'))
changed_specs=[S/n for n,_,_,_ in entries]
files=changed_specs+[record]+sorted(p for p in E.iterdir() if p.is_file() and p.name!='manifest.json')
manifest={'status':'done','scope':'规格汇入与作者检查；内核实现和独立复核另交任务8及独立席','for_owner':[],
 'open_items':['任务8实现最终参数/生命周期、部分传输和门恢复、新状态键及v4/v3证书，并重验相关样例。','独立席复核任务2/6条件证明与本次契约汇入；PC-01—09按四件义务§6逐项承接。','具体完整周期及全称认证仍需实际起点、恢复集合、固定参数和真实仓库/外部过程复原证据。'],
 'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],
 'manifest_self':str(E/'manifest.json'),'protected_and_inputs':{str(R/n):sha(R/n) for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt','求解器/会议成果/任务书7执行/受限转移定义-§6.5替换稿.md','求解器/会议成果/任务书7执行/规格修改稿-任务6.md']},
 'spec_count':len(changed_specs),'backfill_original_prefix_unchanged':True,'audit_summary':{'passed':report['passed'],'failed':report['failed'],'schema_cases':report['schema_case_count']}}
(E/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'done','modified_specs':len(changed_specs),'files_including_manifest':len(files)+1,'audit':manifest['audit_summary']},ensure_ascii=False))
