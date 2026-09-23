import os,sys,json
os.environ['OPENBLAS_NUM_THREADS']='1'
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'会议副本'))
import p2p
out=os.path.join(os.path.dirname(__file__),'../实验')
def plant(w,h):
 r=[]
 for name,kind,cnt,inp,outp,ic,oc in [('种植-砂叶','中',2,'砂叶种子','砂叶',1,1),('采种-砂叶','中',1,'砂叶','砂叶种子',1,2),('粉碎-砂叶','小',1,'砂叶','砂叶粉末',1,3)]:
  r.append(dict(name=name,kind=kind,count=cnt,**{'in':[inp]},out=[outp],in_count={inp:ic},n_out=oc))
 return dict(labels=['砂叶种子','砂叶','砂叶粉末'],roles=r,supply=[],demand=[('砂叶粉末',[0,1,2,3],3)])
for w,h in [(11,11),(10,11),(10,10)]:
 r=p2p.build(plant(w,h),w,h,threads=6,tlimit=55,minimize=False)
 json.dump(r,open(f'{out}/植物砖-{w}x{h}.json','w'),ensure_ascii=False,indent=2)
 print(w,h,r['status'],r['wall'],r.get('T'),flush=True)
 if 'layout' in r:print('\n'.join(r['grid']),flush=True)
