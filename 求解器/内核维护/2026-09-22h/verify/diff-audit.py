import copy,json,re,subprocess
from pathlib import Path
v=Path(__file__).resolve().parent;r=v.parents[3]
head=json.loads((v/'before.json').read_text())['head']
def old(name):return json.loads(subprocess.check_output(['git','show',head+':'+name],cwd=r))
def load(p):return json.loads(p.read_text())
def save(n,x):(v/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def diff(a,b,path=()):
    if type(a)!=type(b):return [(path,a,b)]
    if isinstance(a,dict):
        return sum((diff(a.get(k),b.get(k),(*path,k)) for k in sorted(a.keys()|b.keys())),[])
    if isinstance(a,list):
        if len(a)!=len(b):return [(path,a,b)]
        return sum((diff(x,y,(*path,i)) for i,(x,y) in enumerate(zip(a,b))),[])
    return [] if a==b else [(path,a,b)]
catalog='求解器/数据/正式静态目录.json';a=old(catalog);b=load(r/catalog)
assert all(a[k]==b[k] for k in ['recipes','constraints','task','static_checks','conventions','transcribed_at','schema','source_root'])
units_a={u['id']:u for u in a['units']};units_b={u['id']:u for u in b['units']}
assert [k for k in units_a if units_a[k]!=units_b[k]]==['桥接器']
assert a['sources'][1:]==b['sources'][1:]
rule_changes=[i+1 for i,(x,y) in enumerate(zip(a['sources'][0]['lines'],b['sources'][0]['lines'])) if x!=y]
assert rule_changes==[24,59,63]
bridge=units_b['桥接器'];assert bridge['ports']['port_assignment']=='permanent_bidirectional' if 'port_assignment' in bridge['ports'] else bridge.get('port_assignment')=='permanent_bidirectional'
axis_names={'bridge.scheduling_scope','bridge.capacity','connection.bridge_first_contact','connection.bridge_tie','offline.direction_effect'}
input_changes=[];unexpected=[]
for row in load(v/'active-inputs.json'):
    name=row['path'];before=old(name);after=load(r/name)
    differences=diff(before,after)
    for path,x,y in differences:
        parts=[str(k) for k in path]
        allowed=(parts in [['catalog','sha256'],['parameters','axis_registry','sha256']]
            or (parts[:1]==['parameters'] and any(a in parts for a in axis_names))
            or (parts[:2]==['layout','units'] and 'bridge_axes' in parts)
            or parts[:5]==['initial_state','nonwarehouse','value','logistics','poll_memory']
            or parts[:6]==['initial_state','nonwarehouse','value','semantic_context','arbitration','level_order']
            or parts[:5]==['initial_state','nonwarehouse','value','semantic_context','parameter_values'])
        if not allowed:unexpected.append({'path':name,'field':parts,'old':x,'new':y})
    # Remove precisely the migrated semantic parameter rows, retain all other parameter rows.
    def normalize(j):
        j=copy.deepcopy(j);j['catalog'].pop('sha256');j['parameters']['axis_registry'].pop('sha256')
        for group in ['fixed','offline_mutable','fixedness_unproven']:
            for axis in axis_names:j['parameters'][group].pop(axis,None)
        for u in j['layout']['units']:
            if u['kind']=='桥接器':u['bridge_axes']=None
        bridge_ids={u['id'] for u in j['layout']['units'] if u['kind']=='桥接器'}
        state=j['initial_state']['nonwarehouse']['value']
        if state:
            state['semantic_context']['parameter_values']=[x for x in state['semantic_context']['parameter_values'] if x['axis'] not in axis_names]
            state['semantic_context']['arbitration']['level_order']=[x for x in state['semantic_context']['arbitration']['level_order'] if x.split('|')[1] not in bridge_ids]
            state['logistics']['poll_memory']['value']['sides']=[x for x in state['logistics']['poll_memory']['value']['sides'] if x['unit'] not in bridge_ids]
        return j
    assert normalize(before)==normalize(after),name
    input_changes.append({'path':name,'leaf_differences':len(differences),'normalized_equal':True,'bridge_count':sum(u['kind']=='桥接器' for u in after['layout']['units'])})
save('input-diff-audit.json',input_changes);save('unexpected-input-differences.json',unexpected)
summary={'rule_lines_changed':rule_changes,'only_unit_changed':'桥接器','constraints_unchanged':72,'recipes_unchanged':18,'inputs_normalized_equal':len(input_changes),'inputs_with_bridges':sum(x['bridge_count']>0 for x in input_changes),'unexpected_fields':len(unexpected)}
save('diff-audit-result.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
