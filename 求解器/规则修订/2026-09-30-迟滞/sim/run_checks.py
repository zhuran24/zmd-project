#!/usr/bin/env python3
"""Run all checks; output JSON and traces beneath this script's directory."""
import csv
import hashlib
import itertools as it
import json
from fractions import Fraction
from pathlib import Path

from simulator import (Belt, Box, Item, Machine, Merger, Sink, Source,
                       Splitter, World, steady_stats)

HERE = Path(__file__).resolve().parent


def stats(events, warmup=1000):
    r = steady_stats(events, warmup)
    times = [x[0] for x in events if x[0]>=warmup]
    gaps = [b-a for a,b in zip(times,times[1:])]
    # A reported exact fraction is a repeated observed gap pattern, not a fit
    # rounded to an expected denominator. Require at least ten repetitions.
    for p in range(1,min(len(gaps)//10,800)+1):
        tail = gaps[-10*p:]
        if all(tail[j] == tail[j%p] for j in range(len(tail))):
            r['gap_period'] = tail[:p]
            r['period_steps'] = sum(tail[:p])
            r['rate_fraction'] = str(Fraction(8*p,sum(tail[:p])))
            break
    return r


def trace_csv(name, events):
    fields=['t','unit','event','kind','destination','quantity','cell']
    with (HERE/name).open('w') as f:
        writer=csv.DictWriter(f,fields)
        writer.writeheader()
        writer.writerows(events)


def pure_chain():
    rows=[]
    for n, scope, inner, rev in it.product((1,2,3,4,8,16,64),
                     ('logistics','all_channels'),('flush_send','send_flush'),(False,True)):
        s=Source(); line=Belt('input',n); m=Machine(inner_order=inner)
        out=Belt('output'); sink=Sink()
        s.connect(line).connect(m).connect(out).connect(sink)
        order=[line,out] if not rev else [out,line]
        w=World(order+[m],[s],scope).run(8*n+2500)
        row=dict(n=n,scope=scope,inner=inner,order=[x.name for x in order],
                 **stats(m.starts,8*n+100))
        assert row['rate_fraction']=='1',row
        rows.append(row)
    return rows


def lag_case(n, names=('X','S','D'), polling='skip', cursor=1, initial='full', steps=12000, blocked='tail'):
    src=Source(); x=Splitter('X',polling,cursor); s=Belt('S',n)
    d=Box('D',full=True) if blocked=='direct_box' else Belt('D').fill()
    sink=Sink()
    src.connect(x); x.connect(s).connect(sink); x.connect(d)
    if initial=='full':
        x.fill(); s.fill()
    nodes={z.name:z for z in (x,s,d)}
    if blocked=='box':
        box=Box('B',full=True); d.connect(box); nodes['B']=box
    w=World([nodes[k] for k in names],[src],trace=steps<=80)
    phases=[]
    for _ in range(steps):
        w.step()
        if steps<=80:
            phases.append(dict(t=w.t-1,X=x.phase(w.t-1),S=s.phase(w.t-1)))
    return w,sink,x,phases


def lag():
    rows=[]
    for blocked in ('tail','box','direct_box'):
        namesets=list(it.permutations(('X','S','D','B') if blocked=='box' else ('X','S','D')))
        namesets=[ns for ns in namesets if
                  (blocked=='tail' or blocked=='box' and ns.index('D')<ns.index('B') or
                   blocked=='direct_box' and ns.index('X')<ns.index('D'))]
        for n,names,initial,cursor in it.product(range(1,5),namesets,('full','empty'),(0,1)):
            w,sink,x,_=lag_case(n,names,initial=initial,cursor=cursor,blocked=blocked)
            row=dict(n=n,order=names,initial=initial,cursor=cursor,blocked=blocked,
                     after_one_branch=names.index('X')>(names.index('S') if blocked=='direct_box' else
                                                       min(names.index('S'),names.index('D'))),
                     **stats(sink.received))
            expected=str(Fraction(8*n,8*n+1)) if names.index('X')<names.index('S') else '1'
            assert row['rate_fraction']==expected,row
            rows.append(row)
    alternatives=[]
    for n,policy,cursor in it.product(range(1,5),('rotate','hold'),(0,1)):
        w,sink,x,_=lag_case(n,polling=policy,cursor=cursor)
        alternatives.append(dict(n=n,policy=policy,cursor=cursor,**stats(sink.received)))
    w,sink,x,phases=lag_case(2,steps=45)
    trace_csv('b_n2_trace.csv',w.events)
    return dict(baseline=rows,splitter_polling=alternatives,phase_trace_n2=phases)


def make_machine_case(case,scope,inner,swap=False,trace=False,input_policy='skip'):
    m=Machine(quantity=2 if case==3 else 1,auxiliary=case==3,inner_order=inner,input_policy=input_policy)
    out=Belt('output'); sink=Sink()
    m.connect(out).connect(sink)
    if case==2:
        a=Belt('ab'); a.cells[0]=Item('a',-7)
        src=Source('ab_source',('b','a')); src.connect(a).connect(m)
        belts=[a]; sources=[src]
    else:
        a=Belt('a').fill('a',-7); b=Belt('b').fill('b',-7)
        sa=Source('a_source',('a',)); sb=Source('b_source',('b',))
        sa.connect(a).connect(m); sb.connect(b).connect(m)
        belts=[b,a] if swap else [a,b]
        sources=[sa,sb]
    if case==3:
        sand=Belt('sand'); ss=Source('sand_source',('sand',))
        ss.connect(sand).connect(m)
        belts.append(sand); sources.append(ss)
    w=World(belts+[out,m],sources,scope,trace)
    # Begin on t=1, exactly as the source timelines. Preloaded heads are ready.
    w.t=1
    return w,m,sink


def machines():
    rows=[]
    jobs=[]
    for case in (1,2,3):
        components=['ab','output'] if case==2 else ['a','b','output'] if case==1 else ['a','b','sand','output']
        jobs.extend((case,scope,inner,names) for scope,inner,names in
                    it.product(('logistics','all_channels'),('flush_send','send_flush'),it.permutations(components)))
    for case,scope,inner,names in jobs:
        w,m,sink=make_machine_case(case,scope,inner,trace=True)
        lookup={u.name:u for u in w.order}
        canonical=tuple(u.name for u in w.order[:-1])==names
        w.order=[lookup[n] for n in names]+[m]
        w.run(12000)
        st=stats(m.starts)
        alternating_period=[m.starts[i+2][0]-m.starts[i][0] for i in range(len(m.starts)-2)
                            if m.starts[i][0]>=1000]
        row=dict(case=case,scope=scope,inner=inner,order=names,
                 **st,AB_period=sorted(set(alternating_period)),
                 first_starts=m.starts[:7],first_finishes=m.finishes[:6],
                 first_cache_to_output=m.flushed[:6],first_sends=m.sent[:6],
                 first_receives=m.received[:16])
        assert all(m.starts[i][1]!=m.starts[i+1][1] for i in range(len(m.starts)-1)), row
        rows.append(row)
        if canonical:
            trace_csv(f'c{case}_{scope}_{inner}.csv',[e for e in w.events if e['t']<=50])
    # Full output slot and completed batch: isolates the unresolved inner order.
    blocked=[]
    for scope,inner in it.product(('logistics','all_channels'),('flush_send','send_flush')):
        m=Machine(inner_order=inner); out=Belt('output'); sink=Sink()
        m.output=[Item('A') for _ in range(50)]; m.cache=[Item('A')]
        m.slots[0]=[Item('a')]
        m.connect(out).connect(sink)
        w=World([out,m],scope=scope,trace=True).run(4)
        blocked.append(dict(scope=scope,inner=inner,first_start=m.starts[0][0],
                            first_flush=m.flushed[0][0],first_send=m.sent[0][0]))
    sequential=[]
    for case,policy,scope in it.product((1,2,3),('sequential','skip_one'),('logistics','all_channels')):
        w,m,sink=make_machine_case(case,scope,'flush_send',input_policy=policy)
        w.run(12000)
        sequential.append(dict(case=case,policy=policy,scope=scope,**stats(m.starts),first_starts=m.starts[:8],
                          late_recipe_counts={k:sum(t>=1000 and kind==k for t,kind in m.starts) for k in ('a','b')}))
    return dict(cases=rows,blocked_output=blocked,sequential_input=sequential)


def box_run(k, names=None, trace=False):
    belts=[Belt('L'+str(i)).fill() for i in range(k+1)]
    boxes=[Box('B'+str(i),full=True) for i in range(1,k+1)]
    source=Source(); sink=Sink(opens=0)
    source.connect(belts[0])
    for i,b in enumerate(boxes):
        belts[i].connect(b).connect(belts[i+1])
    belts[-1].connect(sink)
    nodes=belts+boxes
    if names is None:
        # All inputs before all boxes is one valid representative order.
        order=belts+list(reversed(boxes))
    else:
        lookup={u.name:u for u in nodes}; order=[lookup[n] for n in names]
    w=World(order,[source],trace=trace).run(k+12)
    return dict(k=k,order=[u.name for u in order],
                box_first_outputs={b.name:b.sent[0][0] for b in boxes},
                box_first_inputs={b.name:b.received[0][0] for b in boxes},
                upstream_first=belts[0].sent[0][0]), w


def boxes():
    rows=[]
    for k in range(1,7):
        r,w=box_run(k,trace=k==3)
        assert r['upstream_first']==k,r
        rows.append(r)
        if k==3:
            trace_csv('d_boxes3.csv',w.events)
    exhaustive=[]
    for k in range(1,4):
        names=['L'+str(i) for i in range(k+1)]+['B'+str(i) for i in range(1,k+1)]
        count=0; first=set()
        for perm in it.permutations(names):
            ix={v:i for i,v in enumerate(perm)}
            if not all(ix['L'+str(i-1)]<ix['B'+str(i)] and
                       ix['L'+str(i)]<ix['B'+str(i)] for i in range(1,k+1)):
                continue
            r,_=box_run(k,perm)
            count+=1; first.add(r['upstream_first'])
        exhaustive.append(dict(k=k,orders=count,upstream_first=sorted(first)))
    return dict(examples=rows,all_orders=exhaustive)


def mergers():
    rows=[]
    for policy,swap,cursor,phase in it.product(('skip','rotate','hold','rotate_busy'),
                                             (False,True),(0,1),range(40)):
        a=Belt('full'); b=Belt('sparse'); merge=Merger('merge',policy,cursor); sink=Sink()
        sa=Source('full_source'); sb=Source('sparse_source',('b',),period=40,phase=phase)
        sa.connect(a).connect(merge); sb.connect(b).connect(merge); merge.connect(sink)
        w=World([merge]+([b,a] if swap else [a,b]),[sa,sb]).run(12000)
        received=[v for v in sink.received if v[0]>=1000]
        rows.append(dict(policy=policy,order='ba' if swap else 'ab',cursor=cursor,phase=phase,
                         **stats(received),kinds={v:sum(x[1]==v for x in received) for v in ('a','b')}))
    return rows


def priority_insertion(n=1,early_ore=True,steps=12000,names=None):
    ore=Source('ore_source',('ore',)); blue=Source('blue_source',('blue',))
    x=Splitter('X'); s=Belt('S',n); y=Splitter('Y',cursor=0); m=Merger('M')
    dead=Belt('dead').fill('ore'); t=Belt('blue'); sink=Sink()
    ore.connect(x); x.connect(s).connect(y).connect(m).connect(sink); x.connect(dead)
    blue.connect(t).connect(m)
    order=[dead,m,y,x,s,t] if early_ore else [dead,m,t,y,x,s]
    if names is not None:
        lookup={u.name:u for u in order}; order=[lookup[name] for name in names]
    w=World(order,[ore,blue]).run(steps)
    seq=[kind for tick,kind in sink.received if tick>=1000]
    return dict(n=n,ore_first=early_ore,order=[u.name for u in order],**stats(sink.received),
                counts={kind:seq.count(kind) for kind in ('ore','blue')},sequence=seq[:30])


def priority_orders():
    rows=[]
    for names in it.permutations(('dead','M','Y','X','S','blue')):
        ix={n:i for i,n in enumerate(names)}
        if not all(ix[a]<ix[b] for a,b in [('M','Y'),('Y','S'),('M','blue'),('X','S'),('dead','X')]):
            continue
        for n in (1,2,3):
            rows.append(priority_insertion(n,ix['Y']<ix['blue'],names=names))
    return rows


def overflow(steps=12000,lagged=True,top_priority=True):
    # Essential topology visible in the community image; one-slot gates stand
    # in for separate one-slot transportation elements without rate limiting.
    src=Source(); feed=Belt('feed'); box=Box('factory',priority=True)
    top=Belt('top'); x=Splitter('X'); s=Belt('S'); gate=Splitter('top_gate',cursor=0)
    dead=Belt('dead').fill(); lower=Merger('lower'); lowline=Belt('lower_line',5)
    lg=[Splitter('lower_gate'+str(i),cursor=0) for i in range(3)]
    topsink=Sink('top_sink'); lowsink=Sink('lower_sink')
    src.connect(feed).connect(box); box.connect(top).connect(x).connect(s).connect(gate).connect(topsink)
    x.connect(dead); box.connect(lower).connect(lowline)
    prev=lowline
    for g in lg:
        prev=prev.connect(g)
    prev.connect(lowsink)
    order=[dead,gate,*reversed(lg),lowline,lower,*([x,s] if lagged else [s,x]),top,feed,box]
    if not top_priority:
        box.outputs.reverse()
    w=World(order,[src]).run(steps)
    out=[(t,'top') for t,_ in topsink.received]+[(t,'lower') for t,_ in lowsink.received]
    out.sort()
    seq=[kind for t,kind in out if t>=1000]
    # Branch choice is measured at the factory, before unequal path latency.
    choices=[dst for t,kind,dst in box.sent if t>=1000]
    return dict(lagged=lagged,top_priority=top_priority,counts={kind:seq.count(kind) for kind in ('top','lower')},
                branch_choices=choices[:32],top=stats(topsink.received),lower=stats(lowsink.received))


def main():
    saved=json.loads((HERE/'inputs.sha256.json').read_text())
    root=HERE.parents[3]
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==v for p,v in saved.items())
    result={}
    for name,fn in [('a',pure_chain),('b',lag),('c',machines),('d',boxes),('e',mergers),
                    ('f_insert',priority_orders),('f_overflow',overflow),
                    ('f_overflow_variants',lambda:[overflow(lagged=lag,top_priority=top) for lag,top in it.product((False,True),(False,True))])]:
        result[name]=fn()
        print(name,'done',flush=True)
    result['input_hashes_unchanged']=True
    (HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('results.json written',flush=True)


if __name__=='__main__':
    main()
