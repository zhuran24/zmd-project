"""Archive the three authorized premises and the material read for this report."""
from pathlib import Path
import hashlib, json, datetime

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SNAP = OUT.parent / '前提快照'
items = [(SNAP / n, 'formal premise') for n in (
    '《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt')]
items += [(ROOT / n, 'background, not a premise') for n in (
    '候选约束.txt', '候选简化.txt', '候选充分条件.txt', '讨论整理.txt')]
data = {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sources': []}
for p, role in items:
    raw = p.read_bytes()
    data['sources'].append({'path': str(p), 'role': role,
        'sha256': hashlib.sha256(raw).hexdigest(), 'text': raw.decode('utf-8')})
(OUT / 'inputs.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(json.dumps([{k:v for k,v in s.items() if k != 'text'} for s in data['sources']], ensure_ascii=False, indent=2))
