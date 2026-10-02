#!/usr/bin/env python3
import copy,json,hashlib
from pathlib import Path
from check_static import run
BASE=Path(__file__).resolve().parents[1];p=BASE/'布局.json';data=json.loads(p.read_text());base=run(data);baseline={x['name']:x['pass'] for x in base['checks']};cases=[]
def case(name,expected,edit):
 d=copy.deepcopy(data);edit(d);r=run(d);checks={x['name']:x['pass'] for x in r['checks']};cases.append({'name':name,'expected_check':expected,'baseline_component_pass':baseline[expected],'mutated_component_pass':checks[expected],'detected':baseline[expected] and not checks[expected]})
case('删除传送带','声明通道等于自动形成通道',lambda d:d['layout']['transport'].pop(next(i for i,t in enumerate(d['layout']['transport']) if t['type']=='belt')))
def bridge(d):
 t=next(t for t in d['layout']['transport'] if t['type']=='bridge');t['H_in']=(t['H_in']+2)%4
case('反写桥轴方向','桥轴方向及空轴',bridge)
def power(d):
 for i,p in enumerate(d['layout']['power_poles']):
  ps=d['layout']['power_poles'][:i]+d['layout']['power_poles'][i+1:]
  if any(not any(u['x0']<=z['x0']+6 and u['x1']>=z['x0']-5 and u['y0']<=z['y0']+6 and u['y1']>=z['y0']-5 for z in ps) for u in d['layout']['machines']):d['layout']['power_poles']=ps;return
 raise AssertionError('no essential pole')
case('删除必要供电桩','230台全部供电',power)
def block_rect(d):
 r=d['empty_rectangle'];x,y=r['x0'],r['y0'];d['layout']['power_poles'].append(dict(id='MUTATION_POWER',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0))
case('占用空矩形','最大空矩形',block_rect)
case('漏报实体通道','声明通道等于自动形成通道',lambda d:d['design']['physical_channels'].pop())
def duplicate(d):d['design']['logical_feeds'][1]['id']=d['design']['logical_feeds'][0]['id']
case('进路编号重复','通道和进路编号唯一',duplicate)
case('规则指纹错误','规则快照指纹',lambda d:d['source_fingerprints'].update(rules='0'*64))
def recipe(d):d['layout']['machines'][0]['recipe_ids']=['粉碎-荞花']
case('配方不符','配方和开关',recipe)
def baditem(d):d['design']['logical_feeds'][0]['item']='荞花'
case('进路物品不符','声明进路与重建逐格一致',baditem)
r={'base_layout_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'checker_sha256':hashlib.sha256((BASE/'代码/check_static.py').read_bytes()).hexdigest(),'base_static_pass':base['static_pass'],'all_detected':all(c['detected'] for c in cases),'cases':cases,'scope':'基准本身因全厂接法缺失而不通过；这里只检验各已通过组件对新增错误的拒绝。'}
(BASE/'结果/检查器拒绝性检验.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
