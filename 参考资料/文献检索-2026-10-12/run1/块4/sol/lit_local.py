#!/usr/bin/env python3
"""Run the supplied lit.py with cache writes confined to this output directory."""
from pathlib import Path
import json
import sys

out = Path(__file__).resolve().parent
original = out.parents[2] / 'lit.py'
# sol -> 块4 -> run1 -> 文献检索
original = out.parent.parent.parent / 'lit.py'
cache = out / 'cache'
cache.mkdir(exist_ok=True)
budget = original.parent / 'cache' / '_openalex_budget.json'
if budget.exists():
    (cache / '_openalex_budget.json').write_text(budget.read_text(), encoding='utf-8')
source = original.read_text(encoding='utf-8')
source = source.replace('ROOT = os.path.dirname(os.path.abspath(__file__))', 'ROOT = ' + repr(str(out)))
with (out / '工具调用.jsonl').open('a', encoding='utf-8') as log:
    log.write(json.dumps({'argv': sys.argv[1:]}, ensure_ascii=False) + '\n')
exec(compile(source, str(original), 'exec'), {'__name__': '__main__', '__file__': str(original)})
