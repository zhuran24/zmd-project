"""编码甲：快照配方解析、逐物品守恒、Fraction 消元。单进程，只写同目录。"""
from pathlib import Path
from fractions import Fraction as F
import re, json, math

HERE = Path(__file__).resolve().parent
RULES = HERE.parent / '前提快照' / '《明日方舟：终末地》游戏规则.txt'
TYPES = ['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']

def parse():
    active = False
    records = []
    for line in RULES.read_text().splitlines():
        line = line.strip()
        if line == '配方':
            active = True
        elif active and line in TYPES:
            machine = line
        elif active and '→' in line:
            left, right, duration = re.fullmatch(r'(.*?)→(.*?)，(\d+) tick', line).groups()
            def side(s):
                return {name:int(q) for q,name in (re.fullmatch(r'\s*(\d+)\s+(\S+)\s*', p).groups() for p in s.split('＋'))}
            records.append((machine, side(left), side(right), int(duration)))
    return records

def solve(rows, n):
    rows = [[F(v) for v in row] for row in rows]
    pivots=[]
    for col in range(n):
        choice=next((j for j in range(len(pivots),len(rows)) if rows[j][col]),None)
        if choice is None: continue
        pos=len(pivots)
        rows[pos],rows[choice]=rows[choice],rows[pos]
        t=rows[pos][col]; rows[pos]=[x/t for x in rows[pos]]
        for j,row in enumerate(rows):
            if j!=pos and row[col]:
                t=row[col]; rows[j]=[x-t*y for x,y in zip(row,rows[pos])]
        pivots.append(col)
    assert all(any(row[:n]) or not row[-1] for row in rows)
    assert len(pivots)==n
    out=[F(0)]*n
    for row,p in zip(rows,pivots): out[p]=row[-1]
    return out

def run():
    rec=parse(); items=sorted({i for _,a,b,_ in rec for i in a.keys()|b.keys()})
    ext={'蓝铁矿':-34,'源矿':-18,'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20)}
    rows=[[b.get(i,0)-a.get(i,0) for _,a,b,_ in rec]+[ext.get(i,0)] for i in items]
    rindex=next(j for j,(m,a,b,d) in enumerate(rec) if m=='精炼炉' and '蓝铁粉末' in a)
    values=[]
    for rval in (0,1):
        values.append(solve(rows+[[int(j==rindex) for j in range(len(rec))]+[rval]],len(rec)))
    const=values[0]; coef=[b-a for a,b in zip(*values)]
    rate={m:[sum(x[j] for j,q in enumerate(rec) if q[0]==m) for x in (const,coef)] for m in TYPES}
    flow={i:[sum(x[j]*q[2].get(i,0) for j,q in enumerate(rec))+(max(-ext.get(i,0),0) if k==0 else 0) for k,x in enumerate((const,coef))] for i in items}
    lower={m:math.ceil(sum(const[j]*q[3] for j,q in enumerate(rec) if q[0]==m)) for m in TYPES}
    ins={m:math.ceil(sum(const[j]*sum(q[1].values()) for j,q in enumerate(rec) if q[0]==m)) for m in TYPES}
    outs={m:math.ceil(sum(const[j]*sum(q[2].values()) for j,q in enumerate(rec) if q[0]==m)) for m in TYPES}
    size={m:(25 if m in ('种植机','采种机') else 24 if m in ('研磨机','封装机','灌装机') else 9) for m in TYPES}
    # 逐个枚举多通道机器数，核而不是预先代入 ceil 公式。
    multi={}
    for m,total,lo,hi in [('研磨机',F(189,2),2,3),('塑形机',F(11),1,2),('采种机',F(32),1,2),('封装机',F(15),4,5),('灌装机',F(11),3,4)]:
        multi[m]={str(n):next(h for h in range(n+1) if h*hi+(n-h)*lo>=total) for n in range(lower[m],lower[m]+4)}
    result={'recipes':len(rec),'items':len(items),'batch_rates':rate,'flow':flow,'flow_total':[sum(x[k] for x in flow.values()) for k in (0,1)],'lower':lower,'machine_count':sum(lower.values()),'machine_area':sum(size[m]*lower[m] for m in TYPES),'input_channels':ins,'output_channels':outs,'input_total':sum(ins.values()),'output_total':sum(outs.values()),'multi':multi,'ore_blue':34,'ore_source':18,'source_ports':2*(70//3)+6,'period_steps':160}
    return json.loads(json.dumps(result,ensure_ascii=False,default=str))

if __name__=='__main__':
    result=run(); (HERE/'foundation_a.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False))
