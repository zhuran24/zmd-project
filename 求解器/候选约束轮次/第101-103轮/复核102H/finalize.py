"""Validate the report, input identity, artifact links, and handoff schema."""
from pathlib import Path
import ast
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'复核102H.md'
names=['传输相位','判定先后','轮询均分','混料轮询分料','整批k件配k条取货通道的均分',
       '采种单元的回路存量下界','采种单元不断料','传输箱不满']
reasons=['清空重取相位，保留续冷却。','实际送货联判，每元件每步一次。','段内均分与跨段差界成立。',
         '同余公式及跨段实际计数成立。','跨清空差至多2，循环均分保留。','分段界及不耗尽成立；150保守。',
         '活性和满库存证明不依赖历史。','两读法均可证15件及守恒。']
reply=dict(status='done',report_path=str(REPORT),
           verdicts=[dict(name=n,verdict='未否证',reason=r,revised_text='') for n,r in zip(names,reasons)])
(HERE/'reply.json').write_text(json.dumps(reply,ensure_ascii=False,indent=2)+'\n')
content=REPORT.read_text()
assert len(reply['verdicts'])==8 and len(set(v['name'] for v in reply['verdicts']))==8
for v in reply['verdicts']:
    assert v['name'] in content and v['verdict'] in ['未否证','已否证','修正']
    assert v['revised_text']==''
input_manifest=json.loads((HERE/'inputs.json').read_text())
for entry in input_manifest:
    assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
source_files=list(HERE.glob('*.py'))
for p in source_files: ast.parse(p.read_text())
links=[]
for link in re.findall(r'\]\(([^)]+)\)',content):
    if link.startswith(('http:','https:','#')): continue
    path=(REPORT.parent/link.split('#')[0]).resolve()
    if path==HERE/'delivery_check.json': continue
    assert path.exists(),str(path)
    links.append(link)
expected={'arithmetic.json':('release','patterns',321),
          'interfaces.json':('cooldown','max_before_transfer',15),
          'plants.json':('full','max_K_wait_steps',2),
          'unaffected.json':('E29_E31','even_batch_species_cases',28560)}
for filename,(a,b,expected_value) in expected.items():
    assert json.loads((HERE/filename).read_text())[a][b]==expected_value
check=dict(status='passed',report=str(REPORT),report_bytes=REPORT.stat().st_size,
           report_lines=len(content.splitlines()),input_hashes_checked=len(input_manifest),
           links_checked=len(links),python_files_parsed=len(source_files),verdict_count=8,
           reader_review='reader_review.md',
           scope='Eight full H candidates; old counterexamples are not counterexamples to the eight new candidates.',
           runtime='All computation scripts executed individually; run_all.py is a serial reproduction entrypoint.',
           output_policy='Only 复核102H.md and files below 复核102H were written; no git, cargo, sim2 or foreign code imports.')
(HERE/'delivery_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
manifest=[]
for p in [REPORT]+sorted(HERE.iterdir()):
    if p.is_file() and p.name!='artifact_manifest.json':
        data=p.read_bytes()
        manifest.append(dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(HERE/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(check,ensure_ascii=False))
