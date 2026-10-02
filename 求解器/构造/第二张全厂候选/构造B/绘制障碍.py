#!/usr/bin/env python3
"""输出接法障碍示意图；图上的交叉不是游戏中允许的运输交叉。"""
from html import escape
from pathlib import Path

BASE = Path(__file__).resolve().parent
out = []
out.append('''<svg xmlns="http://www.w3.org/2000/svg" width="1420" height="1010" viewBox="0 0 1420 1010">
<style>text {font-family:"Noto Sans CJK SC","Source Han Sans CN","Microsoft YaHei",sans-serif;fill:#17212e} .title{font-size:28px;font-weight:700}.subtitle{font-size:17px;fill:#46566a}.body{font-size:18px}.small{font-size:16px}.node{stroke:#334e68;stroke-width:2;fill:#fff}.line{fill:none;stroke-width:3}.panel{fill:#fff;stroke:#cbd5e1;stroke-width:1.4}</style>
<rect width="1420" height="1010" fill="#f0f4f8"/>
<text x="45" y="50" class="title">S2 接法的边界布线障碍</text>
<text x="45" y="80" class="subtitle">第一台灌装机组 · 拓扑示意，非 70×70 布局；线条相交处表示纯传送带无法实现的交叉</text>
<rect x="30" y="108" width="1360" height="555" rx="12" class="panel"/>
''')
left_y = [195,365,535]
right_y = [195,365,535]
colors = ['#2563eb','#c2410c','#6d28d9']
for i,y1 in enumerate(left_y):
    for j,y2 in enumerate(right_y):
        # A common horizontal span emphasizes all nine required endpoint pairs.
        out.append(f'<path d="M 425 {y1} L 1090 {y2}" class="line" stroke="{colors[i]}" opacity=".67"/>')
for i,(label,detail) in enumerate([
    ('EXT：基地外侧辅助点','只在证明中连接贴边取货口'),
    ('S7：砂叶粉碎机','同一台机器的三条取货进路'),
    ('H1：塑形机','经第一台灌装机连到 H2'),
]):
    y=left_y[i]
    out.append(f'<rect x="60" y="{y-38}" width="365" height="76" rx="10" class="node"/>')
    out.append(f'<text x="78" y="{y-5}" class="body">{escape(label)}</text>')
    out.append(f'<text x="78" y="{y+22}" class="small">{escape(detail)}</text>')
for i,b in enumerate([7,8,9]):
    y=right_y[i]
    out.append(f'<rect x="1090" y="{y-38}" width="270" height="76" rx="10" class="node"/>')
    out.append(f'<text x="1110" y="{y-5}" class="body">B{b}：研磨机</text>')
    out.append(f'<text x="1110" y="{y+22}" class="small">蓝铁粉末＋砂叶粉末</text>')
out.append('''<text x="470" y="617" class="body">九条线代表内部互不相交的九条路径；缩短路径后是 K₃,₃。</text>
<rect x="30" y="685" width="1360" height="295" rx="12" class="panel"/>
<text x="55" y="723" class="body">被缩短的路径（忽略方向，只检验能否不交叉地摆放）：</text>
<text x="55" y="762" class="small">EXT → 第13／15／17个蓝铁矿仓库取货口 → 对应精炼炉 → 蓝铁块粉碎机 → B7／B8／B9</text>
<text x="55" y="799" class="small">S7 → B7；S7 → B8；S7 → B9</text>
<text x="55" y="836" class="small">H1 — R7 — B7；H1 — R8 — B8；H1 — F1 — H2 — R9 — B9</text>
<text x="55" y="885" class="body">平面简单二部图：m ≤ 2n − 4。这里 n = 6、m = 9，而 2n − 4 = 8，矛盾。</text>
<text x="55" y="930" class="subtitle">同类证书另见 S3／E2、S5／E3、S9／H3。任何机器朝向、带长和供电桩摆放都不能消除这个必要条件。</text>
</svg>''')
(BASE/'布线障碍.svg').write_text('\n'.join(out)+'\n',encoding='utf-8')
print(BASE/'布线障碍.svg')
