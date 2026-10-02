"""编码乙：以 20 tick 的整数批数逆推，不导入编码甲，也不做消元。"""
from fractions import Fraction as F
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent

def ceiling(q): return -((-q.numerator)//q.denominator)

def run():
    battery,capsule=12,11
    part,dense_source,bottle,fine_flower=10*battery,15*battery,10*capsule,10*capsule
    steel=part+2*bottle
    dense_blue=steel
    blue_powder=2*dense_blue
    source_powder=2*dense_source
    flower_powder=2*fine_flower
    leaf_powder=dense_blue+dense_source+fine_flower
    flower_crush=flower_powder//2; leaf_crush=leaf_powder//3
    assert flower_crush*2==flower_powder and leaf_crush*3==leaf_powder
    flower_seed=2*flower_crush; leaf_seed=2*leaf_crush
    amounts={'蓝铁矿':blue_powder,'源矿':source_powder,'蓝铁块':blue_powder,'蓝铁粉末':blue_powder,'源石粉末':source_powder,'砂叶粉末':leaf_powder,'砂叶':2*leaf_crush,'砂叶种子':leaf_seed,'荞花':2*flower_crush,'荞花种子':flower_seed,'荞花粉末':flower_powder,'致密蓝铁粉末':dense_blue,'钢块':steel,'致密源石粉末':dense_source,'细磨荞花粉末':fine_flower,'钢制零件':part,'钢质瓶':bottle,'高容谷地电池':battery,'精选荞愈胶囊':capsule}
    flow={k:[F(v,20),int(k in ('蓝铁块','蓝铁粉末'))] for k,v in amounts.items()}
    batches={'粉碎机':source_powder+blue_powder+flower_crush+leaf_crush,'精炼炉':blue_powder+steel,'研磨机':dense_blue+dense_source+fine_flower,'塑形机':bottle,'配件机':part,'种植机':flower_seed+leaf_seed,'采种机':flower_crush+leaf_crush,'封装机':battery,'灌装机':capsule}
    rate={k:[F(v,20),int(k in ('粉碎机','精炼炉'))] for k,v in batches.items()}
    duration={k:5 if k in ('封装机','灌装机') else 1 for k in batches}
    lower={k:ceiling(F(v*duration[k],20)) for k,v in batches.items()}
    intake={'粉碎机':batches['粉碎机'],'精炼炉':batches['精炼炉'],'研磨机':3*batches['研磨机'],'塑形机':2*bottle,'配件机':part,'种植机':flower_seed+leaf_seed,'采种机':flower_crush+leaf_crush,'封装机':25*battery,'灌装机':20*capsule}
    output={'粉碎机':source_powder+blue_powder+flower_powder+leaf_powder,'精炼炉':batches['精炼炉'],'研磨机':batches['研磨机'],'塑形机':bottle,'配件机':part,'种植机':flower_seed+leaf_seed,'采种机':flower_seed+leaf_seed,'封装机':battery,'灌装机':capsule}
    ins={k:ceiling(F(v,20)) for k,v in intake.items()}; outs={k:ceiling(F(v,20)) for k,v in output.items()}
    multi={}
    for machine,total,base in [('研磨机',F(intake['研磨机'],20),2),('塑形机',F(intake['塑形机'],20),1),('采种机',F(output['采种机'],20),1),('封装机',F(intake['封装机'],20),4),('灌装机',F(intake['灌装机'],20),3)]:
        multi[machine]={str(n):max(0,ceiling(total-base*n)) for n in range(lower[machine],lower[machine]+4)}
    min_steps=next(t for t in range(1,1000) if (3*t)%40==0 and (11*t)%160==0)
    result={'recipes':18,'items':len(amounts),'batch_rates':rate,'flow':flow,'flow_total':[F(sum(amounts.values()),20),2],'lower':lower,'machine_count':sum(lower.values()),'machine_area':9*(lower['粉碎机']+lower['精炼炉']+lower['塑形机']+lower['配件机'])+25*(lower['种植机']+lower['采种机'])+24*(lower['研磨机']+lower['封装机']+lower['灌装机']),'input_channels':ins,'output_channels':outs,'input_total':sum(ins.values()),'output_total':sum(outs.values()),'multi':multi,'ore_blue':blue_powder//20,'ore_source':source_powder//20,'source_ports':len(range(0,68,3))*2+6,'period_steps':min_steps}
    return json.loads(json.dumps(result,ensure_ascii=False,default=str))

if __name__=='__main__':
    result=run(); (HERE/'foundation_b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False))
