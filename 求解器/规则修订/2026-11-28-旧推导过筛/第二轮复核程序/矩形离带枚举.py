# 左带 23 个取货口、1 个空格(行 3k, k=0..23)；端口行 = 各取货口中格
def ports(k):
    free=[i for i in range(70) if i!=3*k]
    return [free[j+1] for j in range(0,69,3)]
res={}
for a in (2,3):
  for top in (False,True):
    best=0;arg=None
    for k in range(24):
      P=ports(k)
      for b in range(2,70):
        for H in range(6,71-b):
          if (b+H==70)!=top: continue
          m=sum(b<=p<=b+H-1 for p in P)
          e=1 if b+H==70 else 2
          if m<=e*(a-1) and H>best: best=H;arg=(k,b,H,m)
    res[(a,top)]=(best,arg)
print(res)
# 核对端口公式 3i+1+[i>=k]
assert all(ports(k)==[3*i+1+(i>=k) for i in range(23)] for k in range(24))
print('a=2 面积<=',68*res[(2,False)][0],' a=3 面积<=',67*res[(3,False)][0])
