#!/usr/bin/env python3
"""汇总本轮直接执行的验证、改动文件与还原清单；并行产物不纳入通过计数。"""
from pathlib import Path
import hashlib,json,re,shlex,subprocess
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;repo=R.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda name:json.loads((O/name).read_text())
cat=json.loads((R/'数据/正式静态目录.json').read_text());lock=read('relock.json');audit=read('current-sync-audit.json')
checks=re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored', (O/'cargo-test-workspace-isolated.log').read_text())
counts=[sum(int(row[i]) for row in checks) for i in range(3)]
commands=[json.loads(l) for l in (O/'commands.jsonl').read_text().splitlines()]
assert commands[-1]['name']=='history-restore-final-tests' or any(c['name']=='history-restore-final-tests' and c['exit_code']==0 for c in commands)
assert counts==[141,0,0],counts
assert read('history-restoration.json')['baseline_byte_equality']
restored=read('ignored-history-recovery.json')['files'];assert all(r['exact_match'] for r in restored)
# 只列本轮活动改动；开工已脏、且明确由并行任务拥有的方案排除。
paths=subprocess.check_output(['git','diff','--name-only','-z'],cwd=repo).decode().split('\0')
paths={p for p in paths if p and p!='求解器/内核维护/代码体检方案.md'}
paths|={'求解器/'+row['file'] for row in lock['inputs']}
files=[{'path':p,'sha256':sha(repo/p),'bytes':(repo/p).stat().st_size} for p in sorted(paths)]
(O/'changed-files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n')
(O/'changes.patch').write_bytes(subprocess.check_output(['git','diff','--',*[r['path'] for r in files]],cwd=repo))
initial=read('initial-history.json')['files'];final=read('after-restore-history.json')['files']
intentional={'求解器/规格/推导/'+n for n in ['三种相位不改产量-v2.md','回路总数决定论-v2.md','总纲-流量存量相位.md']}
history_delta=[p for p,h in initial.items() if final.get(p)!=h]
assert set(history_delta)==intentional,history_delta
assert not (set(final)-set(initial))
restoration={'tracked_files_requiring_restore':0,'new_untracked_files_deleted':0,'preexisting_ignored_files_restored':restored,'final_test_history_delta':read('history-restoration.json'),
 'initial_to_final_intentional_current_document_changes':history_delta,'all_other_initial_history_hashes_unchanged':True}
