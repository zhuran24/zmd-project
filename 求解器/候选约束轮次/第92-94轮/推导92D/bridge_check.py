#!/usr/bin/env python3
"""Two independent small-step encodings; no import or modification of sim2.
Encoding A: physical directed channels, items, rule-31 judgement groups.
Encoding B: arrays of entry ages, explicitly listed edge operations.
A bridge axis is one component; physical previous-unit IDs prevent return.
The bridge counterexample uses one admissible supplied order where rule 28 is
undefined. It therefore does NOT claim rule 28 uniquely defines that order.
"""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class ChannelModel:
    def __init__(self, names, edges, order, groups='current', unit=None,
                 receiver=None, closed_until=0, full=True):
        self.names=names; self.edges=edges; self.order=order; self.groups=groups
        self.unit=unit or {n:n for n in names}
        self.receiver=receiver or self.unit
        self.out={n:[] for n in names}
        for a,b in edges: self.out[a].append(b)
        self.items={n:(-8,self.unit[names[i-1]] if i else 'source') if full else None
                    for i,n in enumerate(names)}
        self.items['sink']=None
        self.closed_until=closed_until; self.delivered=[]; self.trace=[]

    def run(self, steps, trace_until=28):
        for t in range(steps):
            judged=set(); events=[]
            def possible_dest(n):
                item=self.items[n]
                if not item: return []
                # A direction that would return to the previous UNIT is not
                # an attempt to send to that receiver, even if the axis differs.
                return [d for d in self.out[n] if self.unit.get(d,d)!=item[1]]
            def send(n):
                item=self.items[n]
                events.append(['judge',n])
                if item is None or t-item[0]<8: return
                for d in self.out[n]:
                    if self.unit.get(d,d)==item[1]: continue
                    if d=='sink':
                        if t<self.closed_until: continue
                        self.delivered.append(t)
                    elif self.items[d] is not None: continue
                    if d!='sink': self.items[d]=(t,self.unit[n])
                    self.items[n]=None; events.append(['send',n,d]); return
            for n in self.order:
                if n in judged: continue
                destinations=self.out[n] if self.groups=='current' else possible_dest(n)
                receiver_ids={self.receiver.get(d,d) for d in destinations}
                members={n}
                for a in self.names:
                    ds=self.out[a] if self.groups=='current' else possible_dest(a)
                    if any(self.receiver.get(d,d) in receiver_ids for d in ds):
                        members.add(a)
                # One representative input polling order; changing the order
                # cannot make U receive before P's own outgoing judgement.
                for a in self.names:
                    if a in members and a not in judged:
                        judged.add(a); send(a)
            # A nontransport source judges strictly after every component.
            if self.items[self.names[0]] is None:
                self.items[self.names[0]]=(t,'source')
                events.append(['send','source',self.names[0]])
            if t<trace_until:
                self.trace.append({'step':t,'events':events,
                   'entry_steps':{n:(None if self.items[n] is None else self.items[n][0]) for n in self.names}})
        return self


def array_model(count, operations, steps, closed_until=0, full=True):
    """Independent local recurrence; no graph/group/item code is shared."""
    entered=[-8]*count if full else [None]*count
    result=[]; trace=[]
    for step in range(steps):
        moves=[]
        for i in operations:
            if entered[i] is None or step-entered[i]<8: continue
            if i==count-1:
                if step<closed_until: continue
                result.append(step); entered[i]=None; moves.append([i,'sink'])
            elif entered[i+1] is None:
                entered[i+1]=step; entered[i]=None; moves.append([i,i+1])
        if entered[0] is None:
            entered[0]=step; moves.append(['source',0])
        if step<28: trace.append({'step':step,'moves':moves,'entry_steps':entered[:]})
    return result,trace


def stats(xs,warmup=1000):
    ys=[x for x in xs if x>=warmup]
    gaps=[b-a for a,b in zip(ys,ys[1:])]
    from fractions import Fraction
    return {'count_after_warmup':len(ys),'gaps':dict(sorted(Counter(gaps).items())),
      'rate_per_tick':str(Fraction(8*len(gaps),sum(gaps))) if gaps else None}


