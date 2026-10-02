#!/usr/bin/env python3
"""Publish a chosen attempt as an explicitly unpassed v1 candidate and check it."""
import json,argparse
from pathlib import Path
from export_candidate import make
from static_check import BASE,read,audit,digest
p=argparse.ArgumentParser();p.add_argument('--input',default=str(BASE/'实验/routing-sources-21.json'));a=p.parse_args();raw=read(a.input);c=read(BASE/'逻辑接法.json');d=make(raw,c,False)
definitions={
'N1':'多个取货通道的非运输单位不直连汇流器。','N2':'多个存货通道的单位不直接收分流器。','N3a':'正流物品准入口没有累计限额。','N3b':'准入口的拒料不形成唯一永久堵死出口。','N4a':'桥的使用轴两端各一存一取，未用轴无相向邻端口。','N4b':'桥接器不正交相邻。','N5a':'声明全部且仅有真实自动通道。','N5b':'全部结构通道均须有严格正的可实现平均流。',
'P1':'运输只用传送带和桥接器，不用协议储存箱。','P2':'每条端到端进路只运一种物品，沿程设计速率相同。','P3':'全部实体通道有正通过量。','P4':'使用桥轴两端都在用；未用轴无通道。','P5':'不使用相邻桥接器。','P6':'粉碎机和采种机各固定一种配方。',
'single-recipe':'所有制造单位在设计中各指定一个recipe_id；它不是游戏中的过滤设定。','fixed-layout':'静态检查固定本文件全部坐标、旋转、端口与设定。','fixed-logical-feeds':'静态检查固定已列进路的源、汇、物品和有理数设计速率；缺少的S2进路由专门检查器拒绝。'}
for uid,statement in definitions.items():d['design']['restrictions'].append(dict(id=uid,source=['shape','dynamic','numeric'],statement=statement,coverage_loss='只检查本文件列出的固定候选；不代表允许桥接器的全部布局。',release_obligations='更改坐标、通道或接法后重做相应几何、物料及运行证明。',failure_scope='只拒绝该候选及固定支持，不推广为S2全类无解。'))
out=BASE/'未通过候选.json';out.write_text(json.dumps(d,ensure_ascii=False,indent=1)+'\n');r=audit(d,c,True);r.update(candidate_sha256=digest(out),candidate_path=str(out),source_attempt=str(Path(a.input).resolve()));(BASE/'证据/静态检查结果.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'static_pass':r['static_pass'],'statistics':r['statistics'],'failures':[k for k,v in r['checks'].items() if v['status']!='PASS']},ensure_ascii=False))
