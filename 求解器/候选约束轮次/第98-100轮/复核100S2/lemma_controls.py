#!/usr/bin/env python3
"""复核100S2：lemma_bfs 的反向对照单独运行（主穷举结果见 lemma_bfs.json）。"""
import json
from lemma_bfs import check
out = []
for ls, de, dl, mg, note in [((1,) * 6, (0,) * 6, 5, 8, '六口期限提前一步：应报期限违例'),
                             ((2, 2, 1), (2, 2, 0), 4, 8, '三口2,2,0期限提前一步：此例不紧，可不报'),
                             ((1,) * 6, (0,) * 6, -1, 5, '六口、相邻轮只隔5步（违反前提）：应报补货前消费'),
                             ((1,) * 6, (0,) * 6, -1, 8, '六口、相邻轮至少隔8步：不应报补货前消费')]:
    r = check(ls, de, (), allow_skip=False, control=True, deadline=dl, min_gap=mg)
    out.append(dict(note=note, lengths=ls, deltas=de, deadline=dl, min_gap=mg, ok=r['ok'], states=r['states'], first=r['viol'][:1]))
    print(json.dumps(out[-1], ensure_ascii=False), flush=True)
json.dump(out, open('lemma_controls.json', 'w'), ensure_ascii=False, indent=1)
