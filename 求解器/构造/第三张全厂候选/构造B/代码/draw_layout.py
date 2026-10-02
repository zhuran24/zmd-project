#!/usr/bin/env python3
import json,sys,html
from pathlib import Path
from collections import Counter
from pack_factory import BASE,D
p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];r=d.get('empty_rectangle',d.get('reserved_rectangle'));out=Path(sys.argv[2]) if len(sys.argv)>2 else BASE/'布局图.svg'
S=17;ox=50;oy=70;W=70*S+310;H=70*S+115
colors={'粉碎机':'#d5b787','精炼炉':'#e4a497','配件机':'#b8bcd9','塑形机':'#dbb8d5','研磨机':'#9cbcd5','封装机':'#f2d57f','灌装机':'#c5a2cc','采种机':'#8fc69c','种植机':'#bddeb0'}
def pos(x,y):return ox+x*S,oy+(70-y)*S
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="#fafaf6"/>','<g font-family="Noto Sans CJK SC,Arial,sans-serif">']
count=len(d.get('design',{}).get('logical_feeds',[]))
svg.append(f'<text x="{ox}" y="30" font-size="22" font-weight="bold">构造 B：全厂静态候选（未通过）</text>')
svg.append(f'<text x="{ox}" y="53" font-size="14">{len(l["machines"])} 台制造单位；已落实 {count}/325 条进路。空白几何面积不代表全厂可达下界。</text>')
for x in range(71):
 xx,_=pos(x,0);svg.append(f'<path d="M{xx} {oy}v{70*S}" stroke="#ddd" stroke-width="{.8 if x%5==0 else .25}"/>')
for y in range(71):
 _,yy=pos(0,y);svg.append(f'<path d="M{ox} {yy}h{70*S}" stroke="#ddd" stroke-width="{.8 if y%5==0 else .25}"/>')
for group in ['machines','warehouse_outlets','core','power_poles']:
 for u in ([l[group]] if group=='core' else l[group]):
  x,y=pos(u['x0'],u['y1']+1);w=(u['x1']-u['x0']+1)*S;h=(u['y1']-u['y0']+1)*S
  fill=colors[u['model']] if group=='machines' else '#708394' if group=='core' else '#637781' if group=='warehouse_outlets' else '#f4ba44'
  svg.append(f'<rect x="{x+.6}" y="{y+.6}" width="{w-1.2}" height="{h-1.2}" rx="1.5" stroke="#44515a" stroke-width=".65" fill="{fill}"/>')
  if group!='warehouse_outlets':
   svg.append(f'<text x="{x+w/2}" y="{y+h/2+3}" text-anchor="middle" font-size="{11 if group=="machines" else 8 if group=="power_poles" else 10}" fill="#1d2f35">{html.escape(u["id"].replace("POWER","P") if group=="power_poles" else u["id"])}</text>')
  if group=='machines':
   di=(u['Din']+2)%4;xx=x+w/2+(.38*w*D[di][0]);yy=y+h/2-(.38*h*D[di][1]);arrow=['→','↑','←','↓'][di]
   svg.append(f'<text x="{xx}" y="{yy+4}" text-anchor="middle" font-size="11" fill="#365057">{arrow}</text>')
for u in l['transport']:
 x,y=pos(u['x']+.5,u['y']+.5)
 if u['type']=='belt':
  a,b=u['in_side'],u['out_side'];sx,sy=x+D[a][0]*S*.48,y-D[a][1]*S*.48;ex,ey=x+D[b][0]*S*.48,y-D[b][1]*S*.48
  svg.append(f'<path d="M{sx},{sy}L{x},{y}L{ex},{ey}" stroke="#344b63" stroke-width="2.3" fill="none"/>')
  xx,yy=x+D[b][0]*4,y-D[b][1]*4;px,py=-D[b][1],-D[b][0];svg.append(f'<path d="M{xx+px*2-D[b][0]*2},{yy+py*2+D[b][1]*2}L{xx},{yy}L{xx-px*2-D[b][0]*2},{yy-py*2+D[b][1]*2}" stroke="#344b63" fill="none"/>')
 else:
  svg.append(f'<rect x="{x-S*.4}" y="{y-S*.4}" width="{S*.8}" height="{S*.8}" fill="#fff" stroke="#d77325" stroke-width="1.3"/><path d="M{x-S/2},{y}h{S} M{x},{y-S/2}v{S}" stroke="#d77325" stroke-width="2"/>')
if r:
 x,y=pos(r['x0'],r['y1']+1);ww=(r['x1']-r['x0']+1);hh=r['y1']-r['y0']+1
 svg.append(f'<rect x="{x}" y="{y}" width="{ww*S}" height="{hh*S}" fill="#31bd8733" stroke="#148558" stroke-width="2" stroke-dasharray="5 3"/><text x="{x+ww*S/2}" y="{y+hh*S/2}" text-anchor="middle" font-size="12">{ww}×{hh}={ww*hh}</text>')
for n in range(0,70,5):
 x,y=pos(n+.5,0);svg.append(f'<text x="{x}" y="{oy+70*S+19}" text-anchor="middle" font-size="11">{n}</text>')
 x,y=pos(0,n+.5);svg.append(f'<text x="{ox-9}" y="{y+4}" text-anchor="end" font-size="11">{n}</text>')
lx=ox+70*S+23;ly=oy+10;cnt=Counter(u['model'] for u in l['machines'])
for i,(name,color) in enumerate(colors.items()):
 yy=ly+i*32;svg.append(f'<rect x="{lx}" y="{yy}" width="17" height="17" fill="{color}" stroke="#44515a"/><text x="{lx+25}" y="{yy+14}" font-size="14">{name} × {cnt[name]}</text>')
for i,txt in enumerate(['深蓝细线：传送带','橙色十字：桥接器','黄色方块：供电桩 P 编号','深灰边带：仓库取货口','坐标原点在左下角','路径与桥轴明细见 JSON']):svg.append(f'<text x="{lx}" y="{ly+335+i*27}" font-size="13">{txt}</text>')
svg.append('</g></svg>');out.write_text('\n'.join(svg));print(out)
