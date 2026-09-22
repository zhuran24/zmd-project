"""第六轮：批量验收前后比较被审树字节及mtime，日志只写到树外的round6根。"""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[4];E=Path(__file__).resolve().parent;BIN=ROOT/'target/release/kernel'
def snapshot(directory):
 return {str(p):dict(bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in directory.rglob('*') if p.is_file()}
for name,directory in [('verify-batch',ROOT/'数据/样例'),('verify-cli-batch',E/'cli')]:
 before=snapshot(directory)
 p=subprocess.run([str(BIN),'verify-batch',str(directory)],capture_output=True,text=True,cwd=ROOT)
 (E/(name+'.log')).write_text(p.stderr)
 after=snapshot(directory)
 assert p.returncode==0,(name,p.stdout,p.stderr)
 assert before==after,(name,'批量验收改写了被审树')
 result=json.loads(p.stdout);result.update(audited_tree_unchanged=True,checked_file_count=len(before),checked_bytes=sum(r['bytes'] for r in before.values()))
 (E/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(name,len(result['records']),len(result['cycles']),'只读通过',flush=True)
