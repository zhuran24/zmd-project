import json
from collections import defaultdict
exec(open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/通道计数.py').read().split("res['label_mismatch']")[0].split('print(')[0])
# 槽：运输单位(桥分轴) / 机器in / 机器out / 源端口
def slot(p):
  u,s,o=p
  if kind[u]=='bridge':return (u,s%2)
  if kind[u] in TR:return (u,)
  if u=='CORE' or kind[u]=='outlet':return p
  return (u,)
src={}
for o in L['warehouse_outlets']:src[(o['id'],o['Dout'],1)]=o['item']
for q in c['output_items']:src[('CORE',q['side'],q['offset'])]=q['item']
emit=defaultdict(set);arr=defaultdict(set)
for p,it in src.items():emit[p].add(it)
BYM=defaultdict(list)
for r,(i,o) in R_.items():BYM[r.split('-')[0]].append((i,o))
pre={'粉碎':'粉碎机','精炼':'精炼炉','研磨':'研磨机','塑形':'塑形机','配件':'配件机','种植':'种植机','采种':'采种机','封装':'封装机','灌装':'灌装机'}
mrec={m['id']:m for m in L['machines']}
ch2=[(a,b) for a,b in ch]
for _ in range(200):
  ch_=False
  for a,b in ch2:
    sa=a if (a[0]=='CORE' or kind[a[0]]=='outlet') else slot(a)
    sb=('in',b[0]) if kind[b[0]]=='machine' else slot(b) if kind[b[0]] in TR else ('sink',b[0])
    e=emit[sa] if sa in emit or True else set()
    if not e<=arr[sb]:arr[sb]|=e;ch_=True
    if kind[b[0]] in TR:
      if not arr[sb]<=emit[sb]:emit[sb]|=arr[sb];ch_=True
  for mid,m in mrec.items():
    got=arr[('in',mid)];out=set(R_[m['recipe_ids'][0]][1])
    for r,(i,o) in R_.items():
      if pre[r.split('-')[0]]==m['model'] and i<=got:out|=o
    if not out<=emit[(mid,)]:emit[(mid,)]|=out;ch_=True
  if not ch_:break
# 机器 out 端口的 slot 是 (mid,)
wrong=[];offd=[]
for mid,m in mrec.items():
  got=arr[('in',mid)]
  allin=set().union(*[i for r,(i,o) in R_.items() if pre[r.split('-')[0]]==m['model']])
  if got-allin:wrong.append((mid,sorted(got-allin)))
  if got-R_[m['recipe_ids'][0]][0]:offd.append((mid,sorted(got-R_[m['recipe_ids'][0]][0])))
print('wrong',wrong);print('offdesign',offd);print('core_arrive',arr[('sink','CORE')])
