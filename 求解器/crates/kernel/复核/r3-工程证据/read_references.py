"""完整读取任务书与本轮直接引用，保存读取清点而不复制来源正文或仓库。"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path('/home/zhuran24/zmd-research-fresh')
OUT = ROOT / '求解器/crates/kernel/复核/r3-工程证据'
TASK = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
MEETING = Path('/home/zhuran24/文档/会议2全套/会议目录')
paths = set((ROOT / '求解器/规格').glob('*.md'))
paths.update((ROOT / '求解器/规格/第五轮规格修订-r8').glob('*'))
paths.update((ROOT / '求解器/规格/第五轮规格修订').glob('*'))
paths.update([ROOT / '求解器/crates/kernel/evidence/round5' / name for name in ['最终回复.json','final-audit.log']])
paths.update([TASK / x for x in ['任务书.md','任务书2.md','任务书3.md','任务书4.md','任务书5.md','gptpro_评审摘录.md','round3_state.json']])
paths.update([MEETING / x for x in ['纪要.md','seat-opus-1/共识草案-v45-5c9e556a.md','seat-opus-3.md','seat-opus-4/design.py','seat-opus-4/channels.csv','seat-opus-4/machines.csv','seat-opus-4/fanout.json','seat-opus-4/scc.py','seat-opus-4/候选-准入口阻断是动态的.txt','seat-opus-4/候选-轮询均分松.txt']])
paths.update([ROOT / x for x in ['求解器/规格/复核/完整性批评.md','求解器/规格/复核/完整性批评-2.md','求解器/规格/复核/完整性批评-3.md','求解器/规格/复核/选择点独立清单-r3.md','求解器/crates/kernel/复核/完整性批评-内核.md','求解器/数据/送料契约.md','求解器/数据/规则覆盖表.md']])
# 当前正文的一层显式引用也完整读取；二进制和构建目录不作为规则来源。
extra = set()
for p in paths:
    if p.is_file() and p.suffix == '.md':
        content = p.read_text()
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if target.startswith(('http:', 'https:', '#')):
                continue
            q = (p.parent / target.split('#')[0]).resolve()
            if q.is_file():
                extra.add(q)
paths.update(extra)
rows = []
for p in sorted(paths):
    if not p.is_file():
        rows.append({'path':str(p),'exists':False})
        continue
    if any(x in p.parts for x in ['target','.cargo-home','registry','.git','模拟器']):
        continue
    content = p.read_bytes()
    text = content.decode('utf-8')
    row = {'path':str(p),'exists':True,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'lines':len(text.splitlines())}
    if p.suffix == '.json':
        value=json.loads(text)
        row['json_type']=type(value).__name__
        if isinstance(value,dict):row['top_level_keys']=list(value)
    elif p.suffix == '.md':
        row['sections']=[line for line in text.splitlines() if line.startswith('#')]
    rows.append(row)
(OUT/'引用文件读取清点.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'read_files':sum(x['exists'] for x in rows),'missing':[x['path'] for x in rows if not x['exists']],'bytes':sum(x.get('bytes',0) for x in rows)},ensure_ascii=False))
