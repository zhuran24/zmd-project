import json, check_full as C
# 1) 精炼(蓝铁矿) 取货边朝东，两条取货通道：一条进汇流器、一条进传送带 => N1；汇流器另接分流器 => N2 密集结点
lay = dict(W=12, H=8, machines=[
    dict(role="精炼-蓝铁矿", kind="小", Din=2, x0=1, y0=2, x1=3, y1=4),     # 存货边西 x=1，取货边东 x=3
    dict(role="粉碎-蓝铁块", kind="小", Din=2, x0=6, y0=2, x1=8, y1=4),
], transport=[
    dict(x=0, y=3, type="belt", in_side=2, out_side=0),                    # 西来蓝铁矿 -> 精炼
    dict(x=4, y=3, type="merger", out_side=0),                             # 精炼(3,3)取货口 -> 汇流器
    dict(x=5, y=3, type="belt", in_side=2, out_side=0),                    # -> 粉碎 (6,3)
    dict(x=4, y=2, type="belt", in_side=2, out_side=0),                    # 精炼(3,2) -> (5,2) -> 粉碎(6,2)
    dict(x=5, y=2, type="belt", in_side=2, out_side=0),
    dict(x=4, y=4, type="splitter", in_side=1),                            # 分流器，取货口朝南直对汇流器 => 密集结点
], vin=[dict(x=0, y=3, side=2, label="蓝铁矿"), dict(x=4, y=4, side=1, label="蓝铁块")], vout=[])
print(json.dumps(C.check(lay), ensure_ascii=False, indent=1))
# 2) 桥两端同为取货口 => N4；限种准入口在传送带后 => N3；断头 => N5；错料
lay2 = dict(W=10, H=6, machines=[
    dict(role="精炼-蓝铁矿", kind="小", Din=0, x0=0, y0=0, x1=2, y1=2),   # 取货边西? Din=0 东为存货，西 x=0 为取货
    dict(role="粉碎-蓝铁块", kind="小", Din=2, x0=4, y0=0, x1=6, y1=2),   # 存货边西 x=4，取货边东 x=6
], transport=[
    dict(x=3, y=1, type="bridge", H_in=None, V_in=None),                  # 西邻精炼存货口(in)、东邻粉碎存货口(in) => 同型
    dict(x=7, y=1, type="gate", in_side=2, filter="钢块"),                 # 粉碎产物蓝铁粉末 -> 限钢块准入口 => 永久堵
    dict(x=8, y=1, type="belt", in_side=2, out_side=0),                   # -> 出界方向无端口 => 断头
    dict(x=3, y=0, type="belt", in_side=1, out_side=0),                   # 没有来料的格 -> 粉碎存货口
    dict(x=7, y=0, type="belt", in_side=2, out_side=1),                   # 粉碎(6,0)取货 -> (7,0) 朝北进 gate? gate 存货边在西，不接
], vin=[], vout=[])
print(json.dumps(C.check(lay2), ensure_ascii=False, indent=1))
