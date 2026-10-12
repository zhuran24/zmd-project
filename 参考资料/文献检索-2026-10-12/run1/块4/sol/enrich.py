#!/usr/bin/env python3
from pathlib import Path
import json
import sys
out = Path(__file__).resolve().parent
original = out.parent.parent.parent / 'lit.py'
source = original.read_text().replace('ROOT = os.path.dirname(os.path.abspath(__file__))', 'ROOT = ' + repr(str(out)))
ns = {'__name__': 'task_lit', '__file__': str(original)}
exec(compile(source, str(original), 'exec'), ns)
pool = str(out / 'pool.jsonl')
for key in sys.argv[1:]:
    try:
        rec = ns['_norm_oa'](ns['resolve'](key))
        added = ns['add_pool'](pool, [rec], 'web-title-and-resolve:' + key)
        print(json.dumps(rec, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'key': key, 'error': str(error)}, ensure_ascii=False))
