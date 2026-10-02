"""Check compensation for overlap between rectangle ring and ore-source cells.
This is a NECESSARY relaxation, never a full factory counterexample.
"""
import argparse,json,time
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('encoding',choices=['a','b']);args=ap.parse_args()
OUT=Path(__file__).resolve().parent
if args.encoding=='a':
    from corner_a import solve,ports
else:
    from corner_b import run,locations
records=[];violations=[];skipped=0;start=time.monotonic()
for gl in range(0,70,3):
    for gb in range(0,70,3):
        if gl and gb:continue
        for h in range(6,10):
            for b in range(3,70-h):
                pp=ports(gl) if args.encoding=='a' else locations(gl//3)
                overlap=sum(b<=y<b+h for y in pp)
                if overlap>2:continue
                rect=(2,b,6,h)
                for mode in ([0,1,2] if 0<max(gl,gb)<69 else [0]):
                    result=solve(gl,gb,mode,rect) if args.encoding=='a' else run(gl//3,gb//3,mode,rect)
                    if result is None:skipped+=1;continue
                    row=[gl,gb,h,b,mode,result['bound'],overlap,result['bound']+overlap]
                    records.append(row)
                    if row[-1]>91:
                        violations.append({'row':row,'local_relaxation':result})
        print(json.dumps({'encoding':args.encoding,'left_gap':gl,'bottom_gap':gb,'cases':len(records),'violations':len(violations),'seconds':time.monotonic()-start}),flush=True)
result={'encoding':args.encoding,'columns':['left_gap','bottom_gap','height','bottom','mode','N_plus_w_upper','ring_overlap','sum_upper'],'cases':records,'incompatible_fixed_machine':skipped,'violations':violations,'maximum':max(r[-1] for r in records),'seconds':time.monotonic()-start}
(OUT/f'scope_{args.encoding}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'encoding':args.encoding,'completed':len(records),'maximum':result['maximum'],'violations':len(violations)}))
