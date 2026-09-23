import json,sys
from audit_files import *
sys.path.insert(0,str(IMPL));import continuation_aa as m
from audit_retained import compare
results=[]
def rejects(name,fn):
    try:fn()
    except (AssertionError,KeyError,ValueError,OSError) as e:results.append(dict(name=name,rejected=True,error=str(e)))
    else:raise AssertionError('accepted negative '+name)
a=b'{"elapsed_ns":"1","value":[1,2]}\n'
assert m.compare_bytes(a,b'{"elapsed_ns":"2","value":[1,2]}\n',True)
for name,b in [('missing',b'{"value":[1,2]}\n'),('wrong-type',b'{"elapsed_ns":2,"value":[1,2]}\n'),('swapped-array',b'{"elapsed_ns":"1","value":[2,1]}\n'),('reordered-json',b'{"value":[1,2],"elapsed_ns":"1"}\n'),('indent',b'{ "elapsed_ns":"1","value":[1,2]}\n'),('unregistered',b'{"elapsed_ns":"1","value":[1,3]}\n'),('duplicate-key',b'{"elapsed_ns":"1","elapsed_ns":"1","value":[1,2]}\n')]:
    rejects(name,lambda b=b:m.compare_bytes(a,b,True));rejects('independent-'+name,lambda b=b:compare(a,b,True))
rejects('wrong-source-map',lambda:m.compare_bytes(b'{"producer":{"path":"/a"}}',b'{"producer":{"path":"/b"}}'))
s=OUT/'comparator-negative';s.mkdir();(s/'target.json').write_text('{}\n');(s/'bad.json').write_text(json.dumps(dict(path='target.json',sha256='0'*64)));(s/'missing.json').write_text(json.dumps(dict(path='absent.json',sha256='0'*64)))
rejects('bad-reference-hash',lambda:m.references(s/'bad.json',[s]));rejects('missing-reference',lambda:m.references(s/'missing.json',[s]));save('comparator-probes.json',dict(passed=True,cases=results))
print('comparator rejects',len(results))
