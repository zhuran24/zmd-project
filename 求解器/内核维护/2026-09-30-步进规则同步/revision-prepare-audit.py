"""沿用包三回源/覆盖表审计判据，仅替换本轮允许改动域与快照标签。"""
from guard import OUT
s=(OUT/'package3-audit.py').read_text()
s=s.replace('包三只读审计；由 run.sh audit 调用，前后复用3481文件原始基线。','修订只读审计；复用包三回源与逐轴投影判据，前后复用3481文件原始基线。')
s=s.replace("OLD=['74de", "OLD=['680acb480aa28443431e119c98e4cc45ca6abade1670c9a4a1283a77a7d199a2','74de")
a=s.index(' # 全量活动清单仅允许包三范围内变更');b=s.index(' inventory=scan(label)',a)
s=s[:a]+''' # 相对修订开工字节的显式允许域；其余旧输入、工具、源码与规格均保持。
 before=json.loads((OUT/'revision-active-before.json').read_text());after=active_snapshot()
 for rel in ['crates/kernel/README.md','crates/kernel/修订记录.md','内核维护/2026-09-30-步进规则同步/设计.md','内核维护/2026-09-30-步进规则同步/差分/diagnose.py']:
  after['求解器/'+rel]=digest(ROOT/rel)
 allowed=set('求解器/'+r for r in [
  'crates/kernel/src/input.rs','crates/kernel/src/graph.rs','crates/kernel/src/output.rs',
  'crates/kernel/src/tests_graph.rs','crates/kernel/src/tests_output.rs','crates/kernel/tests/reference.rs',
  '数据/工具/step_graph.py','数据/工具/step_inputs.py','数据/样例/历史说明.md',
  '规格/内核配置-v2.json','规格/运行语义.md','规格/内核输入.md','规格/内核输出.md',
  '规格/受限模型声明.md','规格/选择点参数轴.md','规格/修订记录.md','crates/kernel/修订记录.md',
  '内核维护/2026-09-30-步进规则同步/设计.md','内核维护/2026-09-30-步进规则同步/差分/diagnose.py'])
 allowed.update('求解器/'+r for r in json.loads((OUT/'revision-samples-final.json').read_text())['files'])
 delta=difference(before,after)
 assert not delta['added'] and not delta['deleted'],delta
 assert set(delta['changed'])<=allowed,delta
 # 30 份输入除配置 SHA 之外，其余语义字节对象与开工时相等。
 for rel in json.loads((OUT/'revision-samples-final.json').read_text())['files']:
  old=json.loads((OUT/'revision-before/求解器'/rel).read_text());new=json.loads((ROOT/rel).read_text())
  old['parameters']['axis_registry']['sha256']=new['parameters']['axis_registry']['sha256']
  assert old==new,rel
 save(label+'-active-after.json',after)
'''+s[b:]
s=s.replace("while (OUT/f'p3-audit{n:02d}.json').exists():n+=1", "while (OUT/f'revision-audit{n:02d}.json').exists():n+=1")
s=s.replace("label=f'p3-audit{n:02d}'", "label=f'revision-audit{n:02d}'")
s=s.replace("['bash','内核维护/2026-09-30-步进规则同步/run.sh','audit']", "['python3','-B','内核维护/2026-09-30-步进规则同步/revision-audit.py']")
(OUT/'revision-audit.py').write_text(s)
