#!/usr/bin/env python3
"""输出拓扑障碍示意SVG；没有虚构机器坐标或布局。"""
from html import escape
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


def main():
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="1120" viewBox="0 0 1560 1120">',
           '<rect width="1560" height="1120" fill="#f5f7fb"/>',
           '<style>text{font-family:"Noto Sans CJK SC","Noto Sans CJK JP","WenQuanYi Micro Hei",sans-serif;fill:#172338}.small{font-size:18px}.body{font-size:22px}.heading{font-size:28px;font-weight:700}</style>']

    def text(x,y,s,size=22,fill=None,weight=None,anchor=None):
        attrs=''
        if fill:attrs+=f' style="fill:{fill}"'
        if weight:attrs+=f' font-weight="{weight}"'
        if anchor:attrs+=f' text-anchor="{anchor}"'
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}"{attrs}>{escape(s)}</text>')

    def box(x,y,w,h,color='#ffffff',stroke=None,r=14):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{color}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')

    text(44,62,'S2 固定接法的平面障碍',36,weight='700')
    text(44,103,'没有生成 70×70 合法布局。下图是不可布线证书，不是候选布局。',23,fill='#556174')
    box(32,136,700,632)
    box(754,136,774,632)
    text(58,181,'压缩中间机器与传送带后的六个分支点',24,weight='700')
    colors=['#d68014','#128575','#396cc6']
    ys=[290,467,644]
    for i,y in enumerate(ys):
        for v in ys:
            dash=' stroke-dasharray="10 7"' if i==0 else ''
            parts.append(f'<line x1="193" y1="{y}" x2="585" y2="{v}" stroke="{colors[i]}" stroke-width="3.4"{dash}/>')
    labels_left=[('X','基地外部辅助点'),('S3','砂叶粉碎机'),('E2','封装机')]
    labels_right=[('B3','蓝铁粉末研磨机'),('B4','蓝铁粉末研磨机'),('O4','源石粉末研磨机')]
    for i,(y,(code,label)) in enumerate(zip(ys,labels_left)):
        parts.append(f'<circle cx="193" cy="{y}" r="34" fill="{colors[i]}"/>')
        text(193,y+10,code,27,fill='#ffffff',weight='700',anchor='middle')
        text(193,y+67,label,20,anchor='middle')
    for y,(code,label) in zip(ys,labels_right):
        parts.append(f'<circle cx="585" cy="{y}" r="34" fill="#273c56"/>')
        text(585,y+10,code,27,fill='#ffffff',weight='700',anchor='middle')
        text(585,y+67,label,20,anchor='middle')
    text(58,748,'每个左侧点都连接三个右侧点：K₃,₃。',21,weight='700')
    text(780,181,'九条路径；内部机器和运输格不能共用',24,weight='700')
    rows=[
        ('X → B3','X — 仓库取货口5（蓝铁矿）— 精炼炉5 — 粉碎机5 — B3'),
        ('X → B4','X — 仓库取货口7（蓝铁矿）— 精炼炉7 — 粉碎机7 — B4'),
        ('X → O4','X — 仓库取货口7（源矿）— 源矿粉碎机7 — O4'),
        ('S3 → B3','S3 — B3'),('S3 → B4','S3 — B4'),('S3 → O4','S3 — O4'),
        ('E2 → B3','E2 — P3 配件机 — R3 精炼炉 — B3'),
        ('E2 → B4','E2 — P4 配件机 — R4 精炼炉 — B4'),
        ('E2 → O4','E2 — O4'),
    ]
    for i,(code,line) in enumerate(rows):
        y=222+i*57
        if i%2==0:box(772,y-25,736,54,'#f3f6fa',r=5)
        text(787,y,code,18,fill=colors[i//3],weight='700')
        text(787,y+24,line,17)
    text(780,753,'路径按无向邻接核验；成品支路可逆向列写。',17,fill='#556174')
    box(32,791,1496,164,'#e8eef6')
    text(56,831,'为什么纯带摆放必然矛盾',25,weight='700')
    text(56,869,'1. 仓库取货口都在基地外边界，可在基地外加入辅助点 X 与三条不相交的弧。',22)
    text(56,904,'2. 机器矩形互不重叠，纯带进路互不共格；压缩它们之后仍应是平面图。',22)
    text(56,939,'3. K₃,₃ 有 6 点、9 边；简单二分平面图必须 E ≤ 2V − 4，此处 9 > 8。',22)
    box(32,977,1496,110,'#fbe9e8')
    text(56,1017,'结论：不要求空矩形也摆不下这条固定接法。',27,fill='#9c252c',weight='700')
    text(56,1056,'证书只用 14 台机器、3 个边界取货口和 18 条真实进路；不涉及协议核心、供电或 737 格面积账。',21,fill='#6c3036')
    parts.append('</svg>')
    (BASE/'布线障碍.svg').write_text('\n'.join(parts)+'\n')


if __name__=='__main__':main()
