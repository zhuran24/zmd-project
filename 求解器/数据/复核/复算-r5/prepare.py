#!/usr/bin/env python3
"""冻结本轮输入和被审材料，所有写入限定在本轮证据目录。"""
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone

ROOT = Path('/home/zhuran24/zmd-research-fresh')
OUT = ROOT / '求解器/数据/复核/复算-r5'
SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
TASK = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
if (OUT / '输入指纹.json').exists():
    raise SystemExit('已有本轮输入指纹，拒绝覆盖冻结快照。复现请运行 recompute.py。')
paths = [ROOT / name for name in ('《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt')]
paths += [SOURCE / name for name in ('design.py', 'machines.csv', 'channels.csv', 'fanout.json', 'scc.py')]
paths += [TASK / name for name in ('任务书.md', '任务书2.md', '任务书3.md')]
paths += [ROOT / '求解器' / name for name in ('Cargo.toml', 'Cargo.lock')]
paths += [p for p in (ROOT / '求解器/crates/topology').rglob('*') if p.is_file()]
paths += [p for p in (ROOT / '求解器/数据/工具').glob('*.py')]
paths += [ROOT / '求解器/数据' / name for name in ('送料契约.md', '规则覆盖表.md', '修订记录.md', '正式静态目录.json')]
paths += [p for p in (ROOT / '求解器/数据/候选B').glob('*') if p.is_file()]
paths += [p for p in (ROOT / '求解器/数据/修订验证/r4').glob('*') if p.is_file()]
paths += [ROOT / '求解器/数据/样例/混做粉碎机两下游-运行记录.json', ROOT / '求解器/规格/内核输入修订验证-r3/运行回归结果.json']
records = []
for path in paths:
    if path.is_relative_to(ROOT):
        rel = path.relative_to(ROOT)
    elif path.is_relative_to(SOURCE):
        rel = Path('原始候选B') / path.name
    else:
        rel = Path('任务依据') / path.name
    target = OUT / '输入快照' / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    target.write_bytes(data)
    records.append({'原路径': str(path), '快照': str(target.relative_to(OUT)), '字节数': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
(OUT / '输入指纹.json').write_text(json.dumps({'时间': datetime.now(timezone.utc).isoformat(), '文件': records}, ensure_ascii=False, indent=2) + '\n')
print(f'冻结 {len(records)} 个输入文件；尚未读取被审报告内容。')
