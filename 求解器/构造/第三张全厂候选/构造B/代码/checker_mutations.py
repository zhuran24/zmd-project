import json,copy
from pack_factory import BASE
from static_check import run
base=json.loads((BASE/'候选布局.json').read_text());contract=json.loads((BASE/'依据/S2接法.json').read_text());cases=[]
def test(name,edit,required):
 d=copy.deepcopy(base);edit(d);r=run(d,contract);bad={c['name'] for c in r['checks'] if not c['pass_']};cases.append(dict(name=name,expected_rejection=required,detected=required in bad));assert required in bad
# These mutations exercise additional failures beyond the known missing-route failures.
test('删除真实通道声明',lambda d:d['design']['physical_channels'].pop(),'exact_automatic_channels')
def bad_axis(d):
 t=next(t for t in d['layout']['transport'] if t['type']=='bridge');t['H_in']=(t['H_in']+2)%4
test('反写桥水平轴方向',bad_axis,'bridge_axis_direction_declarations')
test('移除全部供电桩',lambda d:d['layout'].__setitem__('power_poles',[]),'all_machines_powered')
test('把正向边冒充桥间反向边',lambda d:d['design']['bridge_reverse_channels'].append(d['design']['logical_feeds'][0]['path'][0]),'exact_bridge_reverse_channels')
test('声明含机身的空矩形',lambda d:d.__setitem__('empty_rectangle',dict(x0=2,y0=16,x1=7,y1=21)),'maximum_empty_rectangle')
(BASE/'证据/检查器拒绝性检验.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2));print(json.dumps(cases,ensure_ascii=False))
