import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[2] / 'lit.py'
spec = importlib.util.spec_from_file_location('lit_task', SOURCE)
lit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lit)
lit.CACHE = str(ROOT / 'cache')
lit.BUDGET_FILE = str(ROOT / 'cache' / '_openalex_budget.json')
lit.main()
