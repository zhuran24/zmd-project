"""终审探针二：两相邻桥接器，遍历选支与环锚点；另比较建造次序。只读内存运行。"""
import json, subprocess, sys, copy
from pathlib import Path
ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
sys.path[:0] = [str(ROOT/'数据/工具')]
from step_inputs import generate, axis
from step_samples import u
SAMPLES = ROOT/'数据/样例/步进/差分'
EXE = Path(sys.argv[1])
def layout(k=2):
    specs = [u('source','仓库取货口',10,0)]
    for y in range(1,7):
        specs.append(u(f'x{y}', '桥接器' if 3 <= y < 3+k else '传送带', 11, y))
    specs += [u('crusher','粉碎机',10,7), u('power','供电桩',14,7), u('out','传送带',11,10), u('core','协议核心',10,11)]
    return specs
def order_axis(r):
    return next(v for k,v in [(a, r['parameters'][g][a]) for g in ('fixed','offline_mutable','fixedness_unproven') for a in r['parameters'][g]] if k=='step.order')['value']
jobs=[]
base = generate({'units': layout(2)}, SAMPLES)
so = order_axis(base)
print('default layer_choices', so['layer_choices'], 'cycles', so['cycle_layers'])
variants = [('default', copy.deepcopy(so))]
for comp, other in [('C|x4|vertical','C|x3|vertical')]:
    for anchor in ['C|x3|vertical','C|x4|vertical']:
        for layer in range(1,6):
            s = copy.deepcopy(so)
            s['layer_choices'] = [c if c['component']!=comp else {'component':comp,'downstream':other} for c in s['layer_choices']]
            s['cycle_layers'] = [{'component':anchor,'layer':{'value':str(layer),'category':'候选'}}]
            variants.append((f'{comp}->{other} anchor {anchor}={layer}', s))
for name, s in variants:
    r = copy.deepcopy(base)
    axis(r, 'step.order', s)
    jobs.append(dict(name=name, input=r, steps=480, base=str(SAMPLES), config=str(ROOT/'规格/内核配置-v2.json')))
p = subprocess.run([str(EXE)], input='\n'.join(json.dumps(j, ensure_ascii=False) for j in jobs)+'\n', text=True, capture_output=True)
assert p.returncode == 0, p.stderr
for line in p.stdout.splitlines():
    r = json.loads(line)
    if 'error' in r:
        print(r['name'], 'ERROR', r['error']['status'], r['error']['reason']); continue
    starts = [i for i, ev in enumerate(r['events']) for e in ev if e['phase']=='start' and e['subject']=='crusher']
    gaps = [b-a for a, b in zip(starts, starts[1:])][-16:]
    order = [o for o in r['graph']['order'] if 'x' in o]
    print(f"{r['name']:45s} period {sum(gaps)/len(gaps):.3f} order {order}")
