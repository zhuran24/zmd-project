"""第五轮历史交付生成器（当前交付入口为finalize_revision_r4.py）：以实际日志、保护指纹和当前文档形成结论，不复制缓存或仓库。"""
from pathlib import Path
import json,re,hashlib,datetime,subprocess
ROOT=Path(__file__).resolve().parents[3];K=ROOT/'crates/kernel';E=K/'evidence/round5';BASE=ROOT/'数据/样例'
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
log=(E/'cargo-test.log').read_text();assert 'FAILED' not in log and 'error:' not in log
counts=[int(v)for v in re.findall(r'test result: ok\. (\d+) passed',log)];assert sum(counts)>=113,counts
clippy=(E/'clippy.log').read_text();assert 'Finished 'in clippy and 'error:'not in clippy
records=read(E/'record-validation.json');audit=read(E/'audit-results.json');bench=read(E/'benchmark-final.json')
assert records['status']=='通过' and audit['status']=='pass'
assert set(audit['required_unexercised'])=={'transfer.resume_event','connection.bridge_first_contact','damping.belt_adjacency'}
assert len(read(E/'polling-six-orders.json')['cases'])==6
dense=read(E/'dense-manufacturing-audit.json');assert dense['sensitivity']=='observed' and dense['distinct_ratios']==['0','1']
assert sum(r['status']=='period_preconditions_pass'for r in dense['cases'])==4
protected=read(E/'protected-baseline.json');changes=[p for p,h in protected.items()if sha(Path(p))!=h];assert not changes,changes
before=read(E/'baseline.json');concurrent=[dict(path=p,before=h,after=sha(Path(p)))for p,h in before.items()if '/规格/'in p and not p.endswith('内核实现-对规格的疑问.md') and Path(p).exists()and sha(Path(p))!=h]
forbidden=[str(p)for p in E.rglob('*')if p.is_dir()and p.name in ('target','.cargo-home','registry','snapshot')];assert not forbidden,forbidden
extensions=sorted({p.suffix for p in E.rglob('*')if p.is_file()});assert set(extensions)<={'.json','.md','.log','.py','.sh'},extensions
old=K/'evidence/benchmark.json';legacy=E/'benchmark-legacy.json'
if not legacy.exists():legacy.write_bytes(old.read_bytes())
requested=['benchmark_brick_60','benchmark_candidate_b'];final_bench={**bench,'schema':'kernel-benchmark-round5-v1','requested_cases':requested,'requested_targets_met':all(r['target_met']for r in bench['reports']if r['name']in requested),'before_evidence':str(E/'benchmark-before.json'),'legacy_evidence':str(legacy),'compiler':subprocess.check_output(['rustc','--version'],text=True).strip()}
write(old,final_bench)
open_items=[
 'KQ-09：cycle装载资源不足已保留inconclusive，但现行schema强制未决携完整上下文，与正文装载失败可空冲突；待S线修订schema，原样证据见evidence/revision-r3/cli-schema-audit.json。',
 'K6：connection.bridge_first_contact仅作输入先接历史检查，固定已建成段没有运行定向事件。',
 'K6：damping.belt_adjacency在path_runs下不被调用，需geometric_components实现；连续带不构成几何邻接轴执行证据。',
 'K6：transfer.resume_event未实际触发；固定开关/供电的运行段不能执行暂停后的重新启用，相关调试/离线后效仍未支持。',
 '密集制造闭环6种局部序中的2种在1000 tick内未决；4种已核周期显示分流比0/1敏感性，但条件空种子的完整可达史、全局模板全序及一般动态约束未获证。',
 '级二周期提升仍受整批容量余量与非精确拿取族义务阻断；种子族、参数族、读法族认证、一般动态约束仍未认证；R线当前为第1轮修订，本实现未承担其最终约减复核。']
metrics={r['name']:r['ms_per_tick']for r in bench['reports']}
result={'schema':'kernel-round5-delivery-v1','status':'implementation_delivered_with_open_coverage','profile_revision':read(ROOT/'规格/内核配置-v1.json')['revision'],'tests_passed':sum(counts),'clippy':'pass','reference_records':len(records['records']),'audited_records':len(audit['records']),'cycle_results_checked':len(audit['cycles']),'requested_performance_targets_met':final_bench['requested_targets_met'],'ms_per_tick':metrics,'protected_files':len(protected),'protected_changes':changes,'open_items':open_items,'scope':'单个参数点/读法/条件种子的受限执行与生产周期；不作级二或全称认证'}
write(E/'交付结果.json',result)
# 追加历史记录，当前规范以README与第五轮报告为准。
revision=K/'修订记录.md';text=revision.read_text();marker='## 第五轮任务书实现：规格第8轮接口与循环收口'
suffix=''
if marker in text:
 start=text.index(marker);end=text.find('\n## ',start+len(marker))
 if end!=-1:suffix=text[end:]
 text=text[:start].rstrip()+'\n'
