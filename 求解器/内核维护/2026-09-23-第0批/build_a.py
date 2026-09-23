import os,json,shutil
from pathlib import Path
from ops import *
S=Path(os.environ["HEALTH_SRC"]);profile=os.environ["HEALTH_PROFILE"]
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
args=["cargo","build","--locked","--offline","--workspace","--bins","-j","1","--profile",profile,"--config",f'profile.{profile}.inherits="dev"',"--config",f'profile.{profile}.codegen-units=1',"--message-format=json"]
command("production-a-observed-build",args,S)
rows=[json.loads(x) for x in (RUN/"production-a-observed-build.stdout.log").read_text().splitlines() if x.startswith("{")]
artifacts=[r for r in rows if r.get("reason")=="compiler-artifact" and str(S) in r.get("manifest_path","")]
seal=Path(os.environ["CARGO_TARGET_DIR"])/"health-capture"/RUN.name/"sealed-binaries-a";seal.mkdir(parents=True)
for name in ("kernel","topology"):
 r=next(r for r in artifacts if r["target"]["name"]==name and "bin" in r["target"]["kind"] and not r["profile"]["test"])
 assert not r["fresh"] and Path(r["manifest_path"]).is_relative_to(S)
 shutil.copyfile(r["executable"],seal/name);r["sha256"]=sha(r["executable"])
write(RUN/"production-a-artifacts.json",artifacts)
write(RUN/"production-a-source.json",guarded.g.scan(S))
