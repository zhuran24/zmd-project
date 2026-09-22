from probe_common import *
import shutil,tempfile,difflib
TMP=Path(tempfile.mkdtemp(prefix='zmd-r2-source-'));COPY=TMP/'求解器';COPY.mkdir()
PROFILE='r2source'+TMP.name.rsplit('-',1)[-1]
BINDIR=TARGET/'r2-source-timing-20260922';D=OUT/'source';D.mkdir(exist_ok=True)
copy_paths=[Path('Cargo.toml'),Path('Cargo.lock'),Path('数据/正式静态目录.json'),Path('crates/kernel/周期键读取审计.md')]
for crate in ['kernel','topology']:
 copy_paths.append(Path('crates')/crate/'Cargo.toml')
 copy_paths.extend(p.relative_to(ROOT) for p in (ROOT/'crates'/crate/'src').rglob('*.rs'))
copy_paths.extend(Path('规格')/name for name in ['内核配置-v1.json','受限模型声明.md','受限转移定义.md','运行语义.md','内核输入.md','内核输出.md','内核输出.schema.json'])
for p in copy_paths:
 (COPY/p).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,COPY/p)
dump(D/'copy-manifest.json',{'temporary_source_root':str(COPY),'files':[{'path':str(p),'sha256':sha(ROOT/p),'copy_sha256':sha(COPY/p)} for p in copy_paths]})
CFG=ROOT/'规格/内核配置-v1.json';INPUT=ROOT/'数据/样例/生产循环环带.json';CURRENT=D/'current-record.json'
buildargs=['cargo','build','--manifest-path',str(COPY/'Cargo.toml'),'--locked','--offline','-p','kernel','--bin','kernel','--profile',PROFILE,'--config',f'profile.{PROFILE}.inherits="dev"','--config',f'profile.{PROFILE}.codegen-units=1','--config',f'profile.{PROFILE}.debug=0','-j','1']
def build(name):
 r=run('source/build-'+name,buildargs,cwd=COPY,timeout=300);assert r.returncode==0,r.stderr.decode()
 dst=BINDIR/('kernel-'+name);shutil.copy2(TARGET/PROFILE/'kernel',dst);return dst
def record(name,binary):
 r=run('source/'+name,[binary,'run',INPUT,'--config',CFG,'--ticks',2,'--out',CURRENT]);assert r.returncode==0,r.stderr.decode()
 saved=D/(name+'.json');shutil.copy2(CURRENT,saved);return json.loads(saved.read_text())
def verify(name,binary,path):return run('source/'+name,[binary,'verify-record',path,'--config',CFG])
def checker(record,suffix):return next(r for r in record['fingerprints'] if r['role']=='checker' and r['path'].endswith(suffix))
old=build('tmp-original');oldhash=sha(old);before=record('original-before',old)
assert before['producer']['path']==str(COPY/'crates/kernel/src/lib.rs'), 'build artifact has wrong CARGO_MANIFEST_DIR'
f=COPY/'crates/kernel/src/output.rs';original=f.read_text();claim='Rust 受限内核的有限条件轨迹；不作全称或完整目标认证';marker='R2_TMP_NEW_SOURCE_PRODUCER_MARKER';assert original.count(claim)==1
modified=original.replace(claim,marker);f.write_text(modified)
(D/'existing-source-change.log').write_text(''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),fromfile='output.rs:before',tofile='output.rs:after')))
after=record('old-binary-new-source',old);assert sha(old)==oldhash
vold=verify('verify-old-on-new-source-record',old,D/'old-binary-new-source.json');vpre=verify('verify-old-on-pre-edit-record',old,D/'original-before.json')
assert vold.returncode==0 and vpre.returncode==2
new=build('tmp-marker');fresh=record('rebuilt-new-source',new);vnew=verify('verify-new-on-old-record',new,D/'old-binary-new-source.json');assert vnew.returncode==2
existing={'old_binary':str(old),'old_binary_sha256_before':oldhash,'old_binary_sha256_after':sha(old),'new_binary':str(new),'new_binary_sha256':sha(new),'source_sha256_before':hashlib.sha256(original.encode()).hexdigest(),'source_sha256_after':sha(f),'old_output_fingerprint_before':checker(before,'/output.rs'),'old_output_fingerprint_after':checker(after,'/output.rs'),'old_output_claim_before':before['producer']['claim'],'old_output_claim_after':after['producer']['claim'],'rebuilt_output_claim':fresh['producer']['claim'],'old_before_vs_after_diff':changes(before,after),'old_after_vs_rebuilt_diff':changes(after,fresh),'verify_exit_codes':{'old_on_new_source_record':vold.returncode,'old_on_pre_edit_record':vpre.returncode,'new_on_old_record':vnew.returncode}}
assert existing['old_output_fingerprint_after']['sha256']==existing['source_sha256_after']!=existing['source_sha256_before']
assert after['producer']['claim']==claim and fresh['producer']['claim']==marker
# Add a real compiled module, leave fingerprints' hand-written list untouched.
lib=COPY/'crates/kernel/src/lib.rs';lib_before=lib.read_text();lib.write_text(lib_before+'\npub mod r2_omitted_probe;\n')
mod=COPY/'crates/kernel/src/r2_omitted_probe.rs';mod.write_text('pub const CLAIM: &str = "R2_MODULE_A";\n')
with_module=modified.replace('"claim":"'+marker+'"','"claim":crate::r2_omitted_probe::CLAIM');assert with_module!=modified;f.write_text(with_module)
(D/'module-wiring-change.log').write_text(''.join(difflib.unified_diff(modified.splitlines(True),with_module.splitlines(True),fromfile='output.rs:marker',tofile='output.rs:module'))+'\nlib.rs addition:\npub mod r2_omitted_probe;\n')
a=build('module-a');ra=record('module-a-record',a);hash_a=sha(mod);mod.write_text('pub const CLAIM: &str = "R2_MODULE_B";\n');hash_b=sha(mod)
va=verify('verify-module-a-after-module-edit',a,D/'module-a-record.json');assert va.returncode==0
b=build('module-b');rb=record('module-b-record',b)
assert ra['fingerprints']==rb['fingerprints']
assert not any(r['path']==str(mod) for r in ra['fingerprints'])
assert ra['producer']['claim']=='R2_MODULE_A' and rb['producer']['claim']=='R2_MODULE_B'
module={'module_path':str(mod),'module_sha256_a':hash_a,'module_sha256_b':hash_b,'binary_a':str(a),'binary_b':str(b),'binary_sha256_a':sha(a),'binary_sha256_b':sha(b),'present_in_fingerprints':False,'fingerprints_equal':True,'context_bindings_equal':ra['evidence_scope']['context_bindings']==rb['evidence_scope']['context_bindings'],'full_record_differences':changes(ra,rb),'verify_old_binary_after_module_only_edit_exit':va.returncode,'module_source_a':'pub const CLAIM: &str = "R2_MODULE_A";\n','module_source_b':mod.read_text()}
dump(D/'summary.json',{'copy_root':str(COPY),'build_argv':buildargs,'existing_source':existing,'new_module':module})
print(json.dumps({'existing_source':{'old_sha_unchanged':True,'new_source_hash_emitted_by_old_binary':True,'old_binary_keeps_old_claim':True,'old_verifier_accepts':True,'new_verifier_rejects':True},'new_module':{'compiled':True,'omitted':True,'fingerprints_equal':True,'changed_output_paths':[d['path'] for d in changes(ra,rb)]},'copy_root':str(COPY)},ensure_ascii=False,indent=2))
