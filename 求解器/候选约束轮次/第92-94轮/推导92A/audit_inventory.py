#!/usr/bin/env python3
"""Read only the fixed premises; keep the inventory beside this program."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
SNAP = OUT.parent / '前提快照'
lines = (SNAP / '求解约束.txt').read_text().splitlines()
items = []
for i, line in enumerate(lines, 1):
    if line and not line[0].isspace() and '：' in line and not line.endswith('：'):
        name, text = line.split('：', 1)
        items.append(dict(id=f'N{len(items)+1:02}', line=i, name=name,
                          text=text, basis=lines[i].strip().removeprefix('据：')))
terms = ['阻尼', '存货优先级', '判定次序', '判定先后', '同一时刻']
matches = []
for i, line in enumerate(lines, 1):
    if any(term in line for term in terms):
        entry = max((x for x in items if x['line'] <= i), key=lambda x: x['line'])
        matches.append(dict(line=i, text=line, terms=[t for t in terms if t in line], item=entry['id']))
# An independent regex scan verifies the literal line inventory.
other = [i for i, line in enumerate(lines, 1) if re.search('|'.join(terms), line)]
assert other == [x['line'] for x in matches]
requested = {'N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N41', 'N49', 'N51'}
# N56 has the synonymous obsolete observation boundary, not a literal match.
review = requested | {m['item'] for m in matches} | {'N56'}
data = dict(snapshots=[dict(name=p.name, lines=len(p.read_text().splitlines()),
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in sorted(SNAP.iterdir()) if p.is_file()],
            entry_count=len(items), exact_match_line_count=len(matches),
            exact_match_entry_count=len({m['item'] for m in matches}),
            matches=matches, review_ids=sorted(review), items=[x for x in items if x['id'] in review])
(OUT / 'inventory.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: v for k, v in data.items() if k not in ('snapshots', 'matches', 'items')}, ensure_ascii=False))
