"""第五轮样例显式迁移；旧v2记录和黄金保留，v3参考另行重算。"""
from pathlib import Path
import json,hashlib,itertools,copy
ROOT=Path(__file__).resolve().parents[3]
SAMPLES=ROOT/'数据/样例'
def load(p):return json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def branch_table(data):
    old=data['parameters']['fixedness_unproven']['damping.branch']['value']
    if old['schema']=='damping-branch-v2':return copy.deepcopy(old)
    preferences={}
    for row in old['choices']:
        if 'channel' in row:
            uid=row['fork_unit']; out=row['outgoing_channel']
            if uid in preferences and preferences[uid]!=out:raise ValueError('查询起点异选不能迁移')
            preferences[uid]=out
    # 测试参数点明确选择：保留旧支优先，失活集合按PC字典序第一支；不是内核默认。
    choices=[]
    for u in data['layout']['units']:
        if u['kind']!='分流器':continue
        outgoing=sorted(c['id'] for c in data['layout']['physical_channels'] if c['source_port'].split(':')[0]==u['id'])
        for n in range(1,len(outgoing)+1):
            for subset in itertools.combinations(outgoing,n):
                selected=preferences.get(u['id']);selected=selected if selected in subset else subset[0]
                choices.append(dict(fork_unit=u['id'],available_channels=list(subset),outgoing_channel=selected))
    return dict(schema='damping-branch-v2',fixedness='by_available_set',choices=choices,evaluations=[],on_missing='unresolved')
def migrate(data):
    config=load(ROOT/'规格/内核配置-v1.json')
    params=data['parameters'];params['axis_registry']['sha256']=hashlib.sha256((ROOT/'规格/选择点参数轴.md').read_bytes()).hexdigest()
    if data['schema']!='kernel-input-v3':return data
    params['fixedness_unproven']['damping.branch']['value']=branch_table(data)
    params['fixedness_unproven']['warehouse.external_supply']['value'].pop('basis',None)
    for group in ('fixed','offline_mutable','fixedness_unproven'):
        for a,d in params[group].items():
            if config['axes'][a]['disposition']!='由输入全称量化':d['value']=copy.deepcopy(config['axes'][a]['value'])
    seed=data['initial_state']['nonwarehouse']['value']
    seed['inventory'].sort(key=lambda r:r['slot'])
    seed['semantic_context']['parameter_values']=[dict(axis=a,value=copy.deepcopy(d),lifetime=lifetime) for group,lifetime in [('fixed','F'),('offline_mutable','O'),('fixedness_unproven','U')] for a,d in params[group].items()]
    return data
if __name__=='__main__':
    files=[p for p in SAMPLES.glob('*.json') if load(p).get('schema') in ('kernel-input-v2','kernel-input-v3')]
    files+=list((ROOT/'crates/kernel/tests/fixtures').glob('*.json'))
    for p in files:save(p,migrate(load(p)))
    import sys
    sys.path.insert(0,str(SAMPLES))
    from runtime_example import profile_projection
    for name,out in [('混做粉碎机两下游','kernel_profile_v1参数赋值'),('分流器三路轮询','分流器三路轮询-参数赋值')]:save(SAMPLES/(out+'.json'),profile_projection(load(SAMPLES/(name+'.json'))))
