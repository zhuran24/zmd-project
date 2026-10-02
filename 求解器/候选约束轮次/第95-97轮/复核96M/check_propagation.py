"""Two independent local-contract implementations for candidate 6.

Each Y is forced to satisfy the stipulated nonempty-cache source contract.
These are conditional local checks, not geometric or full-factory witnesses.
"""
from pathlib import Path
import json,random
OUT=Path(__file__).resolve().parent

def run_stamp(config):
    needs,d,lengths,kinds,batches,phases,initial,seed=config
    roads=[[None]*n for n in lengths];source_out=[0]*len(roads);source_cache=list(phases)
    stock=list(initial);out=0;cache=None;output_cell=None;states=[];events=[]
    for t in range(1800):
        for j,c in enumerate(source_cache):
            if c<=t and source_out[j]+batches[j]<=50:
                source_out[j]+=batches[j];source_cache[j]=None
        if cache is not None and cache<=t and out<50:out+=1;cache=None
        # Output transport then all input components, arbitrary receiver order.
        departed=False
        if output_cell is not None and t-output_cell>=8 and not (t%173<80):
            output_cell=None;departed=True
        order=list(range(len(roads)))
        if (t//101+seed)%2:order.reverse()
        for j in order:
            road=roads[j];kind=kinds[j]
            if road[-1] is not None and t-road[-1]>=8 and stock[kind]<50:
                road[-1]=None;stock[kind]+=1
            for p in range(len(road)-2,-1,-1):
                if road[p] is not None and t-road[p]>=8 and road[p+1] is None:
                    road[p+1]=t;road[p]=None
        for j,road in enumerate(roads):
            if road[0] is None and source_out[j]:road[0]=t;source_out[j]-=1
            if source_cache[j] is not None and source_cache[j]<=t and source_out[j]+batches[j]<=50:
                source_out[j]+=batches[j];source_cache[j]=None
        delivered=False
        if output_cell is None and out:output_cell=t;out-=1;delivered=True
        if cache is not None and cache<=t and out<50:out+=1;cache=None
        for j in range(len(roads)):
            if source_cache[j] is None:source_cache[j]=t+8
        if cache is None and all(x>=a for x,a in zip(stock,needs)):
            stock=[x-a for x,a in zip(stock,needs)];cache=t+8*d
        state=(tuple(stock),out,None if cache is None else max(0,cache-t),
               tuple(source_out),tuple(max(0,c-t) for c in source_cache),
               tuple(tuple(None if v is None else max(0,8-t+v) for v in road) for road in roads),
               None if output_cell is None else max(0,8-t+output_cell))
        states.append(state);events.append((departed,delivered))
    return states,events

def run_countdown(config):
    need,d,lengths,kinds,k,phase,initial,seed=config
    chains=[[-1]*size for size in lengths];y_product=[0 for _ in k]
    y_batch=[p+1 for p in phase];x_input=initial[:];x_batch=-1;x_product=0;head=-1
    result=[];events=[]
    for tick in range(1800):
        for i in range(len(k)):
            y_batch[i]=max(0,y_batch[i]-1) if y_batch[i]>=0 else -1
            if y_batch[i]==0 and y_product[i]<=50-k[i]:
                y_product[i]+=k[i];y_batch[i]=-1
        if x_batch>0:x_batch-=1
        if x_batch==0 and x_product<50:x_batch=-1;x_product+=1
        if head>0:head-=1
        gone=head==0 and tick%173>=80
        if gone:head=-1
        for chain in chains:
            for q in range(len(chain)):
                if chain[q]>0:chain[q]-=1
        visit=range(len(k)-1,-1,-1) if (tick//101+seed)%2 else range(len(k))
        for i in visit:
            dest=kinds[i];chain=chains[i]
            if chain[-1]==0 and x_input[dest]<50:chain[-1]=-1;x_input[dest]+=1
            for q in range(len(chain)-1,0,-1):
                if chain[q]==-1 and chain[q-1]==0:chain[q]=8;chain[q-1]=-1
        for i in range(len(k)):
            if chains[i][0]==-1 and y_product[i]>0:chains[i][0]=8;y_product[i]-=1
            if y_batch[i]==0 and y_product[i]<=50-k[i]:y_product[i]+=k[i];y_batch[i]=-1
        replenished=head==-1 and x_product>0
        if replenished:head=8;x_product-=1
        if x_batch==0 and x_product<50:x_product+=1;x_batch=-1
        y_batch=[8 if x==-1 else x for x in y_batch]
        if x_batch==-1 and all(x_input[i]>=need[i] for i in range(len(need))):
            for i in range(len(need)):x_input[i]-=need[i]
            x_batch=8*d
        result.append((tuple(x_input),x_product,None if x_batch<0 else x_batch,
                       tuple(y_product),tuple(y_batch),
                       tuple(tuple(None if a<0 else a for a in chain) for chain in chains),None if head<0 else head))
        events.append((gone,replenished))
    return result,events

cases=[]
for recipe,needs,d in [('crusher',[1],1),('grinder',[2,1],1),('shaper',[2],1),('packer',[10,15],5),('filler',[10,10],5)]:
    for i in range(32):
        rng=random.Random(961000+100*d+i)
        kinds=[kind for kind,a in enumerate(needs) for _ in range((a+d-1)//d+(i%2))]
        lengths=[rng.randrange(1,9) for _ in kinds]
        batches=[rng.randrange(1,4) for _ in kinds];phases=[rng.randrange(8) for _ in kinds]
        initial=[rng.randrange(51) for _ in needs]
        config=(needs,d,lengths,kinds,batches,phases,initial,i)
        a,ea=run_stamp(config);b,eb=run_countdown(config)
        assert a==b,(recipe,i,next(j for j in range(len(a)) if a[j]!=b[j]))
        assert ea==eb
        empty=sum(s[2] is None for s in a[600:]);assert empty==0,(recipe,i)
        unfilled=sum(s[6] is None for s in a[600:])
        if d==1:
            assert unfilled==0,(recipe,i)
            assert all(not sent or refill for sent,refill in ea[600:])
        cases.append({'recipe':recipe,'case':i,'lengths':lengths,'production_sizes':batches,'phases':phases,
                      'initial_stock':initial,'empty_cache_after600':empty,'empty_output_head_after600':unfilled})
ans={'cases':cases,'count':len(cases),'compared_steps':len(cases)*1800,
     'scope':'Fixed source contracts, pure belt paths, changing receiver order and repeated downstream pauses; not a whole factory.'}
(OUT/'propagation.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in ans.items() if k!='cases'})
