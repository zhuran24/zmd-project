import s08_s09_probe as p,json
w,ms,rs=p.build((1,1,1,1),[(50,2),(50,50),(0,0),(0,0)],[[8],[8],[None],[None]],[8,8,None,None],'B',trace=True)
h=[]
for i in range(20):w.step();h.append(p.snapshot(w,ms,rs))
r={'history':h,'events':w.events,'phi_bound':min(h[0]['phi']-.5,178)}
print(json.dumps(r,ensure_ascii=False,indent=2))
