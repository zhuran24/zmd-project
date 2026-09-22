"""第六轮制造砖基准；实测含装载/输出的cycle墙钟和run内循环，阈值另列。"""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,platform,subprocess,time
from types import SimpleNamespace
from pathlib import Path
import build_fixtures as b
from generate_examples import unit
from runtime_example import quantity as q,time_value as t,decision
from migrate_round5 import migrate,save
ROOT=b.ROOT;E=ROOT/'crates/kernel/evidence/round6';BASE=ROOT/'数据/样例';BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
PRODUCTS=('高容谷地电池','精选荞愈胶囊')
def call(args):
 p=subprocess.run([str(BIN),*map(str,args),'--config',str(CFG)],capture_output=True,text=True)
 assert p.returncode==0,(args,p.stdout,p.stderr)
 return json.loads(p.stdout)
def generate():
 units=[];recipes={}
 for i in range(9):
  x=2+10*(i%3);y=3+13*(i//3);kind='封装机' if i%2==0 else '灌装机'
  recipe=next(r for r in b.CATALOG['recipes'] if r['kind']==kind);recipes[f'm{i}']=recipe
  units += [unit(f'm{i}',kind,x,y),unit(f'box{i}','协议储存箱',x,y+5),unit(f'power{i}','供电桩',x+6,y+3)]
  units += [unit(f'b{i}_{j}','传送带',x+j,y+4) for j in range(3)]
 b.OUT=BASE;d=b.generate('双成品制造砖',units)
 b.set_axis(d,'warehouse.external_supply',{'kind':'sufficient'})
 for s in d['settings']['switches']:s['enabled']=True
 inventory=d['initial_state']['nonwarehouse']['value']['inventory']
 for uid,recipe in recipes.items():
  for j,item in enumerate(recipe['inputs']):next(r for r in inventory if r['slot']==f'{uid}:input:{j}')['contents']=[dict(item=item,quantity=q(50),entered_at=t(-1))]
 d['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(E/'实施与验证.md'),'scope':'性能专用条件预装原料；不声称从L6满仓可达，不作为K6达标布局'},'第六轮K5：正式配方真制造，初始两成品在仓内外均为零')
 d['scenario']['assertions']=['9台末级制造、9箱无线入库；55单位/54PC，有限预置50件各原料，不是持续闭环。']
 path=BASE/'双成品制造砖.json';save(path,migrate(d));call(['seed',path,'--out',path]);return path

def main():
 global E
 parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['before','final']);parser.add_argument('--generate',action='store_true');parser.add_argument('--out-dir',type=Path);args=parser.parse_args()
 if args.out_dir:E=args.out_dir.resolve();E.mkdir(parents=True,exist_ok=True)
 if args.generate:generate()
 reports=[]
 sources=[ROOT/'crates/kernel/tests/fixtures'/f'{name}.json' for name in ('benchmark_brick_60','benchmark_brick','benchmark_candidate_b')]+[BASE/'双成品制造砖.json']
 for path in sources:
  raw=json.loads(path.read_text());shape=dict(total_units=len(raw['layout']['units']),physical_channels=len(raw['layout']['physical_channels']),manufacturing_units=sum(u['kind'] in {r['kind'] for r in b.CATALOG['recipes']} for u in raw['layout']['units']))
  ticks=32 if path.name=='双成品制造砖.json' else 12;measurements={}
  for mode in ('run','cycle'):
   dest=E/(path.stem+'-benchmark-cycle.json');rss=E/(path.stem+'-'+mode+'-'+args.stage+'.log')
   cmd=[str(BIN),mode,str(path),'--config',str(CFG),'--ticks',str(ticks)]
   cmd+=['--no-output'] if mode=='run' else ['--no-record','--search-checkpoint-interval','32','--out',str(dest)]
   measured=json.loads(subprocess.run([sys.executable,'-B',str(ROOT/'crates/kernel/tests/measure_command.py'),*cmd],capture_output=True,text=True,check=True).stdout)
   p=SimpleNamespace(**measured);wall=p.wall_ns;rss.write_text(json.dumps(measured,ensure_ascii=False)+'\n')
   assert p.returncode==0,(cmd,p.stdout,p.stderr)
   result=json.loads(p.stdout) if mode=='run' else json.loads(dest.read_text())
   assert result['status'] in ('completed','inconclusive','counterexample','cycle_found'),result
   measurements[mode]=dict(command=cmd,wall_ms_per_tick=wall/1e6/ticks,max_rss_kb=p.max_rss_kb,completed_ticks=result.get('budget',{}).get('completed_ticks',result.get('ticks')),result_status=result['status'])
   if mode=='run':measurements[mode].update(engine_ms_per_tick=int(result['elapsed_ns'])/1e6/ticks,completed_batches=result['completed_batches'])
   else:measurements[mode]['certificate_bytes']=dest.stat().st_size
  target=20 if 'candidate' in path.name else 1
  reports.append(dict(name=path.stem,shape=shape,ticks=ticks,input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),modes=measurements,target_ms_per_tick=target,run_target_met=measurements['run']['engine_ms_per_tick']<=target,cycle_wall_target_met=measurements['cycle']['wall_ms_per_tick']<=target))
  print(path.stem,measurements,flush=True)
 # 真制造和双成品实际入库另用可核v3记录证明；计时不含该有记录审计。
 path=BASE/'双成品制造砖.json';record=BASE/'双成品制造砖-运行记录-v3-kernel.json'
 call(['run',path,'--ticks',12,'--out',record]);call(['verify-record',record])
 data=json.loads(record.read_text());totals={p:sum(int(r['actual_inbound']['value']) for tick in data['trace']['ticks'] for r in tick['warehouse_ledger']['totals'] if r['item']==p) for p in PRODUCTS}
 assert all(v>0 for v in totals.values()) and int(data['validation_scope']['manufacturing_cycles_completed']['value'])>0
 if args.stage=='final':
  other=E/'brick-no-cache.json';call(['run',path,'--ticks',12,'--no-cache','--out',other]);assert json.loads(other.read_text())==data;other.unlink()
 output=dict(status='pass',stage=args.stage,platform=platform.platform(),binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),reports=reports,production_audit=dict(record=str(record),completed_batches=data['validation_scope']['manufacturing_cycles_completed'],actual_inbound=totals,cache_differential='逐字段相同' if args.stage=='final' else '留最终验证'),historical_benchmark_brick_ms_per_tick=2.74,historical_target_met=False,scope='目标达标位与基准执行通过分开；cycle墙钟包含装载、指纹、搜索和写小证书，run engine只含转移；条件预装原料不证明闭环或任务可达性。')
 save(E/f'benchmark-{args.stage}.json',output)
if __name__=='__main__':main()
