import importlib.util,sys
spec=importlib.util.spec_from_file_location('m','均分_步进模拟.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
k,p=2,1
for sd in range(2000):
    lg=m.run(k,120,sd,fixed_order=True)
    T=len(lg)
    for o in range(8):
        nk=(T-o-9)//8
        rows=[]
        for j in range(nk):
            b0=o+8*j; tk=[0]*k; rd=[False]*k
            for s in range(b0,b0+9):
                Sb,emp,took,order,Saf=lg[s]
                idxs=range(p,k) if s==b0 else (range(0,k) if s<b0+8 else range(0,p))
                for i in idxs:
                    c=order[i]
                    if emp[c]: rd[c]=True
                    if took[c]: tk[c]+=1
                if s==b0+8:
                    for i in range(p,k):
                        if emp[order[i]]: rd[order[i]]=True
                if s==b0:
                    for i in range(0,p):
                        c=order[i]
                        if emp[c] and not took[c]: rd[c]=True
            rows.append((all(rd),tk,b0))
        for a in range(nk):
            cum=[0]*k
            for b in range(a,nk):
                if not rows[b][0]: break
                cum=[cum[c]+rows[b][1][c] for c in range(k)]
                if max(cum)-min(cum)>1:
                    s0=rows[a][2]; s1=rows[b][2]+9
                    print('seed',sd,'offset',o,'刻',a,'..',b,'cum',cum,'order',lg[0][3])
                    for s in range(max(0,s0-8),s1):
                        Sb,emp,took,order,Saf=lg[s]
                        print(s,'S前',Sb,'首格空',emp,'取',took)
                    sys.exit()
