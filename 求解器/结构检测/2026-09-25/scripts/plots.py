#!/usr/bin/env python3
"""Static inspection figures: variable counts, never physical layouts."""
import json,os
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(OUT/'cache/matplotlib')
os.environ['XDG_CACHE_HOME']=str(OUT/'cache')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
font=FontProperties(fname='/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family']=font.get_name()
plt.rcParams['axes.unicode_minus']=False
CASES=[('flow_all_window','metis_full_k4'),('flow_all_whole','metis_noglobal_k2'),('geometry_whole','metis_full_k4'),('residual75_whole','metis_full_k4')]
def family(v):return {'ore':'矿石层','all':'全体层','geometry':'几何'}[v['layer']]+'／'+v['family']
for dataset,run in CASES:
    path=OUT/'raw'/dataset;analysis=path/'analyses'/f'{run}.json'
    if not analysis.exists():continue
    d=json.loads(analysis.read_text());p=json.loads((path/'partitions'/f'{run}.json').read_text());z=np.load(path/'input.npz');vids=z['variable_ids'];variables=json.loads((OUT/'models'/d['model']/'variables.json').read_text());part=np.array(p['part']);S=set(d['separator_variable_ids']);k=d['k']
    fig=plt.figure(figsize=(15,11),layout='constrained');gs=fig.add_gridspec(2,k,height_ratios=[1,1.5]);axes=[fig.add_subplot(gs[0,i]) for i in range(k)]
    grids=[]
    for b in range(k):
        G=np.zeros((70,70))
        for local in np.flatnonzero(part==b):
            v=variables[vids[local]]
            if v['id'] in S or v['xy'] is None:continue
            x,y=np.floor(v['xy']).astype(int)
            if 0<=x<70 and 0<=y<70:G[x,y]+=1
        grids.append(G)
    vmax=max(float(g.max()) for g in grids) or 1
    for b,(ax,G) in enumerate(zip(axes,grids)):
        im=ax.imshow(G.T,origin='lower',extent=(0,70,0,70),cmap='Blues',vmin=0,vmax=vmax,interpolation='nearest')
        if d['scope']=='window':ax.set_xlim(16,30);ax.set_ylim(16,30)
        else:ax.add_patch(Rectangle((49,17),21,53,facecolor='none',edgecolor='#777777',hatch='///',alpha=.4,linewidth=.8))
        ax.set_title(f"剩余组 {b}：{d['remaining_block_sizes'][b]:,} 变量",fontproperties=font,fontsize=11)
        ax.set_xlabel('x');ax.set_ylabel('y')
    cb=fig.colorbar(im,ax=axes,label='同格代表点的变量数',shrink=.75);cb.locator=MaxNLocator(integer=True);cb.update_ticks()
    counts={}
    for local,vid in enumerate(vids):
        v=variables[vid];f=family(v)
        if f not in counts:counts[f]=np.zeros(k+1,dtype=int)
        counts[f][k if int(vid) in S else part[local]]+=1
    cats=sorted(counts,key=lambda f:-sum(counts[f]))[:18]
    M=np.array([counts[f] for f in cats]);percentage=M/M.sum(axis=1,keepdims=True)*100
    ax=fig.add_subplot(gs[1,:]);ax.imshow(percentage,cmap='YlGnBu',vmin=0,vmax=100,aspect='auto')
    ax.set_xticks(range(k+1),[f'剩余组 {i}' for i in range(k)]+['连接变量 S'],fontproperties=font)
    ax.set_yticks(range(len(cats)),cats,fontproperties=font,fontsize=9)
    for i in range(len(cats)):
        for j in range(k+1):
            ax.text(j,i,f'{percentage[i,j]:.0f}%\n({M[i,j]:,})',ha='center',va='center',fontsize=8,color='white' if percentage[i,j]>65 else '#222222')
    ax.set_title('变量类别去向（显示数量最多的 18 类；百分比按每行计算）',fontproperties=font,fontsize=11)
    caption='；斜线为空矩形，其中仍可有辅助量索引' if d['scope']=='whole' else ''
    fig.suptitle(f'{dataset} · {run}\n变量计数分布，非机器布局；未做取值传播'+caption,fontproperties=font,fontsize=13)
    filename=OUT/'figures'/f'{dataset}__{run}.png';fig.savefig(filename,dpi=140);plt.close(fig)
    print(filename)
