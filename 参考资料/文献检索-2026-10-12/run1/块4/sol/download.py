#!/usr/bin/env python3
"""Bounded first-party PDF acquisition, with local extraction and provenance."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import requests

out = Path(__file__).resolve().parent
docs = out / '全文'
docs.mkdir(exist_ok=True)
sources = {
    'AdyaMarkov2003': 'https://web.eecs.umich.edu/~imarkov/pubs/jour/tvlsi03-fixedFP.pdf',
    'Alagoz2008': 'https://www.eng.auburn.edu/~aesmith/files/IEE%20Tr%20Spec%20Issue%20Aisles%20Published%20Paper.pdf',
    'Daniels1997': 'https://cogcomp.seas.upenn.edu/papers/maaprJ.pdf',
    'Btree': 'https://cc.ee.ntu.edu.tw/~ywchang/Papers/tcad-btree.pdf',
    'Lpacking2021': 'https://people.idsia.ch/~grandoni/Pubblicazioni/GGIHKW21talg.pdf',
    'Piano2025': 'https://arxiv.org/pdf/2508.13161',
    'Phi2025': 'https://www.mdpi.com/2227-7390/13/3/493/pdf',
}
def fetch(item):
    name, url = item
    result = {'name': name, 'url': url}
    try:
        r = requests.get(url, stream=True, timeout=35)
        r.raise_for_status()
        max_size = 100 * 1024 * 1024
        length = int(r.headers.get('Content-Length', 0))
        if length >= max_size:
            raise ValueError('PDF over size limit')
        data = bytearray()
        for chunk in r.iter_content(65536):
            data.extend(chunk)
            if len(data) >= max_size:
                raise ValueError('PDF over size limit')
        if not data.startswith(b'%PDF'):
            raise ValueError('response is not a PDF')
        pdf = docs / (name + '.pdf')
        pdf.write_bytes(data)
        txt = docs / (name + '.txt')
        subprocess.run(['pdftotext', '-layout', str(pdf), str(txt)], check=True)
        result.update(bytes=len(data), text=str(txt), status='downloaded')
    except Exception as e:
        result.update(status='unavailable', error=str(e))
    return result
with ThreadPoolExecutor(max_workers=5) as pool:
    records = list(pool.map(fetch, sources.items()))
(out / '全文来源.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
for record in records:
    print(json.dumps(record, ensure_ascii=False), flush=True)
