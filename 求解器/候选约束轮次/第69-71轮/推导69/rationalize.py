#!/usr/bin/env python3
from pathlib import Path
from fractions import Fraction as F
import json,sys
OUT=Path(__file__).resolve().parent
name=sys.argv[1] if len(sys.argv)>1 else 'wall0'
a=json.loads((OUT/(name+'_model.json')).read_text()); b=json.loads((OUT/(name+'_lp.json')).read_text()); n=len(a['bodies'])
y=[max(F(0),F(v).limit_denominator(1000000)) for v in b['dual']]
z=[max(F(0),F(v).limit_denominator(1000000)) for v in b['upper_dual']]
co=z.copy()
for row,v in zip(a['rows'],y):
 for j,t in row:co[j]+=t*v
for j in range(n):
 if co[j]<1:z[j]+=1-co[j]
upper=sum(v*r for v,r in zip(y,a['rhs']))+sum(z)
def encode(a):return [[i,v.numerator,v.denominator] for i,v in enumerate(a) if v]
c=dict(name=name,rows=encode(y),bounds=encode(z),upper=[upper.numerator,upper.denominator],integer_upper=upper.numerator//upper.denominator)
(OUT/(name+'_certificate.json')).write_text(json.dumps(c,separators=(',',':')))
print(name,str(upper),c['integer_upper'],len(c['rows']),len(c['bounds']))
