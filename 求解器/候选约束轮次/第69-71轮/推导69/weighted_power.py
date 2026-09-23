#!/usr/bin/env python3
from pathlib import Path
import json
import numpy as np
from scipy.optimize import linprog
from local_power import generate,matrix
OUT=Path(__file__).resolve().parent
b=generate((-20,32,-20,32)); rows,rhs,labels,A=matrix(b)
ans=[]
for t in (0,.1,.25,.5,1,2):
 c=np.array([1+t*(d['rect'][2]>3) for d in b])
 r=linprog(-c,A_ub=A,b_ub=rhs,bounds=(0,1),method='highs')
 row=dict(t=t,lp_upper=-r.fun,needed_for_10=(217+t*86)/10,gap=-r.fun-(217+t*86)/10)
 ans.append(row);print(row,flush=True)
(OUT/'weighted_power.json').write_text(json.dumps(ans,indent=2))
