from fractions import Fraction as Fr
import itertools, math
# 物料流量
flows=[34,18,34,34,18,Fr(63,2),21,21,11,11,11,17,17,9,Fr(11,2),6,Fr(11,2),Fr(3,5),Fr(11,20)]
S=sum(flows); print('物料合计',S,float(S),'ceil',math.ceil(S))
# 机型下限: 批率 / 每台批率
rates={'粉碎':68,'精炼':51,'研磨':Fr(63,2),'塑形':Fr(11,2),'配件':6,'种植':32,'采种':16,'封装':Fr(3,5)*5,'灌装':Fr(11,20)*5}
lb={k:math.ceil(v) for k,v in rates.items()}; print(lb, sum(lb.values()))
size={'粉碎':9,'精炼':9,'塑形':9,'配件':9,'种植':25,'采种':25,'研磨':24,'封装':24,'灌装':24}
M=sum(lb[k]*size[k] for k in lb); print('机器占地',M)
base=M+81+46*3; print('机器+核心+取货口',base,'余',4900-base)
print('3758=',base+40+208,' 3856=',base+40+306)
print('A+4P<=',4900-base-208,'; 4A+14P<=',4*(4900-base)-921)
# 方向预算 Omega
def f研(n):return Fr(379-8*n,2) if n<=47 else Fr(0)
def f塑(n):return Fr(max(0,22-2*n))
def f封(n):return Fr({3:24,4:18,5:10,6:6,7:2}.get(n,0))
def f灌(n):return Fr({3:14,4:6,5:2}.get(n,0))
Om0=f研(32)+f塑(6)+f封(3)+f灌(3); print('Omega0',Om0)
# 4E+Omega 相对基准的最小增量，枚举各类加台数 0..20 及其余机型/箱
best=None
for a,b,c,d in itertools.product(range(0,21),repeat=4):
  for o_small in range(0,3):
    for o_mid in range(0,2):
      for box in range(0,3):
        k=a+b+c+d+o_small+o_mid+box
        if k==0: continue
        E=24*a+9*b+24*c+24*d+9*o_small+25*o_mid+9*box
        val=4*E+f研(32+a)+f塑(6+b)+f封(3+c)+f灌(3+d)-Om0
        r=val/k
        if best is None or r<best[0]: best=(r,(a,b,c,d,o_small,o_mid,box),val)
print('每台最小平均增量',best)
for n,fn,s in [(32,f研,24),(6,f塑,9),(3,f封,24),(3,f灌,24)]:
  print([float(4*s*(i)+fn(n+i)-fn(n)) for i in range(1,8)])
# 占地下界有增配支: 4(T+E) >= 717+Omega+4E >= 717+Om0+34
print('有增配 T+E >=',math.ceil(Fr(717)+Om0+34)/4, math.ceil((Fr(717)+Om0+34)/4))
# 增机面积界
M2=M+9+25; T_F=lambda A,P: 4900-M2-81-138-A-4*P
print('增机 机器占地',M2,'余',4900-M2-81-138)
for P in (10,11):
  Amax=Fr(4*(4900-M2-219)-921-14*P+0,4)  # 4(1356-A-4P)+2P>=921
  Amax=Fr(4*1356-921-14*P,4); print('P',P,'A<=',Amax,float(Amax))
def sizes(A,lim=66):
  return [(w,A//w) for w in range(6,int(A**0.5)+1) if A%w==0 and A//w<=lim]
for A in range(1085,1116): print(A,sizes(A),sizes(A,68))
for A in (1036,1040,1044,1035): print(A,sizes(A),sizes(A,68))
# 无桥: T>=306 / 314
print('无桥 A<=',4900-base-40-306,'; T>=314:',4900-base-40-314,'; 有箱 T>=306+9:',4900-base-40-306-9)
# 面积预算 A=1110 推论
print('A=1110 方向式余量',4751-4*1110,' 921式余量',4639-4*1110)
for P in range(10,16):
  Jmax=min(P,(54*P-520)//25) if 54*P>=520 else None
  if Jmax is None or Jmax<0: print(P,'供电不可行'); continue
  # 16P-2J+X+Y<=199, J<=Jmax
  feas=[J for J in range(0,Jmax+1) if 16*P-2*J<=199]
  print('P',P,'Jmax',Jmax,'可行J',feas,'X+Y上限',{J:199-16*P+2*J for J in feas})
