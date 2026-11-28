from fractions import Fraction as F
bat, cap = F(18,30), F(33,60)   # 0.6, 0.55 /tick
# 电池: 10 零件 + 15 致密源石; 胶囊: 10 瓶 + 10 细磨荞花
part=10*bat; dsrc=15*bat; bottle=10*cap; fine=10*cap
steel=part+2*bottle; dfe=steel; fepow=2*dfe; fe_block=fepow; fe_ore=fe_block
srcpow=2*dsrc; src_ore=srcpow; qpow=2*fine; qflower_crush=qpow/2
sand_pow=dfe+dsrc+fine; sand_crush=sand_pow/3
print("矿", fe_ore, src_ore, fe_ore+src_ore)
ports=2*(70//3)+6; print("出口上界", ports, "边格合计/3", (70+70-1)//3)
plant_q=2*qflower_crush; plant_s=2*sand_crush
for r in (0,1):
    print("r=",r,"粉碎",src_ore+fe_block+r+qflower_crush+sand_crush,"精炼",fe_ore+dfe+r,"配件",part/1,"种植",plant_q+plant_s)
# 准入口: 段号 b(s)=1+s//4，窗口=当前段及前 9 段
def run(k,s0,n=200,step=8):
    got=[]
    for i in range(n):
        s=s0+i*step; b=1+s//4
        cnt=sum(1 for t in got if b-(1+t//4)<=9)
        if cnt>=k: return i+1
        got.append(s)
    return None
for k in range(6):
    print("k=",k,"首拒第几件(8个步位):",[run(k,s0) for s0 in range(1,9)])
# 第 q 件与首件段号差
print([ (1+(1+8*(q-1))//4)-(1+1//4) for q in range(1,7)])
