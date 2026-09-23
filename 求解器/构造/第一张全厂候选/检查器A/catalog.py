"""正式规则配方及固定格式数据；不导入另一份检查器或运行内核。"""
from pathlib import Path
from fractions import Fraction as Q
from functools import lru_cache
ROOT = Path(__file__).resolve().parents[4]
FILES = {'rules':'《明日方舟：终末地》游戏规则.txt','task':'求解任务.txt','constraints':'求解约束.txt'}
HASHES = {'rules':'52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3','task':'1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac','constraints':'a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df'}
MODELS = {'粉碎机':'小','精炼炉':'小','配件机':'小','塑形机':'小','种植机':'中','采种机':'中','研磨机':'大','封装机':'大','灌装机':'大'}
RECIPES = {}
def add(model, rid, a, b, t=1): RECIPES[rid]=(model,a,b,t)
add('粉碎机','粉碎-源矿',{'源矿':1},{'源石粉末':1})
add('粉碎机','粉碎-蓝铁块',{'蓝铁块':1},{'蓝铁粉末':1})
add('粉碎机','粉碎-荞花',{'荞花':1},{'荞花粉末':2})
add('粉碎机','粉碎-砂叶',{'砂叶':1},{'砂叶粉末':3})
add('精炼炉','精炼-蓝铁矿',{'蓝铁矿':1},{'蓝铁块':1})
add('精炼炉','精炼-致密蓝铁',{'致密蓝铁粉末':1},{'钢块':1})
add('精炼炉','精炼-蓝铁粉末',{'蓝铁粉末':1},{'蓝铁块':1})
for n,a,b in [('致密蓝铁','蓝铁粉末','致密蓝铁粉末'),('致密源石','源石粉末','致密源石粉末'),('细磨荞花','荞花粉末','细磨荞花粉末')]:add('研磨机','研磨-'+n,{a:2,'砂叶粉末':1},{b:1})
add('塑形机','塑形-钢质瓶',{'钢块':2},{'钢质瓶':1})
add('配件机','配件-钢制零件',{'钢块':1},{'钢制零件':1})
for plant in ['荞花','砂叶']:
 add('种植机','种植-'+plant,{plant+'种子':1},{plant:1})
 add('采种机','采种-'+plant,{plant:1},{plant+'种子':2})
add('封装机','封装-电池',{'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1},5)
add('灌装机','灌装-胶囊',{'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1},5)
ITEMS=sorted(set().union(*(set(a)|set(b) for _,a,b,_ in RECIPES.values())))
TARGETS={'高容谷地电池':'3/5','精选荞愈胶囊':'11/20'}
MIN_COUNTS=dict(zip(['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机'],[68,51,32,6,6,32,16,3,3]))
MIN_IN=dict(zip(MIN_COUNTS,[68,51,95,11,6,32,16,15,11]))
MIN_OUT=dict(zip(MIN_COUNTS,[95,51,32,6,6,32,32,1,1]))
MATERIAL=dict(zip(['蓝铁矿','源矿','蓝铁块','蓝铁粉末','源石粉末','砂叶粉末','砂叶','砂叶种子','荞花','荞花种子','荞花粉末','致密蓝铁粉末','钢块','致密源石粉末','细磨荞花粉末','钢制零件','钢质瓶','高容谷地电池','精选荞愈胶囊'],map(Q,['34','18','34','34','18','63/2','21','21','11','11','11','17','17','9','11/2','6','11/2','3/5','11/20'])))
NIDS=['N1','N2','N3a','N3b','N4a','N4b','N5a','N5b']
PIDS=['P'+str(i) for i in range(1,7)]
DX=[(1,0),(0,1),(-1,0),(0,-1)]
def opp(d):return (d+2)%4
def nb(c,d):return (c[0]+DX[d][0],c[1]+DX[d][1])
@lru_cache(maxsize=1)
def constraints():
 lines=(ROOT/FILES['constraints']).read_text().splitlines();out=[]
 for i,line in enumerate(lines):
  if i+1<len(lines) and lines[i+1].lstrip().startswith('据：'):
   out.append({'number':len(out)+1,'line':i+1,'name':line.split('：')[0],'text':line,'basis':lines[i+1].strip()})
 return out
