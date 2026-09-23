#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
run=Path(__file__).resolve().parent
args=sys.argv[1:]+["-Zthreads=1","-Zno-parallel-backend"]
with (run/"rustc-invocations.jsonl").open("a") as f:f.write(json.dumps(args)+"\n")
os.execvp(args[0],args)