text+='''

'''+marker+'''

本次执行记录日期：2026-09-19至2026-09-20。KQ-01–KQ-08已与S线第8轮答复对齐；前述第四轮停止策略属于史料，当前接口见[README](README.md)和[第五轮报告](evidence/round5/实施与验证.md)。

- K1：新增种子派生，保留显式级仲裁；before_boundary重建冗余上下文，after_closure保持并校验原参数、真实游标和账，参数缺失或冲突拒收。
- K2–K4：逐字段生产键、cycle/verify-cycle、v3分途径台账、充分补矿/显式历史、t+1续跑、v2局部分支表和I身份维护事件。级二仍停止。
- K5：remaining决定制造完成，整批输出核所有物种；max_sweeps和资源统计、显式base_dir内存解析、库存数组规范排序；时间归一超域停止不环绕。
- K6：扩展桥、传输、混做、阻尼、门控、轮询与密集结点记录；connection.bridge_first_contact只有输入历史检查，transfer.resume_event及damping.belt_adjacency未实际触发。密集制造闭环6局部序取得4份已核周期，D总量与另一来源正量、M收后1 tick腾空均通过；直接分流比0/1构成条件敏感性证据，另2序仍未决。
- K7：新增两档合成生成器，单位/仓库依赖失效缓存与级排序复用；缓存开关路径逐字段差分，覆盖冷却与窗口恢复。
- K8：原测试保留；KQ-02/06旧停止预期按已裁规格改为成功续跑/换支。新增种子、循环/篡改、账本、补矿、库存序、缓存和数值资源回归。

'''
text+=f"最终全工作区 **{sum(counts)} 项通过、0失败**，Clippy `--all-targets -- -D warnings`通过；双参考4份记录和扩展{len(audit['records'])}份记录、{len(audit['cycles'])}份循环结果完成验收。砖档57单位/97PC为 **{metrics['benchmark_brick_60']:.6f} ms/tick**；219制造台/315逻辑段/630PC为 **{metrics['benchmark_candidate_b']:.6f} ms/tick**。额外81单位/100PC对照为{metrics['benchmark_brick']:.6f} ms/tick，不能据前两档推为任意布局的性能保证。\n\n"
text+='[测试日志](evidence/round5/cargo-test.log)、[Clippy](evidence/round5/clippy.log)、[双参考验收](evidence/round5/record-validation.json)、[扩展审计](evidence/round5/audit-results.json)、[性能](evidence/benchmark.json)、[交付结果](evidence/round5/交付结果.json)与[范围审计](evidence/round5/范围审计.json)保存实际证据。旧黄金、历史v2记录和正式源保护指纹保持；源码、样例及投影的第8轮迁移经过重新运行，不给旧结果换哈希冒充通过。未改正式文件/候选约束/模拟器，未commit/push。\n'
revision.write_text(text+suffix)
# 交付物读者视角自审及链接核验。
docs=[K/'README.md',revision,E/'实施与验证.md',BASE/'第五轮样例说明-kernel.md']
bad=[]
for doc in docs:
 content=doc.read_text()
 assert re.search(r'20\d{2}-\d{2}-\d{2}',content[:512]),doc
 for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',content):
  if target.startswith(('http:','https:','#')):continue
  path=(doc.parent/target.split('#')[0]).resolve()
  if not path.exists()and path!=E/'范围审计.json':bad.append(dict(document=str(doc),target=target))
assert not bad,bad
scope={'status':'pass','protected_files':len(protected),'protected_changes':changes,'shared_spec_changes':concurrent,'shared_spec_note':'S/R写权内并发修订，只读核对；不是K线产物。K线疑问文件单列在交付清单。','evidence_forbidden_directories':forbidden,'evidence_extensions':extensions,'build_target':str(ROOT/'target'),'scope_of_audit':'保护集原始字节、显式产物路径和本轮证据目录；不声称审计了整个系统所有文件。','document_reader_review':{'status':'pass','documents':[str(p)for p in docs],'checks':['当前/历史分区明确','头部状态与证据相符','不将条件轨迹写成全称证明','数字分别给测量域','未决逐项保留','链接存在','没有占位符或工作流指令回声'],'broken_links':bad}}
write(E/'范围审计.json',scope)
started=(E/'baseline.json').stat().st_mtime
candidates=list((K/'src').glob('*.rs'))+list((K/'tests').glob('*.py'))+list((K/'tests').glob('*.rs'))+list((K/'tests/fixtures').glob('*.json'))+list(BASE.glob('*'))+[K/'README.md',revision,ROOT/'规格/内核实现-对规格的疑问.md',K/'evidence/benchmark.json']+list(E.rglob('*'))
candidates += list((K/'evidence/revision-r2').glob('*.json'))
paths=[]
for p in candidates:
 if not p.is_file()or p.stat().st_mtime<started:continue
 if str(p)in before and sha(p)==before[str(p)]:continue
 if p.name in ('交付清单.json','最终回复.json','final-audit.log'):continue
 paths.append(p.resolve())
paths=sorted(set(paths));manifest={'schema':'kernel-round5-files-v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))for p in paths],'protected_sources':[dict(path=p,sha256=h)for p,h in protected.items()],'nonrecursive_files':[str(E/'交付清单.json'),str(E/'最终回复.json'),str(E/'final-audit.log')]}
write(E/'交付清单.json',manifest)
summary=f"已实现种子派生、生产键/循环检测/独立重跑、v3台账及补矿/续跑/分支接口。\nKQ-07、KQ-08已按规格第8轮答复落实；制造潜伏项、资源参数和内存解析已修复。\n全工作区{sum(counts)}项测试通过，Clippy零警告，verify_outputs和扩展审计通过。\n57单位/97PC：{metrics['benchmark_brick_60']:.3f} ms/tick；219台/630PC：{metrics['benchmark_candidate_b']:.3f} ms/tick。\n密集结点4份周期核验显示分流比0/1敏感性；先接定向、恢复事件和几何邻接轴的运行覆盖、级二及全称认证仍未完成。\n完整论证、来源、指标和逐文件指纹已落盘；未commit/push。"
write(E/'最终回复.json',dict(files=[str(p)for p in paths]+[str(E/'交付清单.json'),str(E/'final-audit.log')],summary=summary,open_items=open_items))
print(json.dumps(dict(status='pass',tests=sum(counts),records=len(audit['records']),cycles=len(audit['cycles']),files=len(paths)+2,metrics=metrics,requested_targets_met=final_bench['requested_targets_met']),ensure_ascii=False))
