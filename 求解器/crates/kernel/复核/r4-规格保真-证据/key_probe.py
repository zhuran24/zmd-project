"""通过共享target中的公开库接口读取规范键，不修改内核或新增Cargo项目。"""
from pathlib import Path
import json,subprocess,copy
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent
source=r'''
use kernel::{Input,Engine,Config,Result,value::read_json};
use serde_json::{Value,json};
use std::path::Path;
fn examine(path: &Path, config_path: &Path) -> Result<Value> {
 let config=Config::parse(read_json(config_path)?)?;
 let input=Input::load(path,&config,false)?;
 let engine=Engine::new(input)?;
 Ok(json!({"status":"accepted","key":engine.cycle_key()?}))
}
fn main() {
 let args:Vec<String>=std::env::args().collect();
 let result=match examine(Path::new(&args[1]),Path::new(&args[2])) {
  Ok(v)=>v,Err(e)=>json!({"status":"rejected","error":e.to_string()})
 };
 println!("{}",result);
}
'''
def latest(pattern):return max((ROOT/'target/release/deps').glob(pattern),key=lambda p:p.stat().st_mtime)
binary=ROOT/'target/kr-r4-l1-key-probe'
cmd=['rustc','--edition=2021','--crate-name','kr_r4_l1_key_probe','-','--extern','kernel='+str(latest('libkernel-*.rlib')),'--extern','serde_json='+str(latest('libserde_json-*.rlib')),'-L','dependency='+str(ROOT/'target/release/deps'),'-o',str(binary)]
p=subprocess.run(cmd,input=source,text=True,capture_output=True);(OUT/'key-probe-build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
raw=json.loads((OUT/'checkpoint-control-input.json').read_text());supply={'kind':'sufficient'}
raw['parameters']['fixedness_unproven']['warehouse.external_supply']['value']=supply
for row in raw['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
 if row['axis']=='warehouse.external_supply':row['value']['value']=copy.deepcopy(supply)
results=[]
for extra in [False,True]:
 data=copy.deepcopy(raw)
 if extra:data['initial_state']['nonwarehouse']['value']['semantic_context']['pending_events']['value'][0]['trigger']['extra']='未定义扩展'
 name='extra-key' if extra else 'control-key';path=OUT/(name+'-input.json');path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 proc=subprocess.run([str(binary),str(path),str(ROOT/'规格/内核配置-v1.json')],capture_output=True,text=True);result=json.loads(proc.stdout)
 (OUT/(name+'-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');results.append(dict(case=name,status=result['status'],extra=result.get('key',{}).get('state',{}).get('semantic_context',{}).get('pending_events',{}).get('value',[{}])[0].get('trigger',{}).get('extra')))
(OUT/'key-probe-summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps(results,ensure_ascii=False))
