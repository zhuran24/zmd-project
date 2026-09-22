"""Rule-based arithmetic and a stated two-input FIFO model, not the game kernel."""
from pathlib import Path
from hashlib import sha256
from itertools import product
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
DER = OUT.parent

def read(p):
    return json.loads(p.read_text())

def save(name, data):
    (OUT / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

files = [ROOT/n for n in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']]
files += [DER/n for n in ['回路总数决定论-v2.md', '回路总数决定论.md', '总纲-流量存量相位.md',
    '复核/独立推导-opus.md', '复核/否证-1.md', '复核/否证-2.md']]
files += [ROOT/'求解器/会议成果/主会话三审-0920.md',
    Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-主线.md')]
save('inputs', [dict(path=str(p), sha256=sha256(p.read_bytes()).hexdigest(), lines=len(p.read_text().splitlines())) for p in files])

prior = DER/'复核/否证-1-证据'
snap = read(prior/'正式文件与被审66行.json')
for row in snap['sources']:
    current = Path(row['path']).read_text()
    assert sha256(row['text'].encode()).hexdigest() == row['sha256']
    assert current.startswith(row['text']) if Path(row['path']).name == '回路总数决定论.md' else current == row['text']
report = (DER/'复核/否证-1.md').read_text()
assert json.loads(report.split('```json\n')[1].split('\n```')[0]) == read(prior/'结构化结论.json')
assert (prior/'被审66行.md').read_text() == ''.join((DER/'回路总数决定论.md').read_text().splitlines(True)[:66])
# Execute prior geometry/arithmetic assertions, omit its sole write/print tail.
source = (prior/'检查局部证据.py').read_text().split('msg=')[0]
exec(compile(source, str(prior/'检查局部证据.py'), 'exec'), {'__file__': str(prior/'检查局部证据.py')})

checks = {'prior_evidence': 'snapshot/hash/embedded_verdict/geometry/arithmetic checked; no prior kernel trace',
          'denial_2_evidence_files': [str(p) for p in (DER/'复核/否证-2-证据').rglob('*') if p.is_file()]}
n = 0
for ah, ag, h, g, ih, ig, io in product(range(3), repeat=7):
    i = ih + ig + io
    dn, dh, dg = h-g-i, ah-h-ih, ag-g-ig
    assert dn + dh - dg == ah-ag-i-ih+ig
    n += 1
checks['K_identity_assignments'] = n
checks['first_clearance'] = [{'machines':16, 'different_species_full':m, 'clearance':32+48*m} for m in [0,1,16]]
checks['ordinary_slots_capacity'] = 48*100
checks['completed_cache_capacity'] = 32+2*16
checks['illustrative_differences'] = [4800-d-128 for d in [32,80,800]]
assert checks['illustrative_differences'] == [4640,4592,3872]

def fifo(start, word, ticks=180):
    """One item per tick, 2A+B, one-tick processing, free output, fixed FIFO word.
    This is explicitly supplied word service, not a proof that R29 generates it.
    """
    a,b = start
    accepted = done = 0
    busy = False
    trace = []
    for t in range(ticks):
        if busy:
            done += 1
            busy = False
        # An available batch opens before admission; repeat after admission.
        if a>=2 and b>=1:
            a-=2; b-=1; busy=True
        item = word[accepted % len(word)]
        moved = (a<50 if item=='A' else b<50)
        if moved:
            if item=='A': a+=1
            else: b+=1
            accepted += 1
        if not busy and a>=2 and b>=1:
            a-=2; b-=1; busy=True
        trace.append(dict(t=t, a=a, b=b, head=word[accepted%len(word)], accepted=accepted,
                          batches_completed=done, working=busy))
    return trace

bad = fifo((50,0), 'AAB')
good = fifo((50,0), 'BAA')
full = fifo((50,50), 'AAB')
assert bad[-1]['accepted']==bad[-1]['batches_completed']==0
assert good[-1]['accepted']==180 and good[-1]['batches_completed']==60
assert full[-1]['accepted']==180
save('fifo-stated-model', {'scope':'Independent supplied-word model, NOT kernel execution or complete layout',
    'blocked':bad, 'released':good, 'full_inputs':full})
checks['fifo_results'] = {k: v[-1] for k,v in [('blocked',bad),('released',good),('full_inputs',full)]}
prefix=[]
for word in ['AAB','ABA','BAA']:
    d=0; vals=[0]
    for x in word*10:
        d += 1 if x=='A' else -2
        vals.append(d)
    assert max(vals)-min(vals)==2
    prefix.append(dict(word=word, min=min(vals), max=max(vals), interval_difference_bound=2))
checks['weighted_prefix_discrepancy'] = prefix
checks['full_input_Z'] = {'initial':-50, 'A_head_deadlock_Z':50, 'B_head_deadlock_Z':[-100,-99],
    'sufficient_prefix_D_integer_range':[-48,99], 'symmetric_abs_D_lt_48_is_sufficient_for_no_input_deadlock':True,
    'limitations':'requires ongoing FIFO supply and output release; no guarantee of target throughput'}

catalog=read(ROOT/'求解器/数据/正式静态目录.json')
checks['kernel_formal_hashes']=[dict(path=r['path'], catalog_sha256=r['sha256'],
    current_sha256=sha256((ROOT/r['path']).read_bytes()).hexdigest()) for r in catalog['sources']]
checks['kernel_attempts']=read(OUT/'probe-results.json')
assert all(x['status']=='invalid_input' and not x['trajectory_executed'] for x in checks['kernel_attempts'].values())
save('checks',checks)
print(json.dumps({'status':'pass', 'meaning':'arithmetic, prior evidence and stated FIFO model only; kernel blocked before execution'},ensure_ascii=False))