(O/'历史证据还原清单.json').write_text(json.dumps(restoration,ensure_ascii=False,indent=2)+'\n')
# 全仓 grep 结果保留供按用途复核；独立在研的未跟踪目录不纳入本轮代码写入。
pattern=r'plant_trigger|(?:56|71)\s*条|len\([^\n]*==\s*(?:56|71)\b|植物系物品也不入库|仅在台数等于|只输送成品.*植物'
scan=subprocess.run(['rg','-n',pattern,'.','--glob','!**/target/**','--glob','!.git/**','--glob','!**/内核维护/2026-09-22e/**'],cwd=repo,capture_output=True,text=True)
assert scan.returncode in [0,1]
(O/'grep-final.log').write_text(scan.stdout)
(O/'grep-classification.md').write_text('''# 全仓引用复核\n\n日期：2026-09-22。按当前入口与历史用途区分，本清单不批改历史证据。完整命中见 [grep-final.log](grep-final.log)。\n\n- 内核、topology、数据工具、活动目录与候选报告：旧 plant_trigger 消费者已移除，当前数量为72；test_formal_catalog 中的同名项是显式拒收旧键的回归。\n- 当前覆盖表、运行语义和三份活动推导：植物零入库迁移到「非成品零入库」，真正依赖32台的流量/存量特例保留前件。\n- 内核维护旧轮、约束修订提案/审计、候选轮次、复核、evidence、规格各轮验证、历史修订记录、输入快照及会议归档：属于对应旧版本证据，保留原计数与原句。候选B验证记录已明确历史区与当前入口。\n- 构造/第一张全厂候选、几何/1113流量层：开工已有未跟踪内容，现场可见流量层任务运行；检查器B已注明71历史/72现行双版本。按并行在研目录保留，未修改；其中检查器A/生成代码仍有71断言，交其所属线迁移。所有者澄清尚未收到回复，不把它们计为本轮已迁移。\n- 思路.txt 当前条款数量已从56改为72。\n''')
# 历史执行记录，当前摘要与旧日志各有明确版本边界。
text='''# 内核与正式目录同步执行记录\n\n执行日期及截止日期：2026-09-22。状态：内核/目录同步、重锁及要求的构建、Cargo测试、正向链与旧指纹拒收已完成；规格总自查和附加样例/数据总自查仍有下述既有阻断，不能称全部门禁通过。本文件是维护执行记录，不是全厂可行性或全称运行证书。\n\n## 结果与版本\n\n'''
text+=f"目录版本：`{cat['version']}`；SHA-256：`{sha(R/'数据/正式静态目录.json')}`。旧目录 SHA：`6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff`。72条约束、32项常量；task、18类单位、18配方、物料流量及其余常量保持不变。\n\n| 正式文件 | SHA-256 |\n|---|---|\n"
for source in cat['sources']:text+=f"| {source['path']} | `{source['sha256']}` |\n"
text+='''\n三份正式源及候选约束与[开工指纹](只读文件指纹.json)逐字节一致。未写三份正式文件、候选约束、代码体检方案、2026-09-22d、会议归档。未 add、commit 或执行其他 git 写操作；历史已跟踪文件本轮最终没有需要 git restore 的差异。并行目录自身出现的变化不归入本轮成果。\n\n## 实际变更\n\n- formal_catalog 的条数72；移除 plant_trigger 提取且无默认值；目录重建 sources、constraints、static_checks 并写r23版本。正式条文/据变化为矿系不入库、非成品零入库、回路守恒、回路存量、植株半分，另增1113位置。\n- topology 的核心计划只许两成品，兼容名称「矿系不入库/计划」保留，说明据改为非成品零入库、入库途径、协议核心。三项正式动态义务仍为Unknown；未修改普通转移或D.2支持域。\n- 定向Rust回归遍历32/33台和19种物品，共38种组合；十种含矿非成品、七种植物均拒收，两成品通过，逐项核该检查且核三正式义务为Unknown。Python新增无plant_trigger投影成功和旧键残留拒收两项。\n- 重锁45份kernel-input-v3样例、9份fixture、2份profile-assignment-v2；同步SOURCE_HASHES。当前规格来源标签更新引起参数轴/模型说明SHA变化，最终引用亦重新核验。\n- 更新候选B来源及当前报告。3个失效/tmp资料指向仓库内SHA完全一致的存档；转换器采用相同存档入口，存档本身未写。\n- 两张覆盖表为114行规则、16行任务、72条约束；保持既有逐条去向，重算原文/行号/据行/索引。当前规格与推导迁移旧零入库依据；规格修订记录追加目录及三源SHA。旧历史记录保留。\n\n完整逐文件路径、字节数与最终SHA见[changed-files.json](changed-files.json)，逐行变更见[changes.patch](changes.patch)，引用变更见[relock.json](relock.json)。新增脚本均在本目录。全仓检索及并行目录边界见[引用复核](grep-classification.md)。\n\n## 验证结果\n\n| 验证 | 结果 | 证据 |\n|---|---|---|\n| debug / release构建 | 两者退出0；共享target | [debug](cargo-build-debug.log)、[release](cargo-build-release.log) |\n| 最终 cargo test --workspace | 141/141通过，0失败、0忽略 | [完整日志](cargo-test-workspace-isolated.log) |\n| Python目录回归 | 8/8通过；1232单位叶字段＋154配方叶字段变异均拒绝，另含集合负例 | [目录回归](catalog-regressions.log)；与Cargo内调用不重复合计 |\n| 正式目录完整回源 | PASS | [最终回源](catalog-verify-final.log) |\n| 本轮同步独立审计 | PASS：72条、32常量、56份活动引用、两张覆盖表、来源与登记 | [审计JSON](current-sync-audit.json)；不是规格总门禁通过 |\n| 核心计划矩阵 | 38/38组合断言通过 | Rust测试 `core_storage_plan_accepts_only_products_at_any_grower_count` |\n| seed/check/run/verify-record | 4步全部退出0；run 6 ticks | [命令与二进制SHA](positive-validation.json)、[运行记录](positive-run.json) |\n| 上一目录SHA负对照 | 非零退出且status=invalid_input、源文件指纹不符 | [拒收日志](stale-catalog.log) |\n| 候选B当前报告 | 4924通过、0失败、75不能静态检（其中72正式条目） | [候选报告](candidate-b-report.log)；计划核验，不是运行认证 |\n| 规格全自查 | FAIL：既有T12周期末断言与当前文档不符 | [最终失败日志](spec-check-final.log) |\n| 附加样例自查 | FAIL：桥轴对象被通用Decision递归错误识别 | [样例失败](examples.log) |\n| 附加数据全自查 | FAIL：无法取得上述样例检查成功报告；此前目录、CSV、来源与覆盖断言已走过 | [数据自查](data-check.log) |\n\n规格脚本只对齐本轮正式来源/数量/只读基线，旧语义门禁未跳过。诊断中曾检查T12迁移与当前轴状态，继续发现配置JSON中两项coverage_loss仍写“待实现”、文档却写“已实现”；这些超出本轮正式源同步的修复未保留，探索日志spec-check-2至5仍归档。样例故障来自未改动的runtime_example.validate_decision_tree；[同步审计](current-sync-audit.json)记录HEAD对应的既有阻断。\n\n第一次正向链的四步实际成功，但脚本误要求拒收文本含英文sha256，因实际错误为中文“源文件指纹不符”而失败；已改成核status与实际拒收原因，最终五步全部符合预期。首个全套测试进程返回143，未形成完成记录、不计为通过；随后的隔离全套测试和最终引用重锁后全套复跑均141/141通过。\n\n## 历史证据保护与还原\n\n测试使用 `KERNEL_TEST_EVIDENCE_DIR=本目录/test-evidence-tmp`；最终两次再通过[bin/python](bin/python)将六个旧Python CLI脚本固定输出目录重定向到该临时树，只改变输出位置，保留断言、输入和调用。测试前记录四棵历史树各子目录git状态，并记录全部文件SHA；既有忽略文件另做可恢复副本。快照见initial-history、before-tests-history、after-tests-history、after-restore-history各JSON，较早两次保存在attempt-1/、attempt-2/。\n\n第一轮进程终止后，已跟踪历史内容与HEAD一致，但5份开工已存在、被gitignore忽略的记录发生指纹字段变化。由于不是测试新建文件，没有删除；利用未被改动的同轮记录、开工哈希与引用映射恢复，逐个重建结果均与测试前SHA完全相同，才写回。第一次重建未命中任何完整SHA，因此没有写回；补齐该旧证据所绑定的正式约束SHA后五份全部命中。修改后的测试产物另存ignored-test-outputs。最终隔离测试历史差异为0；无需git restore、无需删除新未跟踪历史文件。\n\n| 精确恢复的既有忽略文件 | 恢复后的SHA-256 |\n|---|---|\n'''
for row in restored:text+=f"| `{row['path']}` | `{row['expected_sha256']}` |\n"
text+='''\n还原机器清单见[历史证据还原清单.json](历史证据还原清单.json)、[精确恢复核对](ignored-history-recovery.json)。开工至结束，历史快照中的三个差异是本轮明确修改的活动推导正文（上述来源迁移），所有其他历史文件与开工字节相同。没有将这些当前文档变化算作测试历史污染。\n\n执行期间本目录出现另一个执行者的 `resume/` 产物。本轮未写入或删除该目录，也不将其检查计入以上通过数。\n\n## 命令与结果\n\n工作目录统一为求解器；Python使用`-B`，构建jobs=6、测试线程=1，OMP/OpenBLAS/MKL线程=1，CARGO_TARGET_DIR指向共享target。全部受控步骤的argv、工作目录、环境、耗时、退出码见[commands.jsonl](commands.jsonl)。首次初始化/生成步骤为 `history_guard.py initial`、`update_tests.py`、`regen_constraints.py`、`prepare_relock.py`、`relock.py`，均退出0；生成摘要见regen_constraints.log和relock.log。后续记录如下：\n\n| 步骤 | 命令 | 退出码 | 日志 |\n|---|---|---:|---|\n'''
for c in commands:text+=f"| {c['name']} | `{shlex.join(c['argv'])}` | {c['exit_code']} | [{c['log']}]({c['log']}) |\n"
text+='''\n## 交付自审\n\n已按未来读者视角复读：现行版本/计数与历史区分开；全部数字附作用域；两项总门禁失败和并行在研目录迁移缺口显式保留；未把静态计划、局部运行或测试通过当全厂认证。表内链接与关键产物存在，正式源SHA和目录SHA逐项核验。\n'''
(O/'记录.md').write_text(text)
summary={'status':'synchronized_with_existing_gate_failures','catalog_version':cat['version'],'catalog_sha256':sha(R/'数据/正式静态目录.json'),'rust_tests':dict(zip(['passed','failed','ignored'],counts)),'python_catalog_tests':{'passed':8,'failed':0},'positive_commands':5,'changed_files':len(files),'restored_preexisting_ignored_history_files':len(restored),'protected_sources_unchanged':True,'global_gate_blockers':audit['global_gate_blockers']}
(O/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
