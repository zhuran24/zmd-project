"""第六轮K7：只在非来源内容逐字段相同时重锁sources，不重生成事件对清单。"""
import sys
sys.dont_write_bytecode=True
import copy,hashlib,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];E=Path(__file__).resolve().parent
script=ROOT/'规格/复核/约减/count_classes.py';target=script.parent/'等价类计数.json'
def check(label):
 p=subprocess.run([sys.executable,'-B',str(script),'--check'],capture_output=True,text=True,cwd=ROOT)
 (E/(label+'.log')).write_text(p.stdout+p.stderr)
 return p.returncode
old=json.loads(target.read_text());before=hashlib.sha256(target.read_bytes()).hexdigest();before_exit=check('reduction-before')
spec=importlib.util.spec_from_file_location('round6_reduction',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);current=module.calculate()
a=copy.deepcopy(old);b=copy.deepcopy(current);a.pop('sources');b.pop('sources')
assert json.dumps(a,ensure_ascii=False,sort_keys=True)==json.dumps(b,ensure_ascii=False,sort_keys=True),'类数或其它非指纹内容变化，禁止重锁'
assert [r['path'] for r in old['sources']]==[r['path'] for r in current['sources']],'来源路径集合变化，须另行复核'
changed=[dict(path=x['path'],before=x['sha256'],after=y['sha256']) for x,y in zip(old['sources'],current['sources']) if x!=y]
if changed:
 old['sources']=current['sources'];target.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
after_exit=check('reduction-after');assert after_exit==0
report=dict(status='pass',before_exit=before_exit,after_exit=after_exit,changed_fingerprints=changed,non_fingerprint_content_equal=True,classes={r['name']:{m:v['classes'] for m,v in r['modes'].items()} for r in current['examples']},path=str(target),before_sha256=before,after_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
(E/'reduction-lock.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
