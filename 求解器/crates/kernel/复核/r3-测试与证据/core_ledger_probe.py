"""仓库核心PC入库台账独立核对，补充无线途径审计。"""
from pathlib import Path
import json,subprocess,sys,collections
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent;BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
from audit_round5 import audit_ledger
raw=json.loads((ROOT/'crates/kernel/tests/fixtures/core_inbound.json').read_text())
row=next(r for r in raw['initial_state']['nonwarehouse']['value']['inventory']if r['slot']=='box:storage:0');row['contents']=[{'item':'高容谷地电池','quantity':{'value':'2','category':'候选'},'entered_at':None}]
src=OUT/'core-ledger-input.json';dest=OUT/'core-ledger-record.json';src.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
commands=[[str(BIN),'seed',str(src),'--config',str(CFG),'--out',str(src)],[str(BIN),'run',str(src),'--config',str(CFG),'--ticks','4','--out',str(dest)],[str(BIN),'verify-record',str(dest),'--config',str(CFG)]]
for cmd in commands:
 p=subprocess.run(cmd,text=True,capture_output=True);assert p.returncode==0,(cmd,p.stdout,p.stderr)
data=json.loads(src.read_text());r=json.loads(dest.read_text());assert audit_ledger(r,data)==4
core=[x for t in r['trace']['ticks']for x in t['warehouse_ledger']['core_inbound']];assert len(core)==2 and all(x['port']=='core:south:1'for x in core)
assert not any(t['warehouse_ledger']['wireless_inbound']for t in r['trace']['ticks'])
(OUT/'core-ledger-results.json').write_text(json.dumps({'status':'pass','commands':commands,'ticks':4,'core_inbound':core,'wireless_inbound':[],'per_species_conservation':True},ensure_ascii=False,indent=2)+'\n');print('核心PC实际入库2件，逐笔账和仓库守恒通过')
