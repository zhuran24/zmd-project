import json,sys
p=sys.argv[1]; drop=set(sys.argv[2:])
L=[json.loads(l) for l in open(p) if l.strip()]
keep=[r for r in L if r['key'] not in drop]
open(p,'w').write(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in keep))
print(len(L),'->',len(keep))
