#!/usr/bin/env python3
"""Run a command with a whole-project content check before and after."""
import os, sys, json, subprocess, time
from pathlib import Path
import bootstrap_guard as g
RUN=Path(__file__).resolve().parent
BASE=json.loads((RUN/"initial-protection.json").read_text())
ALLOWED={"求解器/"+p for p in [
 "数据/工具/kernel_file_guard.py","数据/工具/kernel_regression.py","数据/工具/test_formal_catalog.py",
 "crates/kernel/tests/evidence_paths.py","crates/kernel/tests/support","crates/kernel/tests/support/mod.rs",
 "crates/kernel/tests/benchmark_round6.py",
 *["crates/kernel/tests/"+n+s for n in ("revision_cli","revision_r2_cli","revision_r3_cli","revision_r4_cli","revision_r5_cli","round5_cli","round6_cli") for s in (".rs",".py")]]}
def check(label):
 diff=g.changes(BASE,g.scan(BASE["root"],BASE["excludes"]))
 concurrent=[d for d in diff if d["path"].startswith("求解器/候选约束轮次/第63-65轮/")]
 unexpected=[d for d in diff if d["path"] not in ALLOWED and d not in concurrent]
 g.write(RUN/(label+"-protection.json"),{"unexpected":unexpected,"allowed_changes":[d for d in diff if d["path"] in ALLOWED],"concurrent":concurrent,"history_changed":len(unexpected)})
 if unexpected: raise RuntimeError("protected change; STOP: "+str([x["path"] for x in unexpected]))
def run(label, argv):
 check(label+"-before")
 start=time.time(); env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE="1",GIT_OPTIONAL_LOCKS="0",RUST_TEST_THREADS="1",RAYON_NUM_THREADS="1",OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",CARGO_BUILD_JOBS="1",CARGO_PROFILE_DEV_CODEGEN_UNITS="1",CARGO_PROFILE_TEST_CODEGEN_UNITS="1",CARGO_PROFILE_RELEASE_CODEGEN_UNITS="1",CARGO_TARGET_DIR=str(Path(BASE["root"])/"求解器/target"))
 with (RUN/(label+".stdout.log")).open("wb") as out,(RUN/(label+".stderr.log")).open("wb") as err:
  p=subprocess.Popen(argv,env=env,stdout=out,stderr=err)
  code=p.wait()
 check(label+"-after")
 row={"label":label,"argv":argv,"cwd":os.getcwd(),"exit_code":code,"seconds":time.time()-start,"environment":{k:v for k,v in env.items() if k.startswith(("CARGO_","RUST_","HEALTH_","KERNEL_")) or k in ("PATH","RAYON_NUM_THREADS","OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","PYTHONDONTWRITEBYTECODE","GIT_OPTIONAL_LOCKS")}}
 with (RUN/"commands.jsonl").open("a") as f:f.write(json.dumps(row,ensure_ascii=False)+"\n")
 print(json.dumps({k:row[k] for k in ("label","exit_code","seconds")}),flush=True)
 if code:
  print((RUN/(label+".stderr.log")).read_text()[-5000:]);print((RUN/(label+".stdout.log")).read_text()[-2000:])
 return code
if __name__=="__main__":raise SystemExit(run(sys.argv[1],sys.argv[2:]))
