"""编码乙：不用甲的图或配方，显式机群与三倍整数当量重算。"""
import json
from math import gcd, isqrt
from pathlib import Path

def frac(a,b=1):
    g=gcd(a,b);a//=g;b//=g
    return str(a) if b==1 else f'{a}/{b}'
counts={'粉碎机':34+18+13+6,'精炼炉':34+17,'研磨机':17+9+6,'塑形机':6,
        '配件机':6,'种植机':2*(13+6),'采种机':13+6,'封装机':3,'灌装机':4}
s=34+18+13+6+34+17+6+6;m=3*(13+6);l=17+9+6+3+4
area=9*s+25*m+24*l
routes=sum([34,34,18,17*3,9*3,5*3+2,17,6,5*2+1,19,38,19,3*5,4+4+2+2,7])
# 每一当量都放大三倍；按机群相加，不展开成逐台图。
cap=[13*1115+(17+9+6)*101+(17+6)*101+6*152+3*100+4*150,
     3*(6*380+6*76+4*50),
     3*(68*101+17*152+(17+6)*202+6*304+3*100+4*200),
     3*(18*101+9*152+3*100)]
maxunit=[3,3,12,6]
total=[cap[i]+4900*maxunit[i] for i in range(4)]
equiv={
 '砂叶':[3,0,0,0], '砂叶种子':[3,0,0,0], '荞花':[0,3,0,0], '荞花种子':[0,3,0,0],
 '蓝铁矿':[0,0,3,0], '源矿':[0,0,0,3], '蓝铁块':[0,0,3,0], '蓝铁粉末':[0,0,3,0],
 '源石粉末':[0,0,0,3], '砂叶粉末':[1,0,0,0], '荞花粉末':[0,3,0,0],
 '致密蓝铁粉末':[1,0,6,0], '致密源石粉末':[1,0,0,6], '细磨荞花粉末':[1,3,0,0],
 '钢块':[1,0,6,0], '钢制零件':[1,0,6,0], '钢质瓶':[2,0,12,0]}
# 荞花粉末是半株；对该条单独用两倍分子，避免浮点与分数模块。
stock={x:min(total[k]//v[k] for k in range(4) if v[k]) for x,v in equiv.items()}
stock['荞花粉末']=2*total[1]//3
steel=stock['钢块']+stock['钢制零件']+2*stock['钢质瓶']
dense_blue=stock['致密蓝铁粉末']+steel
dense_origin=stock['致密源石粉末']
fine_flower=stock['细磨荞花粉末']
sand_pow=stock['砂叶粉末']+dense_blue+dense_origin+fine_flower
flower_pow=stock['荞花粉末']+2*fine_flower
blue_pow=stock['蓝铁粉末']+2*dense_blue
blue_block=stock['蓝铁块']+blue_pow
origin_pow=stock['源石粉末']+2*dense_origin
raw={'砂叶':stock['砂叶']+(sand_pow+2)//3,'砂叶种子':stock['砂叶种子'],
     '荞花':stock['荞花']+(flower_pow+1)//2,'荞花种子':stock['荞花种子'],
     '蓝铁矿':stock['蓝铁矿']+blue_block,'源矿':stock['源矿']+origin_pow}
pj=[]
for p in range(1226):
    j=min(p,(23*p-s-m-l)//10,(54*p-2*s-3*m-3*l)//25)
    if j>=0:pj.append((16*p-2*j,p,j))
cost=min(x[0] for x in pj)
omega2=(379-8*32)+2*(22-2*6)+48+12
a8=2*(4751-cost-4*(area-3291))-omega2
b8=a8-2*(2*routes-619)
def max_dim(numerator):
    for a in range(numerator//8,35,-1):
        factors=[(x,a//x) for x in range(6,isqrt(a)+1) if a%x==0 and a//x<=68]
        if factors:return (a,factors)
res={
 'machines':counts,'machine_count':s+m+l,'classes':[s,m,l],'machine_area':area,
 'route_count':routes,'interfaces':routes*2,'shared_routes':6+(17+9+6-2)+5*2,
 'power_weight':2*s+3*m+3*l,'best_pj':[(p,j) for c,p,j in pj if c==cost],
 'power_cost':cost,'extra_area':area-3291,'omega':frac(omega2,2),
 'generic_A':frac(a8,8),'specific_A':frac(b8,8),
 'generic_integer_dimensions':max_dim(a8),'specific_integer_dimensions':max_dim(b8),
 'generic_T_min':(2*717+omega2+7)//8,'specific_T_min':(2*(routes*2+98)+omega2+7)//8,
 'generic_T_plus_F_min':(2*(809-2)+omega2+7)//8,
 'T_plus_F_min':(2*(routes*2+190-2)+omega2+7)//8,
 'transport_slots_upper':(70*70-area-9*9-46*3)*2,'route_slots_lower':routes+8,
 'no_double_bridge_A_plus_F':4900-area-81-46*3-11*4-routes-8,
 'machine_equivalent_capacity':[frac(v,3) for v in cap],
 'transport_equivalent_max':[frac(v,3) for v in maxunit],
 'equivalent_capacity':[frac(v,3) for v in total],'stock':stock,'raw_stock':raw,
 'cleanup_bound':sum([50]*52+[53]*18+[153]*9+[100]*3+[2]*4900),
 'recipe_rates':{'粉碎机':frac(2*(34+18)+21+11,2),'精炼炉':'51','研磨机':'63/2',
                 '塑形机':'11/2','配件机':'6','种植机':'32','采种机':'16','封装机':'3/5','灌装机':'11/20'},
 'mine_rates':{'蓝铁矿':frac(20*12+40*11,20),'源矿':frac(30*12,20)},
 'all_mine_routes_one':True,'all_routes_positive':True,
 'plant_loop_constant':str(3*50+25+2),
 'cycle_480_deliveries':[str(3*(60//5)),str(2*(60//5)+60//10+60//20)],
 'cycle_480_mine_per_route':str(60),
 'nonfinal_weight_increases':{'ore_blue':2-1,'blue_powder':3-2,'origin_powder':2-1,
       'B':11-(2*3+4),'O':9-(2*2+4),'Q':13-(2*4+4),'R':12-11,'P':13-12,'H':25-2*12,
       'SC':2*2-3,'SA':3-2,'SB':3-2,'SK':3*4-3,'JC':2*2-3,'JA':3-2,'JB':3-2,'JK':2*4-3},
 'plant_K_rates':{**{f'SK{i}':('2/3' if i in [2,4,6] else '1/3' if i==12 else '1/6' if i==13 else '1') for i in range(1,14)},
                 **{f'JK{i}':('1' if i<=5 else '1/2') for i in range(1,7)}}
}
Path(__file__).with_suffix('.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(res,ensure_ascii=False,indent=2))
