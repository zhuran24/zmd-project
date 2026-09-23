import copy,json
from pathlib import Path
from 目录与流量 import *
import 检查器甲 as A
import 检查器乙 as B
c=load(BASE/'候选.json');cases=[]
def test(name,mutate,predicate):
 x=copy.deepcopy(c);mutate(x);sa=strict(x)
 if sa:aa=bb=True;ae=be=sa
 else:
  a=A.reconstruct(x);b=B.audit(x);al=A.analyze(x,a);aa,bb=predicate(x,a,al,b);ae=a['errors']+al['errors'];be=b['errors']
 cases.append(dict(name=name,A_reject=aa,B_reject=bb,A_evidence=ae[:4],B_evidence=be[:4]))
test('未知字段',lambda x:x.update(extra=1),lambda *args:(False,False))
test('错误正式文件指纹',lambda x:x['source_fingerprints'].update(rules='0'*64),lambda *args:(False,False))
test('删除真实通道声明',lambda x:x['design']['physical_channels'].pop(),lambda x,a,al,b:(bool(al['errors']),bool(b['errors'])))
test('制造单位实体重叠',lambda x:x['layout']['machines'][1].update({k:x['layout']['machines'][0][k] for k in ['x0','x1','y0','y1']}),lambda x,a,al,b:(bool(a['errors']),bool(b['errors'])))
def rotate(x):
 t=next(t for t in x['layout']['transport'] if t['type']=='belt');t['out_side']=next(i for i in range(4) if i not in [t['out_side'],t['in_side']])
test('带子改向漏接',rotate,lambda x,a,al,b:(bool(a['errors']+al['errors']),bool(b['errors'])))
if any(t['type']=='bridge' for t in c['layout']['transport']):
 def bridge(x):
  t=next(t for t in x['layout']['transport'] if t['type']=='bridge');k='H_in' if t['H_in'] is not None else 'V_in';t[k]=(t[k]+2)%4
 test('桥轴声明翻转',bridge,lambda x,a,al,b:(bool(a['errors']),bool(b['errors'])))
test('通道假物品标签',lambda x:x['design']['physical_channels'][0].update(allowed_items=['精选荞愈胶囊'] if x['design']['physical_channels'][0]['allowed_items']!=['精选荞愈胶囊'] else ['源矿']),lambda x,a,al,b:(bool(al['errors']),bool(b['errors'])))
# Empty-rectangle algorithms are compared independently on deterministic varied occupancy.
import random
r=random.Random(24);recttests=[]
for j in range(5):
 x=copy.deepcopy(c)
 # Positive candidate rectangle is intentionally replaced by an occupied 6x6 area.
 m=x['layout']['machines'][0];x['empty_rectangle']=dict(x0=m['x0'],y0=m['y0'],x1=min(69,m['x0']+5),y1=min(69,m['y0']+5))
 a=A.reconstruct(x);b=B.audit(x);ra,score=A.maxrect(a['occ']);recttests.append(dict(A_score=score,B_score=b['score'],equal=tuple(score)==tuple(b['score'])))
 break
result=dict(candidate_sha256=sha(BASE/'候选.json'),cases=cases,rectangle_comparisons=recttests,all_pass=all(t['A_reject'] and t['B_reject'] for t in cases) and all(t['equal'] for t in recttests),scope='有限变异回归，验证所列拒绝路径；不是检查器全规格正确性证明')
(BASE/'检查/回归.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result['all_pass'],len(cases))
