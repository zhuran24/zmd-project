from probe_common import *
import re,ast
report=OUT.parent/'R2-来源与计时.md'
checks={}
missing=[]
for p in [report,OUT/'commands.md']:
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if not (p.parent/target).exists():missing.append({'document':str(p),'target':target})
checks['broken_links']=missing
checks['unexpected_file_extensions']=[str(p) for p in OUT.rglob('*') if p.is_file() and p.suffix not in ['.py','.rs','.sh','.log','.json','.md']]
checks['python_parse_errors']=[]
for p in OUT.glob('*.py'):
 try:ast.parse(p.read_text())
 except SyntaxError as e:checks['python_parse_errors'].append(str(e))
rows=json.loads((OUT/'aa/results.json').read_text());checks['aa_pair_count']=len(rows)
checks['aa_binary_identity_mismatch']=[];checks['aa_command_mismatch']=[];checks['raw_output_hash_mismatch']=[]
for r in rows:
 d=OUT/'aa'/r['name'];a=json.loads((d/'a.command.json').read_text());b=json.loads((d/'b.command.json').read_text())
 if a['argv']!=b['argv'] or a['cwd']!=b['cwd']:checks['aa_command_mismatch'].append(r['name'])
 if sha(r['argv'][0])!=r['binary_sha256']:checks['aa_binary_identity_mismatch'].append(r['name'])
 for label,meta in [('a',a),('b',b)]:
  for channel in ['stdout','stderr']:
   if sha(d/(label+'.'+channel+'.log'))!=meta[channel+'_sha256']:checks['raw_output_hash_mismatch'].append([r['name'],label,channel])
checks['input_hash_mismatch']=[p for p,h in json.loads((OUT/'baseline.json').read_text())['inputs'].items() if sha(p)!=h]
# Recheck the protected subset now, without re-inventorying ongoing sibling outputs.
a=json.loads((OUT/'protected-before.json').read_text())
from summarize_protection import protected
checks['protected_existing_files']=sum(protected(p) for p in a)
checks['protected_content_mismatch']=[p for p,v in a.items() if protected(p) and (not (ROOT.parent/p).exists() or ('sha256' in v and sha(ROOT.parent/p)!=v['sha256']))]
checks['reader_review']={'complete':True,'basis':'Full report reread after generation; corrected empty CLI argument cell, stated profile timing limitation, checked scope, counts, classification and links.'}
assert len(rows)==44
assert all(not checks[k] for k in ['broken_links','unexpected_file_extensions','python_parse_errors','aa_binary_identity_mismatch','aa_command_mismatch','raw_output_hash_mismatch','input_hash_mismatch','protected_content_mismatch']),checks
dump(OUT/'delivery-validation.json',checks)
# Audit manifest contains only path/length/digest, never copies of source trees or binaries.
manifest={str(p.relative_to(OUT.parent)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='artifact-manifest.json'}
manifest[report.name]={'bytes':report.stat().st_size,'sha256':sha(report)}
dump(OUT/'artifact-manifest.json',manifest)
print(json.dumps(checks,ensure_ascii=False,indent=2))
