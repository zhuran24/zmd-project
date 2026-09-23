import json,os
from continuation_b import *
from continuation_build_inputs import verify as verify_build
snapshot=json.loads((RUN/'continuation-b-source.json').read_text());check('b2-start');frozen(snapshot);verify_build()
for crate in ['kernel','topology']:
 for name in ['lib.rs','main.rs']:os.utime(S/'crates'/crate/'src'/name,None)
command('continue-production-b4',['cargo','build','--workspace','--bins',*cargo_args(f['continuation_profile']),'--message-format=json'],S)
art=artifacts('continue-production-b4');old=json.loads((RUN/'continuation-production-a-artifacts.json').read_text());rows=[]
for a in art:
 if a.get('executable'):
  before=next(x for x in old if x['target']['name']==a['target']['name'] and x.get('executable'));assert not a['fresh'];equal=Path(before['sealed']).read_bytes()==Path(a['executable']).read_bytes();rows.append(dict(name=a['target']['name'],before=before['sha256'],after=sha(a['executable']),byte_equal=equal,path=a['executable']));assert equal
write(RUN/'production-byte-equivalence.json',dict(passed=True,profile=f['continuation_profile'],source_root=str(S),binaries=rows,final_test_version='R3 fixture paths relocated; hashes preserved'));verify_build();frozen(snapshot)
bounded_probes(snapshot);profile,tests,art=harnesses(snapshot);isolation(snapshot,profile,tests,art);safe(snapshot);verify_build()
