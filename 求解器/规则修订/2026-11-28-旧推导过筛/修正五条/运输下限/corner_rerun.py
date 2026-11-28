import sys,importlib.util
import os; p=os.path.join(os.path.dirname(os.path.abspath(__file__)),'../../../../候选约束轮次/第78-80轮/推导78B/corner78.py')
spec=importlib.util.spec_from_file_location('c78',p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
mx={True:0,False:0}; over={True:[],False:[]}
for g,h in [(0,0)]+[(q,0) for q in range(3,70,3)]+[(0,q) for q in range(3,70,3)]:
    for t,w in [(False,False)]+([(True,False),(True,True)] if (g or h) and max(g,h)<69 else []):
        for ex in (True,False):
            r=m.solve(g,h,t,w,extra=ex)
            assert r['status']=='OPTIMAL',r['status']
            mx[ex]=max(mx[ex],r['bound'])
            if r['bound']>91: over[ex].append((g,h,t,w,r['bound']))
print('extra=True max',mx[True],over[True]); print('extra=False max',mx[False],over[False])
