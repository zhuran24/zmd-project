#!/usr/bin/env python3
"""Acquire metadata/full text using supplied lit.py; bounded downloads, local cache."""
import importlib.util
import json
import os
import sys
import subprocess
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lit', ROOT.parent.parent.parent / 'lit.py')
lit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lit)
lit.CACHE = str(ROOT / 'cache')
lit.BUDGET_FILE = str(ROOT / 'cache/_openalex_budget.json')
original_get = lit.requests.get

def bounded_get(url, **kwargs):
    kwargs['stream'] = True
    response = original_get(url, **kwargs)
    cap = 99_000_000
    if int(response.headers.get('Content-Length', '0')) > cap:
        response.close()
        raise RuntimeError('download exceeds local 99 MB limit')
    chunks, size = [], 0
    for chunk in response.iter_content(65536):
        size += len(chunk)
        if size > cap:
            response.close()
            raise RuntimeError('download exceeds local 99 MB limit')
        chunks.append(chunk)
    response._content = b''.join(chunks)
    response._content_consumed = True
    response.close()
    return response

lit.requests.get = bounded_get
mode = sys.argv[1]
for key in sys.argv[2:]:
    try:
        if mode == 'add':
            record = lit._norm_oa(lit.resolve(key))
            lit.add_pool(str(ROOT / 'pool.jsonl'), [record], 'web/direct:' + key)
            print(json.dumps(record, ensure_ascii=False), flush=True)
        elif mode == 'full':
            path = lit.full(key)
            print(key, path, flush=True)
            with (ROOT / 'fulltexts.jsonl').open('a') as out:
                out.write(json.dumps({'key': key, 'path': path}, ensure_ascii=False) + '\n')
        elif mode == 'fetch':
            import hashlib
            base = ROOT / 'cache' / ('direct_' + hashlib.sha1(key.encode()).hexdigest()[:16])
            response = bounded_get(key, timeout=40)
            response.raise_for_status()
            if response.content.startswith(b'%PDF'):
                base.with_suffix('.pdf').write_bytes(response.content)
                subprocess.run(['pdftotext', '-layout', str(base.with_suffix('.pdf')), str(base.with_suffix('.txt'))], check=True)
                path = str(base.with_suffix('.txt'))
            else:
                base.with_suffix('.html').write_text(response.text)
                path = str(base.with_suffix('.html'))
            print(key, path, 'bytes', len(response.content), flush=True)
            with (ROOT / 'fulltexts.jsonl').open('a') as out:
                out.write(json.dumps({'url': key, 'path': path, 'bytes': len(response.content)}, ensure_ascii=False) + '\n')
    except (Exception, SystemExit) as error:
        print('ERROR', key, str(error), flush=True)
