"""交付文件、引用目标、输入稳定性和最终JSON形状检查。"""
from pathlib import Path
import json,hashlib,re,datetime

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'复核108S2B.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((HERE/'inputs.json').read_text())
assert all(sha(Path(r['path']))==r['sha256'] for r in inputs),'复核材料在核验后发生改变'
validation=json.loads((HERE/'validation.json').read_text())
assert validation['status']=='passed' and validation['numeric_encodings_equal']
for name,digest in validation['python_sources'].items():assert sha(HERE/name)==digest
for name,digest in validation['result_files'].items():assert sha(HERE/name)==digest
links=[]
for doc in [REPORT,HERE/'reader_audit.md']:
    for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
        assert not target.startswith(('http:','https:'))
        p=(doc.parent/target).resolve();assert p.exists(),str(p)
        links.append({'document':doc.name,'target':target})
report=REPORT.read_text()
assert '**未否证**' in report and '复核完成' in report
assert all(x in report for x in ['98240','28860','4713','11913','74896','83007'])
verdict={'status':'done','report_path':str(REPORT),'verdicts':[{
 'name':'全厂满库存成品机隔离接法达标（桥接器交叉版）','verdict':'未否证',
 'reason':'桥轴递推、调试和两种离线读法均通过复核。','revised_text':''}]}
assert set(verdict)=={'status','report_path','verdicts'}
assert len(verdict['verdicts'])==1 and verdict['verdicts'][0]['verdict'] in ('未否证','已否证','修正')
(HERE/'verdict.json').write_text(json.dumps(verdict,ensure_ascii=False,indent=2)+'\n')
result={'status':'passed','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'report_path':str(REPORT),'report_sha256':sha(REPORT),'report_lines':len(report.splitlines()),
        'reader_audit_sha256':sha(HERE/'reader_audit.md'),'checked_markdown_links':len(links),
        'inputs_unchanged':True,'verdict_schema_valid':True,
        'files':{p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='delivery_check.json'}}
(HERE/'delivery_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'passed','report_sha256':result['report_sha256'],'checked_markdown_links':len(links),'verdict':verdict},ensure_ascii=False,indent=2))
