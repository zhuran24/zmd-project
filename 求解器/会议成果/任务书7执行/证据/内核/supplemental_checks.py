"""新增D.3支持域检查及当前谱系封存；不扩大旧性能回归。"""
import json,copy
from pathlib import Path
from run_command import ROOT,E,run
CFG=ROOT/'规格/内核配置-v1.json';BIN=ROOT/'target/release/kernel'
source=ROOT/'数据/样例/任务7内核/静止成熟与暂停键.json';raw=json.loads(source.read_text())
plant=next(r['slot'] for r in raw['initial_state']['nonwarehouse']['value']['warehouse']['slots'] if r['item']=='荞花')
raw['settings']['warehouse_assignments'][0]['slot']=plant
path=E/'negative/植物出库域-input.json';path.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
r=run('D3-finite-load',[BIN,'check',path,'--config',CFG]);assert json.loads(r.stdout)['status']=='input_checked'
r=run('D3-production-domain',[BIN,'check',path,'--config',CFG,'--cycle-domain'],expected=2);out=json.loads(r.stdout)
assert out['trajectory_executed'] is False and out['domain_report'][2]['status']=='fail' and '原矿' in str(out['domain_report'][2])
checks=[{'name':'植物取货配置可作普通输入','passed':True,'scope':'装载，无步进'}, {'name':'当前生产域显式拒绝非全矿指派','passed':True,'scope':'D.3静态范围，无步进'}]
(E/'supplemental-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print('PASS 2 D.3 boundary checks')
