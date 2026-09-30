"""只格式化包二修改的 Rust 文件；沿用历史守卫。"""
import subprocess,sys
from guard import OUT,ROOT,guard,save
stage=OUT/'package2-stage'
paths=sorted(str(p.relative_to(stage)) for p in (stage/'crates/kernel').rglob('*.rs'))
# lib.rs 的模块扩展不能隐式格式化包一文件。
label=sys.argv[1]
guard(label+'-before')
try:
    argv=['rustfmt','--edition','2021','--config','skip_children=true',*paths]
    with (OUT/(label+'.log')).open('w') as f:r=subprocess.run(argv,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    save(label+'-command.json',{'argv':argv,'cwd':str(ROOT),'exit_code':r.returncode})
    assert r.returncode==0
    for rel in paths:(stage/rel).write_bytes((ROOT/rel).read_bytes())
finally:guard(label+'-after')
