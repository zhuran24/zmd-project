"""原生成器输出重定向到复核目录，再派生种子并核原基准输入。"""
import sys,json,subprocess,hashlib
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
import benchmark_round5 as b
b.b.OUT=OUT/'generated-benchmarks';b.b.OUT.mkdir(exist_ok=True)
reports=[]
for name,m,l,c in [('benchmark_brick_60',0,0,0),('benchmark_brick',30,50,6),('benchmark_candidate_b',219,315,17)]:
 path,shape=b.generate_dense_brick()if m==0 else b.generate(name,m,l,c)
 cmd=[str(ROOT/'target/release/kernel'),'seed',str(path),'--config',str(ROOT/'规格/内核配置-v1.json'),'--out',str(path)]
 r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,(r.stdout,r.stderr)
 current=json.loads(path.read_text());original=json.loads((ROOT/f'crates/kernel/tests/fixtures/{name}.json').read_text());assert current==original,name
 reports.append({'name':name,'shape':shape,'json_equal_to_reviewed_fixture':True,'command':cmd,'generated_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'generator-results.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n');print('三份重新生成并派生的基准输入均与被审JSON逐字段相等')
