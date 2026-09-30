"""终审探针：纯链中插入 0—3 个相邻桥接器，只读调用已编译的差分观察器（内存运行）。"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
sys.path[:0] = [str(ROOT/'数据/工具')]
from step_inputs import generate
from step_samples import u
SAMPLES = ROOT/'数据/样例/步进/差分'
EXE = Path(sys.argv[1])
jobs = []
for k in range(4):
    specs = [u('source','仓库取货口',10,0)]
    for y in range(1,7):
        kind = '桥接器' if 3 <= y < 3+k else '传送带'
        specs.append(u(f'x{y}', kind, 11, y))
    specs += [u('crusher','粉碎机',10,7), u('power','供电桩',14,7), u('out','传送带',11,10), u('core','协议核心',10,11)]
    raw = generate({'units': specs}, SAMPLES)
    jobs.append(dict(name=f'bridges-{k}', input=raw, steps=480, base=str(SAMPLES), config=str(ROOT/'规格/内核配置-v2.json')))
p = subprocess.run([str(EXE)], input='\n'.join(json.dumps(j, ensure_ascii=False) for j in jobs)+'\n', text=True, capture_output=True)
assert p.returncode == 0, p.stderr
for line in p.stdout.splitlines():
    r = json.loads(line)
    if 'error' in r:
        print(r['name'], 'ERROR', r['error']); continue
    starts = [i for i, ev in enumerate(r['events']) for e in ev if e['phase']=='start' and e['subject']=='crusher']
    gaps = [b-a for a, b in zip(starts, starts[1:])]
    tail = gaps[-20:]
    print(r['name'], 'layers', {k:v for k,v in r['graph']['layers'].items()}, 'order', r['graph']['order'])
    print('   starts', len(starts), 'first', starts[:3], 'tail gaps', tail, 'mean tail', sum(tail)/len(tail) if tail else None)
