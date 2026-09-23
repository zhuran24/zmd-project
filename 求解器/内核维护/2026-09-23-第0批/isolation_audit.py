import os,json,shutil,subprocess,importlib.util,ast
from pathlib import Path
from ops import *
S=Path(os.environ["HEALTH_SRC"]);R=Path(os.environ["HEALTH_REPO"])
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
# Only the declared test infrastructure overlay; production and runtime validation sources stay byte-identical.
overlay=[]
for rel in sorted(guarded.ALLOWED):
 p=R.parent/rel
 if p.is_file():
  dest=S/p.relative_to(R);dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(p,dest);overlay.append(dict(path=str(p.relative_to(R)),sha256=sha(p)))
write(RUN/"test-overlay.json",overlay)
profile=os.environ["HEALTH_PROFILE"]
args=["cargo","build","--locked","--offline","--workspace","--bins","-j","1","--profile",profile,"--config",f'profile.{profile}.inherits="dev"',"--config",f'profile.{profile}.codegen-units=1',"--message-format=json"]
command("production-b-build",args,S)
rows=[json.loads(x) for x in (RUN/"production-b-build.stdout.log").read_text().splitlines() if x.startswith("{")]
artifacts=[r for r in rows if r.get("reason")=="compiler-artifact" and str(S) in r.get("manifest_path","")]
byte_results=[]
for name in ("kernel","topology"):
 r=next(r for r in artifacts if r["target"]["name"]==name and "bin" in r["target"]["kind"] and not r["profile"]["test"])
 a=Path(os.environ["CARGO_TARGET_DIR"])/"health-capture"/RUN.name/"sealed-binaries-a"/name
 byte_results.append(dict(name=name,before=sha(a),after=sha(r["executable"]),byte_equal=a.read_bytes()==Path(r["executable"]).read_bytes(),fresh=r["fresh"]))
write(RUN/"production-byte-equivalence.json",byte_results);assert all(r["byte_equal"] for r in byte_results)
# Distinct test profile is mandatory even though the production bytes matched.
profile="health0tests"+str(os.getpid());os.environ["HEALTH_PROFILE"]=profile
with (RUN/"test-env.sh").open("w") as f:f.write((RUN/"env.sh").read_text()+"export HEALTH_PROFILE="+profile+"\n")
args=["cargo","test","--locked","--offline","--workspace","--tests","--no-run","-j","1","--profile",profile,"--config",f'profile.{profile}.inherits="dev"',"--config",f'profile.{profile}.codegen-units=1',"--message-format=json"]
command("test-build",args,S)
rows=[json.loads(x) for x in (RUN/"test-build.stdout.log").read_text().splitlines() if x.startswith("{")]
artifacts=[r for r in rows if r.get("reason")=="compiler-artifact" and str(S) in r.get("manifest_path","")]
harnesses=[r for r in artifacts if r.get("executable") and r["profile"]["test"]]
meta=json.loads(subprocess.check_output(["cargo","metadata","--locked","--offline","--no-deps","--format-version","1"],cwd=S))
expected={(p["manifest_path"],t["name"],tuple(t["kind"])) for p in meta["packages"] for t in p["targets"] if t["test"]}
actual={(r["manifest_path"],r["target"]["name"],tuple(r["target"]["kind"])) for r in harnesses}
assert actual==expected,(actual,expected)
for r in artifacts:
 assert not r["fresh"],r
 assert Path(r["manifest_path"]).is_relative_to(S) and Path(r["target"]["src_path"]).is_relative_to(S)
 if r.get("executable"):
  r["sha256"]=sha(r["executable"])
  assert str(S).encode() in Path(r["executable"]).read_bytes()
write(RUN/"test-harnesses.json",harnesses);write(RUN/"test-artifacts.json",artifacts);write(RUN/"cargo-metadata.json",meta)
source=guarded.g.scan(S);write(RUN/"isolation-source.json",source)
for index,r in enumerate(harnesses):
 command("list-"+str(index),[r["executable"],"--list"],S)
# Direct harnesses only. Each invocation is protected and the frozen source is checked after it.
results=[]
for round_no in (1,2):
 for index,r in enumerate(harnesses):
  assert sha(r["executable"])==r["sha256"]
  label=f"isolation-{round_no}-{index}-{r['target']['name']}"
  command(label,[r["executable"],"--test-threads=1","--nocapture"],S if round_no==1 else S.parent)
  assert not guarded.g.changes(source,guarded.g.scan(S)),"frozen source changed"
  results.append(dict(round=round_no,target=r["target"],log=label))
write(RUN/"isolation-rounds.json",results)
