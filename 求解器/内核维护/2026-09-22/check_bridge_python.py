#!/usr/bin/env python3
"""Python状态校验：桥同种双轴正例，制造普通格同种重复仍拒绝。"""
from pathlib import Path
import json,sys,copy
R=Path.cwd();O=R/'内核维护/2026-09-22';sys.path.insert(0,str(R/'数据/样例'))
from runtime_record import validate_state
from check_examples import CheckError
b=json.loads((R/'crates/kernel/tests/fixtures/bridge.json').read_text());state=copy.deepcopy(b['initial_state']['nonwarehouse']['value'])
for row in state['inventory']:
 if row['slot'] in ['bridge:vertical:0','bridge:horizontal:0']:
  row['contents']=[{'item':'源矿','quantity':{'value':'1','category':'候选'},'entered_at':{'kind':'rational','value':{'value':'0','category':'候选'}}}]
validate_state(b,state)
a=json.loads((R/'数据/样例/混做粉碎机两下游.json').read_text());s=copy.deepcopy(a['initial_state']['nonwarehouse']['value'])
for row in s['inventory']:
 if row['slot'] in ['crusher:input:0','crusher:output:0']:
  row['contents']=[{'item':'源矿','quantity':{'value':'1','category':'候选'},'entered_at':None}]
try:validate_state(a,s)
except CheckError as e:assert '同单位同种物品跨普通格重复' in str(e)
else:raise AssertionError('manufacturing uniqueness guard was lost')
result={'status':'pass','same_species_bridge_axes':'accepted','ordinary_manufacturing_duplicate':'rejected','scope':'Python inventory/state validator; not full trajectory'}
(O/'python-bridge-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
