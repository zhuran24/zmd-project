#!/usr/bin/env python3
"""Canonicalize records and attach evidence/screening decisions without losing raw data."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
pool = ROOT / 'pool.jsonl'
raw = pool.read_text()
(ROOT / 'pool.raw.jsonl').write_text(raw)
rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
parent = list(range(len(rows)))

def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i

def join(a, b):
    a, b = find(a), find(b)
    if a != b:
        parent[b] = a

seen = {}
for i, row in enumerate(rows):
    title = re.sub(r'[^a-z0-9]', '', row['title'].lower())
    ids = [('key', row['key'].lower()), ('title', title)]
    if row.get('doi'):
        ids.append(('doi', row['doi'].lower()))
    if row.get('arxiv'):
        ids.append(('arxiv', row['arxiv'].lower()))
    for identity in ids:
        if identity in seen:
            join(i, seen[identity])
        else:
            seen[identity] = i

groups = {}
for i, row in enumerate(rows):
    groups.setdefault(find(i), []).append(row)

evidence_body = (ROOT / '证据.md').read_text().split('## 文献证据', 1)[1]
evidence = [line for line in evidence_body.splitlines() if line.startswith('- [')]
labels = []
for number, line in enumerate(evidence, 1):
    tokens = {x.strip().lower() for x in line[3:line.index(']')].split('；')}
    labels.append((number, tokens))

def identities(row):
    out = {row['key'].lower()}
    if row.get('doi'):
        out.add(row['doi'].lower())
    if row.get('arxiv'):
        out.add('arxiv:' + row['arxiv'].lower())
    return out

def exclusion_reason(row):
    title = row['title'].lower()
    if any(x in title for x in ['galton', 'general trees', 'walks on trees', 'range and speed',
                                'spiral', 'semi-infinite', 'directed covers', 'recurrent rotor-router configurations']):
        return '空间回返/无穷图随机初态问题，不是有限工厂的时间周期或启动保证'
    if any(x in title for x in ['rotor blade', 'hovering vehicle', 'twin rotor', 'fatigue',
                                'non-abelian', 'anyons', 'neural networks', 'social networks',
                                'phase field', 'fungi', 'noise', 'avic', 'bird', 'jurisdiction',
                                'protective measures', 'object marking', 'scent-marking', 'phonotactic',
                                'face detection', 'osteosarcoma', 'romanticism', 'block printing']):
        return '同词异义或对象无关；摘要不含本块的启动/全初态周期产率方法'
    if 'pushdown' in title:
        return '递归栈无限状态游戏；本块没有递归栈，有限状态方法已单独保留'
    if 'invited talk' in title:
        return '同一windows研究的演讲版本，正式论文已保留'
    if any(x in title for x in ['stochastic', 'markovian', 'unreliable', 'failure', 'distributed processing times',
                                'overflow', 'hyper-exponentially', 'fluid queue', 'vacation policy']):
        return '随机分布/期望性能或故障模型，摘要未提供本块所需逐确定性循环保证；相关边界代表文献已保留'
    if any(x in title for x in ['partial order', 'partial-order', 'stubborn set', 'stutter-preserving']):
        return '已读摘要涉及定性可达/安全/parity/stutter性质，未找到保交付计数与经过时间的平均收益结论；带权候选另保留'
    if any(x in title for x in ['byzantine', 'ledger', 'parliament', 'ntp', 'internet time', 'virus',
                                'exascale', 'critical infrastructure', 'crawler', 'kubernetes', 'openfaas']):
        return '分布式共识/平台故障或网络服务对象，与固定游戏单位的物流启动不同'
    if any(x in title for x in ['synchronous unison', 'stabilizing unison', 'asynchronous unison', 'synchronous vs.']):
        return '同步协议主题重复；已保留Dijkstra与2025强调度收敛代表，未见可由游戏单位实现的额外构造'
    return '标题和可得摘要未给本块可操作的新启动或全周期产率内容；通用背景/其他块方法，不纳入证据保留组'

canonical = []
screening = []
for group in groups.values():
    # Prefer OpenAlex metadata; preserve every alternative identity and origin.
    group.sort(key=lambda x: (not x['key'].startswith('W'), -len(x.get('abstract', ''))))
    record = dict(group[0])
    record['aliases'] = sorted(set().union(*(identities(x) for x in group)) - identities(record))
    record['found_by_all'] = sorted({x.get('found_by', '') for x in group if x.get('found_by')})
    ids = set().union(*(identities(x) for x in group))
    matches = [n for n, tokens in labels if tokens & ids]
    record['evidence_rows'] = matches
    record['screening'] = 'retained' if matches else 'excluded'
    record['screening_reason'] = '已有逐篇对应关系和边界证据；包括明确标注的待核/背景项' if matches else exclusion_reason(record)
    canonical.append(record)
    screening.append({key: record[key] for key in ['key', 'title', 'screening', 'screening_reason', 'evidence_rows']})

covered = {n for row in canonical for n in row['evidence_rows']}
if covered != set(range(1, len(evidence) + 1)):
    raise SystemExit('Unmatched evidence rows: ' + str(set(range(1, len(evidence) + 1)) - covered))
for path, values in [(pool, canonical), (ROOT / 'screening.jsonl', screening)]:
    path.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in values))
print(json.dumps({'raw_records': len(rows), 'canonical_records': len(canonical),
                  'retained_groups': len(evidence), 'retained_records': sum(bool(x['evidence_rows']) for x in canonical)}, ensure_ascii=False))
