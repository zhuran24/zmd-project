import sys
exec(open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/独立几何.py').read().split('# 核心/取货口附近')[0])
x0,x1,y0,y1=map(int,sys.argv[1:5])
A={0:'>',1:'^',2:'<',3:'v'}
tmap={t['id']:t for t in L['transport']}
for y in range(y1,y0-1,-1):
  row=f'{y:2d} '
  for x in range(x0,x1+1):
    u=occ.get((x,y))
    if u is None:row+='.'
    elif kind[u]=='belt':row+=A[tmap[u]['out_side']]
    elif kind[u]=='bridge':row+='#'
    elif kind[u]=='machine':row+='M'
    elif kind[u]=='core':row+='C'
    elif kind[u]=='outlet':row+='O'
    elif kind[u]=='pole':row+='P'
  print(row)
print('   '+''.join(str(x%10) for x in range(x0,x1+1)))
