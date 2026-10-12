import importlib.util,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('lit_task',root.parents[2]/'lit.py')
lit=importlib.util.module_from_spec(spec);spec.loader.exec_module(lit)
lit.CACHE=str(root/'cache');lit.BUDGET_FILE=str(root/'cache/_openalex_budget.json')
for k in sys.argv[1:]:
 try:
  r=lit._norm_oa(lit.resolve(k));new=lit.add_pool(str(root/'pool.jsonl'),[r],'web-primary:'+k)
  print(k,r['key'],r['title'],'added',len(new))
 except Exception as e: print(k,'ERROR',str(e))
