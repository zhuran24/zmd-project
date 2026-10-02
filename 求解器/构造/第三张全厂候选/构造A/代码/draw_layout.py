#!/usr/bin/env python3
"""Readable SVG/PNG; diagnostics are labelled explicitly in the image."""
import os,argparse,json,html
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
os.environ['XDG_CACHE_HOME']=str(BASE/'实验/render-cache')
a=argparse.ArgumentParser();a.add_argument('input');a.add_argument('--out',required=True);a.add_argument('--title',default='部分布线，非可行全厂');p=a.parse_args();d=json.loads(Path(p.input).read_text());l=d['layout'];W,H=l['W'],l['H'];s=12 if W==70 else 30;ox=38;oy=84;wid=max(660,ox+W*s+26);hei=oy+H*s+105
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{wid}" height="{hei}" viewBox="0 0 {wid} {hei}"><rect width="100%" height="100%" fill="#fafbfc"/><style>text{{font-family:"Noto Sans CJK SC",sans-serif}}.id{{font-family:monospace;font-weight:bold}}</style>',f'<text x="{ox}" y="30" font-size="21" font-weight="bold" fill="#a21a27">{html.escape(p.title)}</text>',f'<text x="{ox}" y="56" font-size="13">{W}×{H} 格；制造单位 {len(l["machines"])} 台；已列进路 {len(d["design"]["logical_feeds"])} 条；紫色格为桥接器</text>']
def xy(x,y):return ox+x*s,oy+(H-1-y)*s
for x in range(W+1):parts.append(f'<path d="M {ox+x*s},{oy} V {oy+H*s}" stroke="#dde2e7" stroke-width=".45"/>')
for y in range(H+1):parts.append(f'<path d="M {ox},{oy+y*s} H {ox+W*s}" stroke="#dde2e7" stroke-width=".45"/>')
colors={'粉碎机':'#a9d5ee','精炼炉':'#e5b895','研磨机':'#c0c2ea','塑形机':'#f1ce9e','配件机':'#efb4b4','种植机':'#aed8b0','采种机':'#d5e6a2','封装机':'#87c8c4','灌装机':'#e9abc9'}
for group in ['machines','warehouse_outlets','power_poles','core']:
    us=([l['core']] if l.get('core') else []) if group=='core' else l.get(group,[])
    for u in us:
        x,y=xy(u['x0'],u['y1']);w=(u['x1']-u['x0']+1)*s;h=(u['y1']-u['y0']+1)*s;color=colors.get(u.get('model'),'#edcb51' if group=='power_poles' else '#42697f' if group=='core' else '#84accc');parts.append(f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" fill="{color}" stroke="#425264" stroke-width=".8"/>')
        if group in ('machines','core'):
            fs=7.5 if W==70 else 13;fill='#fff' if group=='core' else '#253443';parts.append(f'<text class="id" x="{x+w/2}" y="{y+h/2+fs/3}" text-anchor="middle" font-size="{fs}" fill="{fill}">{u["id"]}</text>')
            di=u['Din'];seg=[(x+w,y,x+w,y+h),(x,y,x+w,y),(x,y,x,y+h),(x,y+h,x+w,y+h)][di];parts.append(f'<line x1="{seg[0]}" y1="{seg[1]}" x2="{seg[2]}" y2="{seg[3]}" stroke="#16723a" stroke-width="2"/>')
        elif group=='power_poles':parts.append(f'<text x="{x+w/2}" y="{y+h*.67}" text-anchor="middle" font-size="{s}">P</text>')
for t in l['transport']:
    x,y=xy(t['x'],t['y']);cx,cy=x+s/2,y+s/2
    if t['type']=='bridge':
        parts.append(f'<rect x="{x+1}" y="{y+1}" width="{s-2}" height="{s-2}" rx="2" fill="#9659c8"/><path d="M{x+2},{cy} H{x+s-2} M{cx},{y+2} V{y+s-2}" stroke="white" stroke-width="1.4"/>')
    else:
        dd=[(1,0),(0,-1),(-1,0),(0,1)];a0=dd[t['in_side']];b0=dd[t['out_side']];parts.append(f'<path d="M{cx+a0[0]*s*.45},{cy+a0[1]*s*.45} L{cx},{cy} L{cx+b0[0]*s*.45},{cy+b0[1]*s*.45}" fill="none" stroke="#354d61" stroke-width="{max(1.2,s*.12)}"/>');ex,ey=cx+b0[0]*s*.3,cy+b0[1]*s*.3;parts.append(f'<circle cx="{ex}" cy="{ey}" r="{s*.105}" fill="#ed8b21"/>')
r=d.get('empty_rectangle')
if r:
    x,y=xy(r['x0'],r['y1']);w=(r['x1']-r['x0']+1)*s;h=(r['y1']-r['y0']+1)*s;parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#b3e7c0" fill-opacity=".4" stroke="#087b43" stroke-width="2" stroke-dasharray="5 3"/><text x="{x+w/2}" y="{y+h/2}" text-anchor="middle" font-size="10">{r["x1"]-r["x0"]+1}×{r["y1"]-r["y0"]+1}</text>')
for z in range(0,W,5):x,y=xy(z,0);parts.append(f'<text x="{x+s/2}" y="{oy+H*s+16}" font-size="9" text-anchor="middle">{z}</text>')
for z in range(0,H,5):x,y=xy(0,z);parts.append(f'<text x="{ox-8}" y="{y+s*.7}" font-size="9" text-anchor="end">{z}</text>')
parts.append(f'<text x="{ox}" y="{oy+H*s+43}" font-size="12">绿色边为机器存货边，棕色小点表示带的出货方向。坐标原点在左下角。</text><text x="{ox}" y="{oy+H*s+65}" font-size="12">黄色 P 为供电桩，深蓝色为协议核心，浅蓝色边界格为仓库取货口。</text><text x="{ox}" y="{oy+H*s+88}" font-size="12" fill="#a21a27">部分布线与局部构型均不构成达标全厂或已认证空矩形。</text></svg>')
out=Path(p.out).resolve()
if not out.is_relative_to(BASE):raise ValueError('输出越界')
out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(parts))
try:
 import cairosvg
 cairosvg.svg2png(url=str(out),write_to=str(out.with_suffix('.png')))
except ImportError:pass
print(out)
