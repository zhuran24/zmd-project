"""规范数据；逐项抄核正式规则的单位、配方与现行任务。"""
from fractions import Fraction as F
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
FILES = {'rules':'《明日方舟：终末地》游戏规则.txt','task':'求解任务.txt','constraints':'求解约束.txt'}
HASHES = {'rules':'52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3','task':'1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac','constraints':'a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df'}
CONSTRAINT_PROFILES = {
 'cf44821f07779490b9b1d913bfb87d7757ae8abfe784c912bb7891868780f7f3':'constraint_catalog_71.json',
 'a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df':'constraint_catalog.json',
}
ITEMS = '源矿 蓝铁矿 蓝铁块 蓝铁粉末 源石粉末 荞花 砂叶 荞花种子 砂叶种子 荞花粉末 砂叶粉末 致密蓝铁粉末 致密源石粉末 细磨荞花粉末 钢块 钢制零件 钢质瓶 高容谷地电池 精选荞愈胶囊'.split()
TARGETS = {'高容谷地电池':'3/5','精选荞愈胶囊':'11/20'}
MODELS = dict(zip('粉碎机 精炼炉 研磨机 塑形机 配件机 种植机 采种机 封装机 灌装机'.split(), '小 小 大 小 小 中 中 大 大'.split()))
MINIMUM = dict(zip(MODELS,[68,51,32,6,6,32,16,3,3]))
IN_MIN = dict(zip(MODELS,[68,51,95,11,6,32,16,15,11]))
OUT_MIN = dict(zip(MODELS,[95,51,32,6,6,32,32,1,1]))
RECIPES = {}
def recipe(r,m,a,b,t=1): RECIPES[r]=(m,a,b,t)
recipe('粉碎-源矿','粉碎机',{'源矿':1},{'源石粉末':1})
recipe('粉碎-蓝铁块','粉碎机',{'蓝铁块':1},{'蓝铁粉末':1})
recipe('粉碎-荞花','粉碎机',{'荞花':1},{'荞花粉末':2})
recipe('粉碎-砂叶','粉碎机',{'砂叶':1},{'砂叶粉末':3})
recipe('精炼-蓝铁矿','精炼炉',{'蓝铁矿':1},{'蓝铁块':1})
recipe('精炼-致密蓝铁','精炼炉',{'致密蓝铁粉末':1},{'钢块':1})
recipe('精炼-蓝铁粉末','精炼炉',{'蓝铁粉末':1},{'蓝铁块':1})
recipe('研磨-致密蓝铁','研磨机',{'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1})
recipe('研磨-致密源石','研磨机',{'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1})
recipe('研磨-细磨荞花','研磨机',{'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1})
recipe('塑形-钢质瓶','塑形机',{'钢块':2},{'钢质瓶':1})
recipe('配件-钢制零件','配件机',{'钢块':1},{'钢制零件':1})
for p in ['荞花','砂叶']:
 recipe('种植-'+p,'种植机',{p+'种子':1},{p:1})
 recipe('采种-'+p,'采种机',{p:1},{p+'种子':2})
recipe('封装-电池','封装机',{'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1},5)
recipe('灌装-胶囊','灌装机',{'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1},5)
MATERIAL_MIN = dict(zip(ITEMS,map(F,['18','34','34','34','18','11','21','11','21','11','63/2','17','9','11/2','17','6','11/2','3/5','11/20'])))
N_IDS = ['N1','N2','N3a','N3b','N4a','N4b','N5a','N5b']
P_IDS = ['P1','P2','P3','P4','P5','P6']
DX = [(1,0),(0,1),(-1,0),(0,-1)]
def opp(d): return (d+2)%4
def nb(c,d): return c[0]+DX[d][0],c[1]+DX[d][1]
def ref(p): return (p['unit'],p['side'],p['offset'])
def unref(p): return dict(zip(['unit','side','offset'],p))
def cells(u):
 if 'x' in u: return [(u['x'],u['y'])]
 return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def edge(u,d):
 if d==0: return [(u['x1'],y) for y in range(u['y0'],u['y1']+1)]
 if d==2: return [(u['x0'],y) for y in range(u['y0'],u['y1']+1)]
 if d==1: return [(x,u['y1']) for x in range(u['x0'],u['x1']+1)]
 return [(x,u['y0']) for x in range(u['x0'],u['x1']+1)]
