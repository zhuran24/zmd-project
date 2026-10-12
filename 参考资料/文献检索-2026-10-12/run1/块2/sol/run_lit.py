#!/usr/bin/env python3
"""Use the supplied lit.py with all cache writes confined to this seat's output."""
import importlib.util
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.abspath(os.path.join(ROOT, '../../../lit.py'))
spec = importlib.util.spec_from_file_location('lit', SOURCE)
lit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lit)
lit.CACHE = os.path.join(ROOT, 'cache')
lit.BUDGET_FILE = os.path.join(lit.CACHE, '_openalex_budget.json')
lit.main()
