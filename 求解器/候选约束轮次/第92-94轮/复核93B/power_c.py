"""Independent direct-side HiGHS model in a translated coordinate system.
This is the second completed power encoding if CP-SAT times out.
"""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import itertools,json,time,warnings
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
out=Path(__file__).resolve().parent
allresults=[]
for edge in [False,True]:
    options=[]
    supply=set(itertools.product(range(-6,6),repeat=2));pole=set(itertools.product((-1,0),repeat=2))
    for w,h in [(3,3),(5,5),(6,4),(4,6)]:
        for x,y in itertools.product(range(-6-w+1,6),range(-6-h+1,6)):
            body=set(itertools.product(range(x,x+w),range(y,y+h)))
            if not body&supply or body&pole or (edge and any(a>0 for a,b in body)):continue
            for axis in (['x','y'] if w==h else ['y'] if w>h else ['x']):
                if axis=='x':sides=[{(x-1,b) for b in range(y,y+h)},{(x+w,b) for b in range(y,y+h)}]
                else:sides=[{(a,y-1) for a in range(x,x+w)},{(a,y+h) for a in range(x,x+w)}]
                sides=[s-pole for s in sides]
                if edge:sides=[{p for p in s if p[0]<=0} for s in sides]
                if not all(sides):continue
                options.append((x,y,w,h,axis,2 if w==3 else 3,body,sides))
    N=len(options);cover={}
    for i,o in enumerate(options):
        for cell in o[6]:cover.setdefault(cell,[]).append(i)
    rows=[{i:1 for i in indices} for indices in cover.values()];bounds=[1]*len(rows)
    for i,o in enumerate(options):
        for side in o[7]:
            row={i:1}
            for cell in side:
                for j in cover.get(cell,[]):row[j]=row.get(j,0)+1
            rows.append(row);bounds.append(len(side))
    for kind,target in [('count',14 if edge else 24),('weight',30 if edge else 55)]:
        countmax=(14 if edge else 24) if kind=='count' else (13 if edge else 23)
        rr=rows+[{i:1 for i in range(N)},{i:-(1 if kind=='count' else o[5]) for i,o in enumerate(options)}]
        bb=bounds+[countmax,-target];matrix=lil_matrix((len(rr),N))
        for j,row in enumerate(rr):
            for i,v in row.items():matrix[j,i]=v
        start=time.monotonic()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            sol=milp(np.zeros(N),integrality=np.ones(N),bounds=Bounds(0,1),constraints=LinearConstraint(matrix.tocsr(),-np.inf,np.array(bb)),options={'threads':1,'time_limit':240,'mip_rel_gap':0})
        rec={'edge':edge,'kind':kind,'target':target,'options':N,'status':{0:'FEASIBLE',1:'LIMIT',2:'INFEASIBLE'}.get(sol.status,str(sol.status)),'seconds':time.monotonic()-start,'message':sol.message}
        allresults.append(rec);(out/'power_c.json').write_text(json.dumps(allresults,indent=2)+'\n');print(json.dumps(rec),flush=True)
        if kind=='count' and sol.status!=2:break
    normalized=sorted([[o[0]+6,o[1]+6,o[2],o[3],o[4],o[5]] for o in options])
    (out/f'power_c_domain_{edge}.json').write_text(json.dumps(normalized)+'\n')
    assert normalized==json.loads((out/f'power_b_domain_{edge}.json').read_text())
