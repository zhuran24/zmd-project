from helpers import *
from guard import REPO,SOURCES,digest,guard
guard('reader-fixes-before')
edit('规格/四件前置义务对照.md',[
    ('规则`52df4c12ce90`','规则`'+digest(REPO/SOURCES[0])[:12]+'`'),
    ('约束`a67c18dec5f6`','约束`'+digest(REPO/SOURCES[2])[:12]+'`'),
    ('桥接器每格 1 为已采纳约束的记账口径，非规则直引；规则例外是否也覆盖容量、该口径能否覆盖全部合法状态尚缺证明（T14）。若只实现该口径须标受限模型；不能以容量未给即断言无限，也不能声称已有统一有限界。','桥接器每对边各一格、上限1由规则L59/L63直接给出，两轴调度独立（T14）；来路只在本轴相邻单位的有限集合中取值。该局部容量界不构成全状态有限证明。')])
p=ROOT/'规格/规则覆盖表.md';text=p.read_text();lines=text.splitlines();old=(OUT/'before/规格/规则覆盖表.md').read_text().splitlines()
# Source-line numbers in the constraints table are unrelated to game-rule row numbers.
for i,line in enumerate(lines):
    if '| 约束·' in line and any(line.startswith(f'| {n} |') for n in [24,59,63]):
        prefix=line.split('|')[1].strip()
        reference=next(l for l in old if l.startswith(f'| {prefix} |') and '| 约束·' in l)
        lines[i]=reference
text='\n'.join(lines)+'\n'
text=text.replace('零时移动不裁定同刻闭包或非运输停留','保存桥物品来路，禁止立即返回；零时移动不裁定同刻闭包或非运输停留')
write(p,text)
edit('crates/kernel/周期键读取审计.md',[
    ('日期：2026-09-21。','日期：2026-09-22。'),
    ('d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a',digest(REPO/SOURCES[0])),
    ('| 非运输 entered_at |','| 桥物品 last_unit | compute_physical 比较目标单位与直接来路；validate_inventory 核本轴真实入边；成功移入桥写源单位 | 原值保留，不随年龄成熟、窗口重置或循环平移清除；禁止立即返回依赖它。规则L24/L63。 |\n| 非运输 entered_at |'),
    ('保留实际环序和位置；只对以身份索引的无序列表排序。','保留实际环序和位置；桥按(unit,axis,side)区分四个调度辖域，规范排序也包括axis。只对以身份索引的无序列表排序。')])
guard('reader-fixes-after')
