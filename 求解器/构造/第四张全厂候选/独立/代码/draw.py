#!/usr/bin/env python3
import json,sys,html
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];scale=18;margin=38;W=70*scale+2*margin;H=W+190
im=Image.new('RGB',(W,H),'white');dr=ImageDraw.Draw(im)
fontpath='/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc'
if not Path(fontpath).exists():fontpath='/usr/share/fonts/TTF/DejaVuSans.ttf'
font=ImageFont.truetype(fontpath,13);small=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf',10)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="white"/>']
colors={'粉碎机':'#f0d399','精炼炉':'#eaa9a1','研磨机':'#a9bfdc','种植机':'#bfddb0','采种机':'#92cbbc','塑形机':'#ceb8dc','配件机':'#e1bbbf','封装机':'#c8d7e9','灌装机':'#c3d2fa'}
def box(u,color,label=''):
 x0=u.get('x0',u.get('x'));x1=u.get('x1',u.get('x'));y0=u.get('y0',u.get('y'));y1=u.get('y1',u.get('y'))
 x=margin+x0*scale;y=margin+(69-y1)*scale;w=(x1-x0+1)*scale;h=(y1-y0+1)*scale
 dr.rectangle((x,y,x+w-1,y+h-1),fill=color,outline='#444444');svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" stroke="#444" stroke-width=".7"/>')
 if label:
  dr.text((x+w/2,y+h/2),label,fill='#17232f',font=small,anchor='mm');svg.append(f'<text x="{x+w/2}" y="{y+h/2+3}" font-family="sans-serif" text-anchor="middle" font-size="10">{html.escape(label)}</text>')
 return x,y,w,h
r=d.get('empty_rectangle')
if r:box(r,'#e8f4ff')
for u in l['machines']:box(u,colors[u['model']],u['id'])
for u in l['warehouse_outlets']:box(u,'#bfdbfe' if u['item']=='蓝铁矿' else '#c4b5fd',u['id'][2:])
box(l['core'],'#f9e08b','CORE')
for u in l['power_poles']:box(u,'#ffd944',u['id'].replace('POWER',''))
for u in l['transport']:
 x,y,w,h=box(u,'#6d9da2' if u['type']=='bridge' else '#dadde2');cx=x+w/2;cy=y+h/2
 sides=range(4) if u['type']=='bridge' else [u['in_side'],u['out_side']]
 for s in sides:
  dx,dy=[(1,0),(0,-1),(-1,0),(0,1)][s];xx=cx+dx*w/2;yy=cy+dy*h/2
  dr.line((cx,cy,xx,yy),fill='#1d455c',width=2);svg.append(f'<path d="M {cx} {cy} L {xx} {yy}" stroke="#1d455c" stroke-width="2"/>')
 for s in ([u['out_side']] if u['type']=='belt' else []):
  dx,dy=[(1,0),(0,-1),(-1,0),(0,1)][s];x1=cx+dx*5;y1=cy+dy*5;points=[(x1,y1),(x1-dx*4+dy*3,y1-dy*4-dx*3),(x1-dx*4-dy*3,y1-dy*4+dx*3)];dr.polygon(points,fill='#1d455c')
for g in ['machines','core','warehouse_outlets']:
 for u in ([l['core']] if g=='core' else l[g]):
  if g=='machines':spec=[(u['Din'],'#cc2633',None),((u['Din']+2)%4,'#166534',None)]
  elif g=='core':spec=[(side,'#cc2633' if side%2==u['Din']%2 else '#166534',range(1,8) if side%2==u['Din']%2 else [1,4,7]) for side in range(4)]
  else:spec=[(u['Dout'],'#166534',[1])]
  for side,color,offs in spec:
   n=u['x1']-u['x0']+1 if side%2 else u['y1']-u['y0']+1
   for off in (range(n) if offs is None else offs):
    gx=u['x1'] if side==0 else u['x0'] if side==2 else u['x0']+off;gy=u['y1'] if side==1 else u['y0'] if side==3 else u['y0']+off
    x=margin+gx*scale;y=margin+(69-gy)*scale
    xy=[(x+scale-1,y,x+scale-1,y+scale),(x,y,x+scale,y),(x,y,x,y+scale),(x,y+scale-1,x+scale,y+scale-1)][side]
    dr.line(xy,fill=color,width=3);svg.append(f'<line x1="{xy[0]}" y1="{xy[1]}" x2="{xy[2]}" y2="{xy[3]}" stroke="{color}" stroke-width="3"/>')
for z in range(0,70,5):
 dr.text((margin+(z+.5)*scale,margin-17),str(z),fill='#444',font=small,anchor='mm');dr.text((margin-18,margin+(69-z+.5)*scale),str(z),fill='#444',font=small,anchor='mm')
title=f'未达标候选 · 第四张全厂候选独立构造 · 已列进路 {len(d["design"]["logical_feeds"])}/325 · 不能计为达标下界'
notes=[title,'坐标左下角为 (0,0)。红边为存货边，绿边为取货边；青色为桥接器；黄色小方块为供电桩。','箭头表示进路前向；相邻桥的自动逆向通道见布局JSON。字母为机器编号。']
for j,txt in enumerate(notes):
 yy=W+10+j*25;dr.text((margin,yy),txt,fill='#222',font=font);svg.append(f'<text x="{margin}" y="{yy+16}" font-family="sans-serif" font-size="14">{html.escape(txt)}</text>')
legend=list(colors.items())+[('协议核心','#f9e08b'),('供电桩','#ffd944'),('取货口：蓝铁矿','#bfdbfe'),('取货口：源矿','#c4b5fd'),('传送带','#dadde2'),('桥接器','#6d9da2')]
for k,(name,color) in enumerate(legend):
 xx=margin+(k%5)*248;yy=W+90+(k//5)*26;dr.rectangle((xx,yy,xx+15,yy+15),fill=color,outline='#444');dr.text((xx+22,yy-2),name,font=font,fill='#222');svg.append(f'<rect x="{xx}" y="{yy}" width="15" height="15" fill="{color}" stroke="#444"/><text x="{xx+22}" y="{yy+13}" font-family="sans-serif" font-size="13">{name}</text>')
svg.append('</svg>');out=Path(sys.argv[2]);im.save(out.with_suffix('.png'));out.with_suffix('.svg').write_text('\n'.join(svg));print(str(out.with_suffix('.png')))
