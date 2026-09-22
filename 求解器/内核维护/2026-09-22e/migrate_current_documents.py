#!/usr/bin/env python3
"""同步当前入口的源标签；旧推导行号明确绑定被审快照，植物入库依据按条名迁移。"""
from pathlib import Path
import json,re
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
cat=json.loads((R/'数据/正式静态目录.json').read_text());changed=[]
phrase='本次现行依据为'+ '、'.join(label+'`'+source['sha256'][:12]+'`' for label,source in zip(['规则','任务','约束'],cat['sources']))
for p in (R/'规格').glob('*.md'):
 s=p.read_text()
 if '本次现行依据为' not in s:continue
 new=re.sub(r'本次现行依据为规则`[^`]+`、任务`[^`]+`、约束`[^`]+`',phrase,s)
 if new!=s:
  new=new.replace('日期：2026-09-21。状态：','日期：2026-09-22。状态：正式来源标签已同步；')
  p.write_text(new);changed.append(str(p.relative_to(R)))
# 转移定义该节保留旧独立证明的来源时间，不把其旧指纹称为当前规则。
p=R/'规格/受限转移定义.md';s=p.read_text().replace('规则SHA-256为 `d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a`','该节原证明绑定的规则SHA-256为 `d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a`；现行正式源指纹见运行语义§1')
p.write_text(s)
p=R/'规格/推导/回路总数决定论-v2.md';s=p.read_text()
s=s.replace('行号按本轮现行文件计。三份 SHA-256 分别为：','下列行号与 SHA-256 绑定 2026-09-21 被审快照；现行正式文件见[运行语义](../运行语义.md)§1，2026-09-22 迁移按条款名定位。被审快照三份 SHA-256 分别为：')
s=s.replace('C66：“种植机恰 32 台时植物系物品也不入库”','现行约束·非成品零入库：任意种植机台数的达标循环中植物系物品零入库')
s=s.replace('日期：2026-09-21。状态：','日期：2026-09-22。状态：植物零入库依据已迁移至现行「非成品零入库」；')
p.write_text(s);changed.append(str(p.relative_to(R)))
p=R/'规格/推导/总纲-流量存量相位.md';s=p.read_text()
s=s.replace('R、T、C及其现行指纹见第6节。','R、T、C行号及第6节指纹绑定2026-09-21被审快照；现行正式源见[运行语义](../运行语义.md)§1，2026-09-22零入库迁移按条款名定位。')
s=s.replace('恰32台种植机的达标循环按C66、70有植物零入库；按C74，','任意种植机台数的达标循环按现行约束·非成品零入库有植物零入库；种植机恰32台时，按约束·回路存量（旧C74），')
s=s.replace('一般增机域及过渡段保留实际I；','过渡段保留实际I；')
s=s.replace('恰32种植机的循环零入库、一般过渡的实际入库','任意种植机台数的达标循环零入库、一般过渡的实际入库')
s=s.replace('日期：2026-09-21。状态：','日期：2026-09-22。状态：植物零入库依据已迁移至现行「非成品零入库」；')
p.write_text(s);changed.append(str(p.relative_to(R)))
p=R/'规格/推导/三种相位不改产量-v2.md';s=p.read_text()
s=s.replace('约束第66、70行在恰32种植机的达标循环给零入库；其他台数及过渡保留实际入库项。','现行约束·非成品零入库在任意种植机台数的达标循环给植物零入库；过渡保留实际入库项。')
s=s.replace('只在有相应依据的配置中把植物入库项置零。','达标循环按现行约束·非成品零入库把植物入库项置零，不依赖种植机台数；过渡段仍须记录实际入库。')
# 标注旧引用基线，条件式的原文不篡改成无条件结论。
lines=s.splitlines();lines.insert(4,'来源迁移（2026-09-22）：本文旧行号与旧指纹属于被审快照；现行正式源见[运行语义](../运行语义.md)§1。植物零入库依现行「非成品零入库」适用于任意台数的达标循环，旧32台数值特例仍保留前件。')
p.write_text('\n'.join(lines)+'\n');changed.append(str(p.relative_to(R)))
(O/'current-document-migration.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(changed,ensure_ascii=False))
