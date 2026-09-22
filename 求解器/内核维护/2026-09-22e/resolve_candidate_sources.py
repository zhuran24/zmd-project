#!/usr/bin/env python3
"""仅将已消失的临时来源移指到 SHA 完全一致的仓库存档。"""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
p=R/'数据/候选B/来源清单.json';rows=json.loads(p.read_text());changes=[]
archive=R/'规格/复核/内核输入/复核-r4-可导出性-证据/任务依据'
for row in rows:
 if not Path(row['path']).exists():
  dest=archive/Path(row['path']).name
  assert hashlib.sha256(dest.read_bytes()).hexdigest()==row['sha256']
  changes.append({'before':row['path'],'after':str(dest),'sha256':row['sha256']})
  row['path']=str(dest)
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
lock=json.loads((O/'relock.json').read_text());lock['relocated_byte_identical_sources']=changes
(O/'relock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n')
# 转换器再次执行也使用这一组可回核来源，防止重生失效 /tmp 路径。
p=R/'数据/工具/convert_candidate_b.py';s=p.read_text()
old="Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')"
assert old in s
s=s.replace(old,"(ROOT/'规格/复核/内核输入/复核-r4-可导出性-证据/任务依据')")
p.write_text(s)
print(json.dumps(changes,ensure_ascii=False,indent=2))
