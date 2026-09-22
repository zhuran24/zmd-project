from pathlib import Path
import json,hashlib,subprocess,shlex,copy,datetime
R=Path('/home/zhuran24/zmd-research-fresh'); W=R/'求解器'; E=W/'会议成果/任务书7执行/证据/规格'
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj): (E/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
commands=[]
def run(name,args):
 print('running:',shlex.join(args),flush=True)
 r=subprocess.run(args,cwd=W,text=True,capture_output=True)
 (E/(name+'.log')).write_text('$ '+shlex.join(args)+'\nCWD='+str(W)+'\nEXIT_CODE='+str(r.returncode)+'\nSTDOUT:\n'+r.stdout+'\nSTDERR:\n'+r.stderr)
 row={'name':name,'command':shlex.join(args),'cwd':str(W),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr};commands.append(row);save('commands.json',commands)
 print(name,'exit',r.returncode,(r.stdout+r.stderr)[-800:],flush=True)
 assert r.returncode==0,name
 return r
# A verification input derived from a named supplied sample; original sample is preserved.
p=W/'数据/样例/混做粉碎机两下游.json'; sample=json.loads(p.read_text()); orig=copy.deepcopy(sample)
config_path=W/'规格/内核配置-v1.json'; config=json.loads(config_path.read_text())
sample['catalog']={'path':str(W/'数据/正式静态目录.json'),'sha256':h(W/'数据/正式静态目录.json')}
sample['parameters']['axis_registry']={'path':str(W/'规格/选择点参数轴.md'),'sha256':h(W/'规格/选择点参数轴.md')}
values={a:v for group in ['fixed','offline_mutable','fixedness_unproven'] for a,v in sample['parameters'][group].items()}
for group in ['fixed','offline_mutable','fixedness_unproven']:sample['parameters'][group]={}
for axis,row in config['axes'].items():
 v=values[axis]
 if row['disposition']!='由输入全称量化':
  v={'status':'specified','value':copy.deepcopy(row['value']),'basis':[row['basis'],'任务7规则回填；本输入仅作seed装载检查']}
 life=row['lifetime']
 if axis=='judgment.order':life='F' if values['judgment.order_scope']['value']=='global' else 'U'
 group='fixed' if life.startswith('F') else ('offline_mutable' if life=='O' else 'fixedness_unproven')
 sample['parameters'][group][axis]=v
state=sample['initial_state']['nonwarehouse']['value'];state['semantic_context']['parameter_values']=[{'axis':a,'value':v,'lifetime':life} for g,life in [('fixed','F'),('offline_mutable','O'),('fixedness_unproven','U')] for a,v in sample['parameters'][g].items()]
# Preserve source reachability citation by resolving its relative document if present.
r=sample['initial_state']['reachability'].get('value')
if isinstance(r,dict) and isinstance(r.get('document'),str): r['document']=str((p.parent/r['document']).resolve())
assert not sample['debug_operations']
assert not any(u['kind'] in ['协议储存箱','物品准入口'] for u in sample['layout']['units'])
changes=[]
def diff(a,b,path=''):
 if type(a)!=type(b):changes.append(path);return
 if isinstance(a,dict):
  for k in a.keys()|b.keys():
   if k not in a or k not in b: changes.append(path+'/'+k)
   else: diff(a[k],b[k],path+'/'+k)
 elif isinstance(a,list):
  if a!=b:changes.append(path)
 elif a!=b:changes.append(path)
diff(orig,sample)
input_path=E/'装载样例.json';save(input_path.name,sample)
save('sample-migration.json',{'source':str(p),'source_sha256':h(p),'derived':str(input_path),'changed_json_paths':sorted(changes),'preserved_geometry':orig['layout']==sample['layout'],'preserved_settings':orig['settings']==sample['settings'],'preserved_inventory':orig['initial_state']['nonwarehouse']['value']['inventory']==state['inventory'],'scope':'仅迁移引用、配置值/生命周期及其种子投影；无箱、无门、无调试动作。合成初态可达性未证。'})
run('cargo-build',['cargo','build','--release','-p','kernel','--target-dir',str(W/'target')])
bin=W/'target/release/kernel'
run('kernel-seed',[str(bin),'seed',str(input_path),'--config',str(config_path),'--out',str(E/'seed-output.json')])
run('kernel-check',[str(bin),'check',str(E/'seed-output.json'),'--config',str(config_path)])
out=json.loads((E/'seed-output.json').read_text())
assert out['schema']=='kernel-input-v3'
save('load-verification.json',{'status':'passed','time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'binary':{'path':str(bin),'sha256':h(bin)},'input':{'path':str(input_path),'sha256':h(input_path)},'seed_output':{'path':str(E/'seed-output.json'),'sha256':h(E/'seed-output.json')},'catalog_sha256':h(W/'数据/正式静态目录.json'),'config_sha256':h(config_path),'axis_sha256':h(W/'规格/选择点参数轴.md'),'trajectory_executed':False,'interpretation':'seed先通过Input::parse_with_base的目录引用、编译期目录与三份正式源检查，再派生初态调度上下文；check复读派生输入。未运行step，不认证新传输、门恢复、完整语义或达标。'})
