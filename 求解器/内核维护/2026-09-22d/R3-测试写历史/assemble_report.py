#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
rows=json.loads((OUT/'file_audit.json').read_text())
evidence=[r for r in rows if '/crates/kernel/evidence/' in r['path']]
assert len(evidence)==166
restore=[];details=['# evidence 逐文件判定\n\n路径相对于 `求解器/crates/kernel/evidence/`。M/A 为提交中实际修改/新增。历史输入也属于旧运行材料。\n\n| 路径 | a7539f5 | 220f7b6 | 性质 | 恢复版本 |\n|---|---|---|---|---|\n']
for r in evidence:
    p=r['path'].split('/crates/kernel/evidence/')[1]
    changes={x['commit']:x['status'] for x in r['changes']}
    if r['base_sha256']:
        assert r['base_equals_pre'] and changes['a7539f5']=='M'
        kind='旧历史证据被测试再生成覆盖';version='f8f6129（7da52a7 等价）'
        restore.append(dict(path=r['path'],source_commit='f8f6129',equivalent_commit='7da52a7',expected_sha256=r['base_sha256'],current_sha256=r['head_sha256'],reason=kind))
    else:kind='新增当前测试产物';version='无入库旧版本；保留/分运行归档'
    details.append(f"| `{p}` | {changes.get('a7539f5','—')} | {changes.get('220f7b6','—')} | {kind} | {version} |\n")
assert len(restore)==159
(OUT/'restore_manifest.json').write_text(json.dumps(dict(action_executed=False,files=restore),ensure_ascii=False,indent=2)+'\n')
(OUT/'逐文件判定.md').write_text(''.join(details))
others=[r for r in rows if r not in evidence]
assert len(others)==110
other=['# 其他证据路径逐文件判定\n\n全部为新增，未覆盖同路径旧文件。\n\n| 路径（相对于求解器） | 提交 | 判定 | 恢复 |\n|---|---|---|---|\n']
for r in others:
    assert len(r['changes'])==1 and r['changes'][0]['status']=='A'
    kind='有意新增的当前参考运行基线' if '参考运行记录' in r['path'] else '新增本轮维护脚本/日志/结果/说明'
    other.append(f"| `{r['path'].removeprefix('求解器/')}` | {r['changes'][0]['commit']} | {kind} | 无需恢复 |\n")
(OUT/'other_evidence_changes.md').write_text(''.join(other))
drift=[r for r in json.loads((OUT/'pre_day_hash_drift.json').read_text()) if not r['tracked']]
ignored=['\n## 9. 未跟踪历史文件的恢复依据（14 个）\n\n路径相对于 `crates/kernel/evidence/`；14 个原路径在 `f8f6129`、`7da52a7` 均无 Git blob，恢复不能指定该路径的 Git 版本。完整旧/新哈希见 `pre_day_hash_drift.json`。表中的目标哈希就是恢复验收条件。\n\n| 路径 | 目标 SHA-256 | 可用恢复来源 |\n|---|---|---|\n']
for r in drift:
    for rev in ('f8f6129','7da52a7'):
        assert subprocess.run(['git','-C',str(ROOT.parent),'cat-file','-e',rev+':求解器/'+r['path']],capture_output=True).returncode!=0
    matches=r['existing_exact_copy_candidates']
    source='；'.join('`'+p+'`（现存同哈希副本）' for p in matches) if matches else 'before.json 仅有哈希；本次未找到现存同哈希副本，需另查旧备份'
    ignored.append(f"| `{r['path'].split('/evidence/')[1]}` | `{r['before_sha256']}` | {source} |\n")
body=(OUT/'report_body.md').read_text().replace('第四节在其第 147–175 行','第四节在其第 119–144 行').replace('revision_r4_cli.py:10–11,20–22,39–40,143','revision_r4_cli.py:10–11,20–22,39–40,134').replace('convert_candidate_b.py:15,22,125–130','convert_candidate_b.py:15,22,124–130')
body+='\n## 8. 应恢复及新增文件完整清单\n\n下列 166 行与 `file_audit.json` 一一对应；其中 159 行明确指定恢复版本。所有路径相对于 `crates/kernel/evidence/`，恢复尚未执行。机器可读列表含每个文件的完整旧/新 SHA-256，见 `restore_manifest.json`。\n\n'
body+='| 路径 |'+''.join(details).split('| 路径 |',1)[1]
body+=''.join(ignored)
body+='\n## 10. 交付检查\n\n逐项核对：166 路径分类完整；159 恢复项的 f8f6129 与 7da52a7 字节一致；7 新增项不混入旧文件恢复；14 未跟踪漂移单列；第一次恢复三文件完整哈希仍匹配；所有恢复均未执行。本报告的当前事实与历史日志结果分开。工作树保护和读者视角复核结果见 `reader_review.json`。\n'
report=OUT.parent/'R3-测试写历史.md';report.write_text(body)
print(json.dumps({'report_path':str(report),'evidence_rows':len(evidence),'restore_files':len(restore),'other_evidence_rows':len(others),'untracked_drift':len(drift)},ensure_ascii=False))
