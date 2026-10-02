# 推导席报告第 3.2、3.3、7 节几个数字的两套独立算法（分数精确）。
from fractions import Fraction as F
import json

# 甲：按配方逐级推流量（每 tick）
def chain(x, y):
    yuan_powder = x                     # 源矿→源石粉末 1:1
    dense_yuan = yuan_powder / 2        # 2 源石粉末(+1 砂叶粉末)→1 致密源石粉末
    iron_block = y                      # 蓝铁矿→蓝铁块
    iron_powder = iron_block            # 蓝铁块→蓝铁粉末
    dense_iron = iron_powder / 2        # 2 蓝铁粉末→1 致密蓝铁粉末
    steel = dense_iron                  # 致密蓝铁粉末→钢块
    battery = dense_yuan / 15           # 每电池 15 致密源石粉末、10 钢制零件
    parts_steel = 10 * battery
    bottle_steel = steel - parts_steel
    capsule = bottle_steel / 2 / 10     # 2 钢块→1 钢质瓶；每胶囊 10 瓶
    return battery, capsule

# 乙：闭式 b=x/30, c=y/40−x/60
def closed(x, y):
    return F(x) / 30, F(y) / 40 - F(x) / 60

res = {}
for name, x, y in (('全满', F(18), F(34)), ('一条源矿 8/9', F(17) + F(8, 9), F(34)), ('一条源矿停', F(17), F(34))):
    a = chain(x, y)
    b = closed(x, y)
    assert a == b, (a, b)
    res[name] = {'电池': str(a[0]), '胶囊': str(a[1]), '两法一致': a == b,
                 '电池≥3/5': a[0] >= F(3, 5), '胶囊≥11/20': a[1] >= F(11, 20)}
# 达标反推：b≥3/5 ⇒ x≥18；c≥11/20 且 x=18 ⇒ y≥34
res['反推'] = {'x下限': str(F(3, 5) * 30), 'y下限(x=18)': str((F(11, 20) + F(18, 60)) * 40)}
# 第三台灌装机：第 5、6 塑形机共 2/2+1/2 瓶/tick → 胶囊
res['第三台灌装机'] = {'瓶/tick': str(F(1) + F(1, 2)), '胶囊/tick': str((F(1) + F(1, 2)) / 10),
                    '三台合计': str(2 * F(2, 10) + (F(1) + F(1, 2)) / 10)}
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(__file__.rsplit('/', 1)[0] + '/arithmetic.json', 'w'), ensure_ascii=False, indent=1)
