from probe_common import *
import tempfile,shutil
D=OUT/'cache-origin';D.mkdir(exist_ok=True)
copy=Path(tempfile.mkdtemp(prefix='zmd-r2-cache-origin-'))/'求解器';copy.mkdir()
manifest=json.loads((OUT/'source/copy-manifest.json').read_text())
for row in manifest['files']:
 rel=Path(row['path']);(copy/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,copy/rel)
base=json.loads((OUT/'baseline.json').read_text())
args=base['build_argv'].copy();args[2:2]=['--manifest-path',str(copy/'Cargo.toml'),'-vv']
before=sha(TARGET/'r2audit/kernel')
r=run('cache-origin/build',args,cwd=copy,timeout=300);assert r.returncode==0
binary=TARGET/'r2-source-timing-20260922/kernel-cache-origin';shutil.copy2(TARGET/'r2audit/kernel',binary)
p=D/'record.json';r=run('cache-origin/run',[binary,'run',ROOT/'数据/样例/生产循环环带.json','--config',ROOT/'规格/内核配置-v1.json','--ticks',2,'--out',p]);assert r.returncode==0
v=json.loads(p.read_text());dump(D/'summary.json',{'temporary_manifest':str(copy/'Cargo.toml'),'copied_with':'shutil.copy2 (preserves modification times)','binary_sha256_before_build':before,'binary_sha256_after_build':sha(binary),'baseline_binary_sha256':base['binaries']['kernel']['sha256'],'expected_producer_path':str(copy/'crates/kernel/src/lib.rs'),'actual_producer_path':v['producer']['path'],'mismatched_origin':v['producer']['path']!=str(copy/'crates/kernel/src/lib.rs'),'cargo_build_exit':0,'run_exit':0})
print((D/'summary.json').read_text())
