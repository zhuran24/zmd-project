"""Exhaustive one-step search in a non-splitting layered motif.

Slots: 0,1 -> merger 2; 2,3 -> X; 4 -> Y. Slots 0/1 are layer 2;
2/3/4 are layer 1. Values -1 empty, 0 immature, 1 ready, 2 ready but
cannot return to the destination unit. Receiver histories remain fixed.
These local states are a superset; no full-layout reachability is claimed.
"""
import itertools,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
target=[2,2,5,5,6];groups={2:[0,1],5:[2,3],6:[4]}

def sequential(values,spaces,history,order):
    v=list(values);room=dict(zip((5,6),spaces));rr=dict(zip((2,5,6),history));done=set()
    for source in order:
        if source in done:continue
        if v[source]!=1:done.add(source);continue
        dest=target[source];seq=groups[dest][:]
        if rr[dest] in seq:
            k=seq.index(rr[dest])+1;seq=seq[k:]+seq[:k]
        for sender in seq:
            if sender in done:continue
            empty=v[dest]==-1 if dest<5 else room[dest]>0
            if v[sender]==1 and empty:
                v[sender]=-1
                if dest<5:v[dest]=0
                else:room[dest]-=1
                rr[dest]=sender
            done.add(sender)
    return tuple(v),(room[5],room[6]),tuple(rr[k] for k in (2,5,6))

def event_group(values,spaces,history,order):
    cargo={i:v for i,v in enumerate(values)};capacity={5:spaces[0],6:spaces[1]}
    recent={2:history[0],5:history[1],6:history[2]};rank={v:i for i,v in enumerate(order)}
    # Group event is located at its first actually eligible upstream judgment.
    actions=[]
    for receiver,senders in groups.items():
        ready=[s for s in senders if cargo[s]==1]
        if ready:actions.append((min(rank[s] for s in ready),receiver))
    for _,receiver in sorted(actions):
        senders=groups[receiver];last=recent[receiver]
        start=senders.index(last)+1 if last in senders else 0
        for k in range(len(senders)):
            s=senders[(start+k)%len(senders)]
            if cargo[s]!=1:continue
            can_receive=cargo[receiver]<0 if receiver<5 else capacity[receiver]!=0
            if can_receive:
                cargo[s]=-1
                if receiver<5:cargo[receiver]=0
                else:capacity[receiver]-=1
                recent[receiver]=s
    return tuple(cargo[i] for i in range(5)),(capacity[5],capacity[6]),tuple(recent[k] for k in (2,5,6))

perms=[p+q for p in itertools.permutations((2,3,4)) for q in itertools.permutations((0,1))]
count=0;transitions=0
for slots in itertools.product((-1,0,1,2),repeat=5):
    for spaces in itertools.product(range(3),range(2)):
        for history in itertools.product((0,1),(2,3),(4,)):
            expected=None
            for order in perms:
                a=sequential(slots,spaces,history,order);b=event_group(slots,spaces,history,order)
                assert a==b,(slots,spaces,history,order,a,b)
                if expected is None:expected=a
                assert a==expected,(slots,spaces,history,order)
                transitions+=1
            count+=1

# Formation times of a geometrically possible triangle of physical units:
# a 3x3 machine's two neighbouring bridge units also touch each other.
formation=[]
edges=((0,1),(0,2),(1,2))
for perm in itertools.permutations(range(3)):
    t={u:i for i,u in enumerate(perm)}
    via_max=[max(t[x],t[y]) for x,y in edges]
    built=set();via_events=[None]*3
    for step,u in enumerate(perm):
        built.add(u)
        for i,(x,y) in enumerate(edges):
            if via_events[i] is None and x in built and y in built:via_events[i]=step
    assert via_max==via_events and len(set(via_max))==2
    formation.append({'units':perm,'edge_times':via_max})

# Violating the unique nontransport-source premise really loses confluence.
def first_claim(order):
    head=None;sent={x:0 for x in order}
    for source in order:
        if head is None:head=source;sent[source]+=1
    return head,sent
negative=[first_claim(('west','north')),first_claim(('north','west'))]
assert negative[0]!=negative[1]
ans={'initial_states':count,'permutations_each':len(perms),'compared_transitions':transitions,
     'order_differences':0,'encoding_differences':0,'triangle_formation':formation,
     'strict_three_edge_orders':0,'negative_shared_machine_sources':negative,
     'scope':'Local functional DAG motif and contract states, not an enumeration of all layouts.'}
(OUT/'order.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in ans.items() if k not in ('triangle_formation','negative_shared_machine_sources')})
