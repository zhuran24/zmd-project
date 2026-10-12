#!/usr/bin/env python3
import importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
out=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("lit_core", '/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索/lit.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
old_budget=Path(core.BUDGET_FILE)
core.CACHE=str(out/"cache");Path(core.CACHE).mkdir(exist_ok=True)
core.BUDGET_FILE=str(out/"cache"/"_openalex_budget.json")
if old_budget.exists() and (not Path(core.BUDGET_FILE).exists() or json.loads(old_budget.read_text()).get("at",0) > json.loads(Path(core.BUDGET_FILE).read_text()).get("at",0)):
 b=json.loads(old_budget.read_text())
 # Native tool owns the daily budget and any credential setup; copy only budget metadata.
 Path(core.BUDGET_FILE).write_text(json.dumps(b))
def __getattr__(name):return getattr(core,name)
if __name__=="__main__":core.main()
