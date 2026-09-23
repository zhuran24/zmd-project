from guard import ROOT,REPO,OUT,save,digest,guard
from pathlib import Path
from datetime import datetime,timezone
import json,re,subprocess
p=OUT/'记录.md';text=p.read_text()
text=text.replace('全部位于 `kernel/src/tests_bridge.rs`','全部位于 `crates/kernel/src/tests_bridge.rs`')
text=text.replace('原有未跟踪 `求解器/老项目/` 不属本轮。','原有／并行未跟踪的 `求解器/老项目/` 和 `求解器/规则修订/2026-09-22-桥接器/` 不属本轮，未修改。')
p.write_text(text)
missing=[]
for file in [OUT/'记录.md',OUT/'changed-files.md']:
    for target in re.findall(r'\]\(([^)]+)\)',file.read_text()):
        if not (file.parent/target).exists():missing.append(str(file)+':'+target)
assert not missing,missing
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip()
initial_head=(OUT/'initial-head.txt').read_text().strip()
concurrent=subprocess.check_output(['git','diff','--name-only','-z',initial_head,head],cwd=REPO).decode().split('\0')
concurrent=[name for name in concurrent if name]
business={r['path'] for r in json.loads((OUT/'changed-files.json').read_text())}
assert not business.intersection(concurrent), '并行提交涉及本轮业务文件，须另行核验'
save('concurrent-head.json',{'initial_head':initial_head,'delivery_head':head,'changed_paths':concurrent,'overlap_with_business':[]})
text=p.read_text()
if head!=initial_head:
    text+=f'\n交付自审观察到并行会话提交 `{head}`（老项目归档）；逐路径核对与本轮94个业务文件交集为空，见 [concurrent-head.json](concurrent-head.json)。本轮未进行提交，七份受保护文件仍按开工HEAD核验。\n'
p.write_text(text)
(OUT/'final-status.txt').write_bytes(subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=normal'],cwd=REPO))
summary=json.loads((OUT/'summary.json').read_text());summary['delivery_head']=head;summary['concurrent_commit_business_overlap']=[]
save('summary.json',summary)
# Refresh the delivery snapshot under the same label, without changing its count.
guard('delivery')
save('reader-review.json',{'status':'pass','reviewed_utc':datetime.now(timezone.utc).isoformat(),
    'record_sha256':digest(p),'checked':['self-contained scope and chronology','current numbers versus historical iterations','eight test names and source location','all local links resolve','unresolved failures and out-of-scope issues separated','94 business files versus unrelated untracked work','history and seven protected files unchanged'],
    'fixed':['constraint section row number collision','remaining bridge capacity paragraph','full schema last_unit field in both Content and CycleKey','precise new unit-test path','separate concurrent untracked directories'],
    'remaining_issues':[]})
files=[{'path':str(f.relative_to(OUT)),'bytes':f.stat().st_size,'sha256':digest(f)} for f in sorted(OUT.rglob('*')) if f.is_file() and f.name!='artifacts.json']
save('artifacts.json',files)
print(json.dumps({'reader_review':'pass','record':str(p),'record_files':len(files)},ensure_ascii=False))
