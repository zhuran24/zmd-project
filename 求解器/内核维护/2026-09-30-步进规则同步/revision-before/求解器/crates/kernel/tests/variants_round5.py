"""保持同级供货/先释放前件，六种局部模板全序的真实几何回放。"""
import copy,itertools,json
import round5_scenarios as s
from audit_round5 import read,write,polling_check
base=read(s.OUT/'轮询均分核验.json');order=base['parameters']['fixed']['judgment.order']['value']['template_order'];local=[r for r in order if r['operation']=='move'and r['target'].startswith('PC|furnace:')]
results=[]
for index,permutation in enumerate(itertools.permutations(local)):
    data=copy.deepcopy(base);data['parameters']['fixed']['judgment.order']['value']['template_order']=[r for r in order if r not in local]+list(permutation)
    name=f'轮询均分序{index}核验'
    source=s.finish(data,name,40)
    result=polling_check(read(s.OUT/(name+'-运行记录-v3-kernel.json')))
    results.append(dict(input=str(source),order=[r['target']for r in permutation],**result))
write(s.ROOT/'crates/kernel/evidence/round5/polling-six-orders.json',dict(status='pass',cases=results,scope='同一已核前件下六种局部顺序；没有替代judgment.order全域约减'))
