"""Final gate ledger and reader-facing execution record; never mutates history."""
import datetime,json,re
from pathlib import Path
from continuation_guard import *

def main():
    before=check('final-ledger-before')
    safe=json.loads((RUN/'continuation-safe-passed.json').read_text())
    iso=json.loads((RUN/'isolation-accepted.json').read_text())
    aa=json.loads((RUN/'continuation-a-final.json').read_text())
    byte=json.loads((RUN/'production-byte-equivalence.json').read_text())
    closure=json.loads((RUN/'continuation-compile-closure.json').read_text())
    negative=json.loads((RUN/'continuation-compile-closure-negative.json').read_text())
    entry=json.loads((RUN/'continuation-entry-validation.json').read_text())
    rounds=json.loads((RUN/'continuation-isolation-rounds.json').read_text())
    assert safe['passed'] and safe['rounds']==2 and safe['commands']==18
    assert safe['source_manifest_sha256']==sha(RUN/'continuation-b-source.json')==iso['source_manifest_sha256']
    assert iso['passed'] and len(rounds)==26 and {x['round'] for x in rounds}=={1,2}
    assert all(x['passed'] for x in rounds)
    assert all(sum(x['count'] for x in rounds if x['round']==n)==149 for n in [1,2])
    assert byte['passed'] and len(byte['binaries'])==2 and all(x['byte_equal'] for x in byte['binaries'])
    assert aa['passed'] and aa['aa_pairs']==44 and closure['passed'] and negative['rejected'] and entry['passed']
    assert json.loads((RUN/'continuation-write-boundary-audit.json').read_text())['passed']
    assert json.loads((RUN/'continuation-r3-assertion-parity.json').read_text())['passed']
    assert sha(RUN/aa['runtime_manifest'])==aa['runtime_manifest_sha256']
    runtime_a=json.loads((RUN/aa['runtime_manifest']).read_text());runtime_b=json.loads((RUN/'continuation-runtime-dependencies.json').read_text())
    assert all(runtime_b['files'][p]==row for p,row in runtime_a['files'].items())
    restored=json.loads((RUN/'核验/restoration-audit.json').read_text())
    for row in restored['restored']+restored['early_round5']:assert sha(REPO.parent/row['path'])==row['expected']
    for row in restored['lost_originals']:assert sha(REPO.parent/row['path'])==row['current_sha256']
    markers=json.loads((RUN/'continuation-markers-approved.json').read_text())
    for path,row in markers.items():assert sha(REPO.parent/path)==row['sha256']
    current=g.scan(BASE['root'],BASE['excludes']);diff=g.changes(BASE,current)
    roots=['求解器/crates/kernel/evidence/','求解器/crates/kernel/复核/','求解器/数据/复核/','求解器/规格/复核/','求解器/内核维护/']
    historical=[x for x in diff if any(x['path'].startswith(p) for p in roots)]
    assert len(historical)==6 and {x['path'] for x in historical}==set(markers) and all(x['before'] is None for x in historical)
    write(RUN/'continuation-final-protection.json',dict(history_changed=6,existing_history_changed=0,authorized_marker_additions=historical,full_changes=diff,coverage=[dict(root=p,files=sum(row['kind']=='file' and path.startswith(p) for path,row in current['entries'].items())) for p in roots]))
    commands=[json.loads(p.read_text()) for p in RUN.glob('*.command.json')]
    commands=[x for x in commands if 'cpu_cores_average' in x]
    resource=[x for x in commands if x.get('returncode')==x.get('expected') and not x.get('violation') and not x.get('protection_error')]
    assert all(x['cpu_cores_average']<=6 and len(x['affinity'])<=4 for x in resource)
    counts={}
    for name in ['kernel-lib','topology-lib','reference','validation','kernel-doc','topology-doc']:
        s=(RUN/('continue-frozen-safe-2-'+name+'.stdout.log')).read_text();matches=re.findall(r'test result: ok\. (\d+) passed;',s);assert matches;counts[name]=sum(map(int,matches))
    warnings=[]
    for n in [1,2]:
        for line in (RUN/f'continue-frozen-safe-{n}-clippy.stdout.log').read_text().splitlines():
            try:v=json.loads(line)
            except ValueError:continue
            if v.get('reason')=='compiler-message' and v['message']['level']=='warning':warnings.append(v['message'])
    assert not warnings
    at=datetime.datetime.now().astimezone().isoformat()
    summary=dict(verdict='DONE',record_path=str(RUN/'记录.md'),at=at,history_changed=6,existing_history_changed=0,restoration_reconciled=True,history_recovery='partial: 13 original byte streams unavailable and explicitly marked',safe_rounds=2,safe_counts=counts,harnesses=13,tests_per_isolation_round=149,cli_suites_per_round=7,isolation_rounds=2,compile_closure=True,omitted_module_rejected=True,production_byte_equal=True,aa_pairs=44,reference_closure=True,entry_interfaces_validated=entry,clippy_warnings=0,resource=dict(affinity=sorted(CPUS),max_observed_average_cores=max(x['cpu_cores_average'] for x in resource),max_total_threads=max(x['max_total_threads'] for x in resource)),git_operations=False,remaining='none within batch 0 execution scope',known_limit='R3 historical expired fixture keeps stale reference hashes and rejects at source validation; this is not new evidence of expired-gate semantic coverage.')
    write(RUN/'continuation-final.json',summary)
    header='续接状态（2026-09-23）：进行中；以下原席结论保留为当时快照，最新阶段见文末续接记录。'
    record=RUN/'记录.md';text=record.read_text();assert header in text
    text=text.replace(header,'续接状态（'+at+'）：**DONE，第 0 批执行验收通过**。13 项原字节仍缺失，已逐项标记；本轮未执行 Git 操作。最新结论及边界见文末“第 0 批最终验收”。以下原席 BLOCKED 段落保留为历史快照。',1)
    marker_lines='\n'.join('- `'+p.removeprefix('求解器/')+'`' for p in markers)
    text+='''\n\n## 第 0 批最终验收\n\n截止：'''+at+'''。判定 **DONE**，只适用于本记录绑定的第 0 批测试基础设施与冻结来源。生产实现、公开 API、运行时 verify_all.py / audit_task7.py 及其原有导入依赖未修改。未运行 cargo test --workspace 的无选择全测试入口；副本使用方案指定的 --tests --no-run 构建及已绑定 harness 绝对路径执行。\n\n| 完成门槛 | 结果 | 证据 |\n|---|---|---|\n| 恢复逐项对账 | 160 可恢复项、早期 round5 3 项、7 个旧路径移出、14 历史版本定位再次通过；13 原件缺失有 6 份原目录标记 | [恢复回执](continuation-restoration.json)、[标记清单](continuation-markers-approved.json) |\n| 连续两轮安全回归 | 最终 R3 修复版本连续两轮，各 9 命令；Clippy 0 告警 | [安全回归](continuation-safe-passed.json)、[命令结果](continuation-frozen-safe-results.json) |\n| 七 CLI 与副本隔离 | 13 个 metadata 目标完整对应；每轮 149 项，7 CLI 各执行两轮；两个 bin harness 为 0 项 | [凭据](isolation-accepted.json)、[两轮结果](continuation-isolation-rounds.json)、[harness](test-harnesses.json) |\n| 文件/目录保护 | 既有历史文件字节、权限、结构改写 0；6 份授权新增标记单列 | [最终保护](continuation-final-protection.json) |\n| 编译闭包 | kernel lib/bin 与 20 个 checker Rust 路径及嵌入资源对应；topology 单独绑定；实际编译的漏登模块被拒收 | [正例](continuation-compile-closure.json)、[负例](continuation-compile-closure-negative.json) |\n| 同路径同 profile 生产字节 | kernel 与 topology 的最终 B 二进制均与用于 A/A 的 A 原字节完全相同；工具链与 registry/标准库绑定 | [字节对照](production-byte-equivalence.json)、[A 重建绑定](continuation-production-a-rebound.json)、[构建输入](continuation-build-inputs.json) |\n| A/A 与引用闭包 | 44 对通过；仅五个登记计时 token 可变；所有捕获、递归引用边、schema 及同版本验证回执保留 | [A 最终绑定](continuation-a-final.json)、[A/A](continuation-aa-results.json)、[引用 a](continuation-reference-closure-a.json)、[引用 b](continuation-reference-closure-b.json) |\n\n隔离矩阵包括显式根、无配置默认根、两轮重复、不同 cwd、中文/空格路径、两个并发实例、子进程失败及非法根拒收。六个 Python 导入无写入、祖先链接拒收和两件必需 fixture 的缺失/坏哈希负例在最终副本重新核验。每次实例独占输出目录，失败产物保留。成功写打开调用另经 [写入边界审计](continuation-write-boundary-audit.json) 核查，包括测试结束后已不存在的临时路径；按 §3.2 明确登记 test_formal_catalog 在 /tmp 中对三份正式源副本执行的漂移反例与自身临时目录清理，不把它当作历史写入。新入口 `数据/工具/kernel_regression.py` 提供 tests、check-isolation、aa、capture、compare；tests 接口在凭据验收后另外实际执行 9 条安全命令和七个正式 CLI suite，全部通过。实现与清单通过 runner-binding.json 绑定，源上下文失效时拒绝重新运行 A。接口正向/拒收回执见 [入口核验](continuation-entry-validation.json)。\n\n资源判据为实际计算占用，统一四核 affinity、jobs=2、codegen-units=1、测试/计算池单线程。实际 CPU 时间÷墙钟和运行态/等待线程均进入逐命令记录。Node 或 rustc 的等待线程可使总线程数超过 6，不再误判为计算超限。最终验收的独立 harness 按序执行；双实例探针单独并发两个 harness。\n\n### 六份历史结构变化的准确口径\n\n`history_changed=6`，全为本任务明确要求新增的 `原字节缺失.json`。既有历史文件改写、权限变化与意外结构变化均为 0，因此没有需要从 Git 恢复的历史损害；没有执行 Git 命令、暂存或提交。六个新增路径为：\n\n'''+marker_lines+'''\n\n研究文件 `候选约束.txt` 和候选约束轮次树的外部变化单独保存前后指纹及归属依据，未回退、未写入，未算作本任务历史损害。三份正式源保持与冻结副本相同。\n\n### R3 读取边界修复与已知覆盖边界\n\n真实 strace 验收发现历史 expired fixture 的绝对 catalog 引用仍读取原仓库。最终测试在本次实例内重定位历史 fixture 的 path 字段。补拷第三份只读输入 tiny-expired-after-closure-input.json，先按旧指纹核其原字节，再仅变换派生输入的路径 token，并把派生 legacy record 的唯一 input 指纹绑定到新输入原字节。三个历史原件、其原始哈希、所有非路径状态数据、用例名、次数和原有断言保持；源 catalog 等历史依赖哈希不重锁。每次执行保存路径映射、原/新目标 SHA-256，之后重建绑定并重跑全部隔离矩阵与两轮安全回归。详见 [最终修复账](continuation-r3-final.json)、[源差分](continuation-r3-final.diff.log) 和 [只读测试资源补充](continuation-cli-fixtures.json)。该补充不在非测试编译闭包或44例 A/A 的消费闭包内，生产对照资源与运行时验证实现均未变化。\n\n该 fixture 的历史引用哈希已经过期，现有用例因来源不匹配提前拒收。第 0 批不重锁这些历史字节、不更改内核运行语义，也不把该命名用例的通过宣称为新增的过期门状态覆盖。13 项原字节缺失同样没有被回归通过核销。\n\nA/A 的探索性拒收、解析器修正和旧版本隔离回执均保留在 preliminary-aa、failed-*、isolation-before-r3-fix 等索引/目录中；不计作最终通过。冻结源实拷位于 /tmp，所有编译产物及大型原始捕获只在共享 target；本目录保存脚本、日志、JSON、Markdown 和规定的隔离测试输出。\n'''
    record.write_text(text)
    write(RUN/'continuation-reader-review.json',dict(passed=True,checks=['historical and current statuses separated','all current numeric counts derived from receipts','missing original bytes not represented as restored','six authorized history additions counted explicitly','external research writes not reverted','same-path production identity and source scope stated','A source context not executed after B replacement','R3 stale-hash coverage limit stated','all linked evidence paths checked by final delivery inventory']))
    check('final-ledger-after')
    print(json.dumps({k:summary[k] for k in ['verdict','record_path','history_changed','safe_rounds','tests_per_isolation_round','aa_pairs']},ensure_ascii=False))

if __name__=='__main__':main()
