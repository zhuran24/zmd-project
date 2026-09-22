#!/usr/bin/env python3
"""第六轮只读批量闸：结构、来源、独立重跑、逐事务台账及固定保护基线。"""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'数据/样例'))
from audit_task7 import audit_ledger
BIN=Path(os.environ.get('KERNEL_BIN',ROOT/'target/release/kernel'))
AJV='/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
def read(path):return json.loads(path.read_text())
def schema_check(paths):
 script='''const fs=require('fs');const Ajv=require(process.argv[1]);const args=JSON.parse(fs.readFileSync(0,'utf8'));const schema=JSON.parse(fs.readFileSync(args.schema,'utf8'));const validate=new Ajv({strict:false,allErrors:true}).compile(schema);for(const path of args.paths){if(!validate(JSON.parse(fs.readFileSync(path,'utf8')))){console.error(JSON.stringify({path,errors:validate.errors}));process.exit(1);}}'''
 p=subprocess.run(['node','-e',script,AJV],input=json.dumps(dict(schema=str(ROOT/'规格/内核输出.schema.json'),paths=[str(p) for p in paths])),capture_output=True,text=True)
 assert p.returncode==0,(p.stdout,p.stderr)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--dry',action='store_true',required=True);parser.add_argument('--config',type=Path,default=ROOT/'规格/内核配置-v1.json');args=parser.parse_args()
 assert args.directory.is_dir(),args.directory
 paths=[];historical=[];records=[];cycles=[];reference_count=0
 for path in sorted(args.directory.rglob('*.json')):
  data=read(path)
  if not isinstance(data,dict):continue
  schema=data.get('schema')
  if schema in ('kernel-output-v4','kernel-cycle-v3'):paths.append(path)
  elif schema in ('kernel-cycle-v1','kernel-cycle-v2','kernel-output-v1','kernel-output-v2','kernel-output-v3'):historical.append(str(path))
  elif isinstance(schema,str) and schema.startswith(('kernel-output-','kernel-cycle-','kernel-proof-')):raise AssertionError(('尚未支持的证据版本或直接证明语义入口',str(path),schema))
 schema_check(paths)
 certified_records={};cycle_results={}
 for path in paths:
  data=read(path)
  if data['schema']!='kernel-cycle-v3':continue
  checked=subprocess.run([str(BIN),'verify-cycle',str(path.resolve()),'--config',str(args.config.resolve())],capture_output=True,text=True)
  assert checked.returncode==0,(str(path),checked.stdout,checked.stderr)
  cycle_results[path]=json.loads(checked.stdout)
  if data['run_record_ref']:
   certified_records[(path.parent/data['run_record_ref']['path']).resolve()]=str(path.resolve())
 for path in paths:
  data=read(path);mode='verify-cycle' if data['schema']=='kernel-cycle-v3' else 'verify-record'
  if mode=='verify-cycle':
   pass
  elif path.resolve() in certified_records and data['status']!='completed':
   pass  # 上方已按证书预算完整重跑其停止前缀，不能由孤立记录猜资源预算。
  elif mode=='verify-record' and data['producer']['kind']!='kernel':
   raise AssertionError(('当前批量入口仅支持kernel生产者；参考执行器尚未迁移v4',str(path)))
  else:
   p=subprocess.run([str(BIN),mode,str(path.resolve()),'--config',str(args.config.resolve())],capture_output=True,text=True)
   assert p.returncode==0,(str(path),p.stdout,p.stderr)
  if mode=='verify-record':
   source=next((path.parent/row['path']).resolve() for row in data['fingerprints'] if row['role']=='input')
   ticks=audit_ledger(data,read(source))
   records.append(dict(path=str(path.resolve()),ticks=ticks))
  else:cycles.append(dict(path=str(path.resolve()),verification=cycle_results[path]))
  print('已核 '+path.name,file=sys.stderr,flush=True)
 print(json.dumps(dict(status='input_checked',read_only=True,records=records,cycles=cycles,reference_records=reference_count,historical_records=historical,scope='当前v4记录和v3周期按现行源、schema、Rust重放及Python部分接收账验收；旧版本列作史料。'),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
