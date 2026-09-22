from aa_probe import *
results.extend(json.loads((OUT/'aa/results.json').read_text()))
p=BATCH/'cycle-found.json';rp=BATCH/'cycle-found.record.json'
k('cycle-found-referenced','cycle',INPUT,['--max-ticks',50,'--search-checkpoint-interval',3,'--out',p],[('certificate',p),('record',rp)])
assert json.loads(p.read_text())['cycle'] is not None
k('cycle-found-no-record','cycle',INPUT,['--max-ticks',50,'--no-record'])
k('verify-cycle-found','verify-cycle',p)
cp=ART/'checkpoint-cycle-found.json';k('checkpoint-cycle-found','checkpoint',p,['--out',cp],[('seed',cp)])
pair('verify-batch-with-cycle-found',[BIN,'verify-batch',BATCH,'--config',CFG],expected=0)
dump(OUT/'aa/summary.json',{'pairs':len(results),'unexpected_exits':[r['name'] for r in results if r['unexpected_exit']],'unstable':[{'name':r['name'],'output':key,'differences':value.get('json_differences',value)} for r in results for key,value in {'stdout':r['stdout'],'stderr':r['stderr'],**r['files']}.items() if not value['byte_equal']],'binary_sha256_before':base['binaries'],'binary_sha256_after':{'kernel':sha(BIN),'topology':sha(TOPO)}})
