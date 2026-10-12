from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json

out = Path(__file__).resolve().parent
ns = {'__file__': str(out / 'download.py')}
source = (out / 'download.py').read_text().split('with ThreadPoolExecutor')[0]
exec(compile(source, str(out / 'download.py'), 'exec'), ns)
sources = {
 'FeketeCharacterization': 'https://www.ibr.cs.tu-bs.de/users/fekete/hp/publications/PDF/2004-A_Combinatorial_Characterization_of_Higher-Dimensional_Orthogonal_Packing.pdf',
 'FeketeExact': 'https://www.ibr.cs.tu-bs.de/users/fekete/hp/publications/PDF/2007-An_Exact_Algorithm_for_Higher-Dimensional_Orthogonal_Packing.pdf',
 'Church1974': 'https://people.geog.ucsb.edu/~forest/G294download/MAX_COVER_RLC_CSR.pdf',
 'IntegratedAisle2021': 'https://hal.science/hal-03021331/document',
 'Chan2021': 'https://arxiv.org/pdf/2103.08043',
 'Zone2023': 'https://arxiv.org/pdf/2309.02453',
 'CornerTheorem2012': 'https://arxiv.org/pdf/1107.4463',
}
with ThreadPoolExecutor(max_workers=5) as pool:
 records = list(pool.map(ns['fetch'], sources.items()))
(out / '全文来源_补充.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
for r in records: print(json.dumps(r, ensure_ascii=False))
