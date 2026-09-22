from pathlib import Path
import re
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
(R/'数据/候选B/校验报告.md').write_bytes((O/'candidate-b-report.log').read_bytes())
p=R/'数据/候选B/转换说明.md';s=p.read_text().replace('日期：2026-09-19。状态：第四轮统一目录门禁及 feeding-v2 源表转换核对完成','日期：2026-09-22。状态：72 条正式约束目录与来源引用已同步，feeding-v2 契约未变')
s=s.replace('（56 条，算术计数）','（72 条，算术计数）')
s=s.replace('任务书与顾问评审的实际路径也在清单中。','任务书与顾问评审的实际路径也在清单中；原临时路径已迁至仓库内 SHA-256 完全一致的历史存档，重定位明细见[本轮重锁记录](../../内核维护/2026-09-22e/relock.json)。')
p.write_text(s)
p=R/'数据/候选B/验证记录.md';s=p.read_text()
s=s.replace('日期：2026-09-19。状态：第四轮契约目录门禁修订与自查完成；当前目录及候选契约字节保持不变。本文记录静态工具验证，不是游戏运行实测。','史料截止日期：2026-09-19。本节保存第四轮契约目录门禁验证结果及其版本边界；其中计数、目录指纹与测试结果均为当时快照，不代表现行版本。本文记录静态工具验证，不是游戏运行实测。')
s=s.replace('# 候选 B 交付验证记录\n','# 候选 B 交付验证记录\n\n现行目录为 `2026-09-22-r23-constraints-72`；候选 B 当前报告为 4924 项通过、0 项失败、75 项不能静态检，其中 72 项是正式约束运行/几何义务。当前执行与限制见[2026-09-22e 记录](../../内核维护/2026-09-22e/记录.md)；下文是旧轮史料。\n\n## 2026-09-19 历史验证\n')
p.write_text(s)
# 当前总览仅校正条款数量，不改其历史任务/结论。
p=R.parent/'思路.txt';s=p.read_text().replace('求解约束里的 56 条','求解约束里的 72 条').replace('求解约束 56 条','求解约束 72 条');p.write_text(s)
print('candidate report and active count references updated; old evidence logs retained')
