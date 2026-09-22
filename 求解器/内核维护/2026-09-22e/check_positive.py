#!/usr/bin/env python3
"""当前编译内核的正向seed/check及旧指纹拒收对照。"""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;source=R/'数据/样例/任务7内核/无线多格全收.json'
d=json.loads(source.read_text())
for ref in [d['catalog'],d['parameters']['axis_registry']]:ref['path']=str((source.parent/ref['path']).resolve())
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=O/'positive-input.json';save(p,d);bin=R/'target/release/kernel';cfg=R/'规格/内核配置-v1.json';rows=[]
for name,args,expected in [
 ('kernel-seed',['seed',str(p),'--out',str(O/'seed-output.json')],0),
 ('kernel-check',['check',str(O/'seed-output.json')],0),
 ('kernel-run',['run',str(O/'seed-output.json'),'--ticks','6','--out',str(O/'positive-run.json')],0),
 ('kernel-verify-record',['verify-record',str(O/'positive-run.json')],0),
]:
 argv=[str(bin),*args,'--config',str(cfg)];r=subprocess.run(argv,capture_output=True,text=True);(O/(name+'.log')).write_text(r.stdout+r.stderr);rows.append({'name':name,'argv':argv,'exit_code':r.returncode});assert r.returncode==expected,(name,r.stdout,r.stderr)
# 原目录SHA不能被新内核当成当前输入接受。
d['catalog']['sha256']='6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff';p=O/'stale-catalog-input.json';save(p,d)
argv=[str(bin),'seed',str(p),'--config',str(cfg)];r=subprocess.run(argv,capture_output=True,text=True);(O/'stale-catalog.log').write_text(r.stdout+r.stderr);assert r.returncode!=0;assert json.loads(r.stdout)['status']=='invalid_input' and '源文件指纹不符' in r.stdout,(r.stdout,r.stderr);rows.append({'name':'stale-catalog-negative','argv':argv,'exit_code':r.returncode,'expected':'nonzero'})
save(O/'positive-validation.json',{'status':'pass','binary_sha256':hashlib.sha256(bin.read_bytes()).hexdigest(),'commands':rows});print(json.dumps(rows,ensure_ascii=False))
