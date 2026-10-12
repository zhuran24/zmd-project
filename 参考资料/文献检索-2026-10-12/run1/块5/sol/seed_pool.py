import importlib.util, json
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('lit_task',root.parents[2]/'lit.py')
lit=importlib.util.module_from_spec(spec);spec.loader.exec_module(lit)
lit.CACHE=str(root/'cache');lit.BUDGET_FILE=str(root/'cache/_openalex_budget.json')
seeds=['10.1007/s001860400376','10.1016/j.cor.2006.05.012','10.1016/j.cor.2005.08.012','10.1111/j.1475-3995.2009.00713.x','10.1287/opre.47.5.730','10.1016/j.dam.2014.05.017','10.4230/LIPIcs.CP.2024.11']
for k in seeds:
 try:
  r=lit._norm_oa(lit.resolve(k));lit.add_pool(str(root/'pool.jsonl'),[r],'web-seed:'+k)
  print(k,r['key'],r['title'])
 except Exception as e: print(k,'ERROR',str(e))
(root/'chain_seeds.json').write_text(json.dumps(seeds,ensure_ascii=False,indent=2))
