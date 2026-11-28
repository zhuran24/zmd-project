from itertools import combinations, product
R={'粉碎机':[{'源矿':1},{'蓝铁块':1},{'荞花':1},{'砂叶':1}],'精炼炉':[{'蓝铁矿':1},{'致密蓝铁粉末':1},{'蓝铁粉末':1}],
'研磨机':[{'蓝铁粉末':2,'砂叶粉末':1},{'源石粉末':2,'砂叶粉末':1},{'荞花粉末':2,'砂叶粉末':1}],'塑形机':[{'钢块':2}],'配件机':[{'钢块':1}],
'种植机':[{'荞花种子':1},{'砂叶种子':1}],'采种机':[{'荞花':1},{'砂叶':1}],'封装机':[{'钢制零件':10,'致密源石粉末':15}],'灌装机':[{'钢质瓶':10,'细磨荞花粉末':10}]}
N={k:(2 if k in('研磨机','封装机','灌装机') else 1) for k in R}
MAIN={'蓝铁粉末','源石粉末','荞花粉末'}
for m,rs in R.items():
  legal=sorted({i for r in rs for i in r}); W='W'
  states=[{}]
  for k in (1,2)[:N[m]]:
    for items in combinations(legal,k):
      for cs in product(range(1,51),repeat=k): states.append(dict(zip(items,cs)))
  cnt=[0,0]; bad=[]
  for s in states:
    if m=='研磨机' and len(MAIN&set(s))==2: continue
    if any(all(s.get(i,0)>=n for i,n in r.items()) for r in rs): continue
    unr=[x for x in legal+[W] if (x in s and s[x]==50) or (x not in s and len(s)==N[m])]
    for withW in (0,1):
      pool=[x for x in unr if withW or x!=W]
      # count nonempty subsets; for withW count all (incl. legal-only)
      n=2**len(pool)-1; cnt[withW]+=n
      if n and withW==0 or (withW and W in pool):
        # classify against text
        full=[x for x in s if s[x]==50]
        if N[m]==1:
          ok = (m=='塑形机' and s=={'钢块':1} and pool==[W]) if withW else False
        elif len(s)==1: ok = full==list(s) and set(pool)-{W}==set(full)
        else:
          t=set(full)|({x for x in MAIN if x not in s} if m=='研磨机' else set())
          short = (m=='研磨机' and any(s[x]==1 for x in MAIN&set(s))) or (m=='封装机' and (s['钢制零件']<10 or s['致密源石粉末']<15)) or (m=='灌装机' and (s['钢质瓶']<10 or s['细磨荞花粉末']<10))
          ok = short and set(pool)-{W}==t
        if not ok: bad.append((s,pool))
  print(m,'仅合法首件',cnt[0],'含误料',cnt[1],'不符',len(bad))