def main():
    results=[]
    # Belt U, bridges P and Q, belt D. P<->Q are two real channels.
    names=['U','P','Q','D']
    edges=[('U','P'),('P','Q'),('Q','P'),('Q','D'),('D','sink')]
    for mode,ops in [('current',[3,0,2,1]),('proposed',[3,2,1,0])]:
        for closed_until in [0,17,53]:
            a=ChannelModel(names,edges,['D','Q','P','U'],groups=mode,
                           closed_until=closed_until).run(12000)
            b,traceb=array_model(4,ops,12000,closed_until)
            assert a.delivered==b, (mode,closed_until,a.delivered[:20],b[:20])
            results.append({'case':'adjacent_bridge_pair','reading':mode,
             'closed_until_step':closed_until,'same_all_12000_steps':True,
             'statistics':stats(a.delivered),'first_deliveries':a.delivered[:16],
             'trace_A':a.trace,'trace_B':traceb,
             'layer_note':'current supplies D<Q<P<U as one undefined-layer possibility; proposed order counts simple paths'})
    # A separating belt X removes P<->Q: every receiver has one upstream.
    names=['U','P','X','Q','D']
    edges=list(zip(names,names[1:]))+[(names[-1],'sink')]
    for mode in ['current','proposed']:
        for closed_until in [0,53]:
            a=ChannelModel(names,edges,names[::-1],groups=mode,closed_until=closed_until).run(12000)
            b,_=array_model(5,list(range(4,-1,-1)),12000,closed_until)
            assert a.delivered==b
            results.append({'case':'bridge_pair_separated_by_belt','reading':mode,
             'closed_until_step':closed_until,'same_all_12000_steps':True,
             'statistics':stats(a.delivered),'first_deliveries':a.delivered[:16]})
    # Cross-axis textual alternative, isolated from the main coordinated reading:
    # forced early horizontal input exactly U then bridge then downstream.
    # This is a warning about reading "unit" without the explicit independence
    # of the two bridge axes, not a counterexample under the independence rule.
    for mode,ops in [('unit_group_early_input',[3,0,2,1]),('axis_independent',[3,2,1,0])]:
        deliveries,_=array_model(4,ops,12000)
        results.append({'case':'cross_axis_wording_diagnostic','reading':mode,
                        'statistics':stats(deliveries),
                        'status':'conditional schedule only; not a contradiction of independent axes'})
    # Reachable provenance trap without adjacent bridges: during debugging,
    # reverse gate G sends one mineral into bridge P; rotating that SAME G
    # makes P->G the final route, but P's previous physical unit remains G.
    debug=ChannelModel(['G','P'],[('G','P')],['P','G'],full=False).run(20)
    assert debug.items['P']==(8,'G') and debug.items['G']==(8,'source')
    final=ChannelModel(['U','P','G','D'],[('U','P'),('P','G'),('G','D'),('D','sink')],
                       ['D','G','P','U'],full=False)
    final.items['P']=(-12,'G')
    final.items['G']=(-12,'source')
    final.run(12000)
    # Independent array state machine, with previous-unit indices separately
    # written out. The debug stage is a two-cell reverse gate/bridge route.
    vals=[None,None]; previous=[None,None]
    for step in range(20):
        if vals[0] is not None and step-vals[0]>=8 and vals[1] is None:
            vals[1]=step; previous[1]=0; vals[0]=None; previous[0]=None
        if vals[0] is None: vals[0]=step; previous[0]=-1
    assert vals==[8,8] and previous==[-1,0]
    vals=[None,vals[1]-20,vals[0]-20,None]
    previous=[None,2,-1,None]
    independent=[]
    for step in range(12000):
        for i in [3,2,1,0]:
            if vals[i] is None or step-vals[i]<8: continue
            j=i+1
            if previous[i]==j: continue
            if j==4:
                independent.append(step); vals[i]=None; previous[i]=None
            elif vals[j] is None:
                vals[j]=step; previous[j]=i; vals[i]=None; previous[i]=None
        if vals[0] is None: vals[0]=step; previous[0]=-1
    assert final.delivered==independent==[8]
    assert final.items['P']==(-12,'G')
    results.append({'case':'debug_rotation_provenance_trap_no_adjacent_bridges',
       'reading':'current_and_proposed_with_persistent_previous_unit',
       'same_all_12000_steps':True,'statistics':stats(final.delivered),
       'debug_trace_A':debug.trace,'final_trace_A':final.trace,
       'final_deliveries':final.delivered,
       'assumption':'rotation preserves the physical unit and previous-unit identity; no snapshot rule resets it',
       'conclusion':'P never sends; the final directed chain is blocked forever'})
    from fractions import Fraction
    bound_a=Fraction(18-1,2*15)
    minerals_b=sum(30 for _ in range(17))
    powder_b=minerals_b
    dense_b=powder_b//2
    batteries_b=dense_b//15
    bound_b=Fraction(batteries_b,30)
    assert bound_a==bound_b==Fraction(17,30)<Fraction(3,5)
    data={'stalled_source_line_battery_bound':{
              'encoding_A_rate':str(bound_a),'encoding_B_30_tick_minerals':minerals_b,
              'encoding_B_dense_powder':dense_b,'encoding_B_batteries':batteries_b,
              'encoding_B_rate':str(bound_b),'target_rate':str(Fraction(3,5))},
          'encodings':'A channel/item/group model; B independent age-array recurrence',
          'steps_per_tick':8,'cases':results}
    (ROOT/'bridge_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(results),'all_crosschecked_cases':11,
       'rates':[(r['case'],r['reading'],r['statistics']['rate_per_tick']) for r in results]},ensure_ascii=False))

if __name__=='__main__': main()
