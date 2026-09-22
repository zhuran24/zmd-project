from pathlib import Path
R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
s = (R/'内核维护/2026-09-22c/relock.py').read_text()
s = s.replace("R=Path.cwd();O=R/'内核维护/2026-09-22c'", "R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent")
a=s.index("for row in d['sources']:"); b=s.index("hashes={",a)
s=s[:a]+"from importlib import import_module\nsys.path.insert(0,str(R/'数据/工具'))\nimport_module('formal_catalog').verify(d)\nassert d['version']=='2026-09-22-r23-constraints-72'\n"+s[b:]
s=s.replace("save(O/'relock.json'", "save(O/'relock.json'", 1)
a=s.index("save(O/'relock.json'")
s=s[:a]+'''# 候选 B 正式源/候选约束/目录引用更新；历史外部来源不能静默重指。
p=R/'数据/候选B/来源清单.json'; records=json.loads(p.read_text()); source_changes=[]
current_paths={str(R.parent/name) for name in [*hashes,'候选约束.txt']}|{str(R/'数据/正式静态目录.json')}
for ref in records:
 if ref['path'] in current_paths:
  new=sha(Path(ref['path']))
  if ref['sha256']!=new:source_changes.append({'path':ref['path'],'before':ref['sha256'],'after':new});ref['sha256']=new
save(p,records)
'''+s[a:]
s=s.replace("'inputs':rows,", "'inputs':rows,'candidate_b_sources':source_changes,")
(O/'relock.py').write_text(s)
s=(R/'内核维护/2026-09-22c/check_positive.py').read_text()
s=s.replace("R=Path.cwd();O=R/'内核维护/2026-09-22c'", "R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent")
s=s.replace('c252c5fae915e2e4002869d7830fff61a50407c47c2ffd9fa855ad0fc893879d','6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff')
s=s.replace("assert r.returncode!=0;rows", "assert r.returncode!=0;assert 'sha256' in (r.stdout+r.stderr).lower(),(r.stdout,r.stderr);rows")
(O/'check_positive.py').write_text(s)
