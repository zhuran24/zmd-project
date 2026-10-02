"""Replay original JSON certificates using only the two new engines.
No original Python is imported or executed. Original JSON omits final connection
orders; use independently generated physical rebuild orders and explicitly record
that limitation. Both stored state encodings are decoded separately.
"""
import json,re,random,hashlib
from collections import defaultdict,deque,Counter
from pathlib import Path
from model_spec import graph
from engine_time import TimestampWorld
from engine_age import AgeWorld
from factory_check import compare,units

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parent/"推导98S2"
PREFIX={"矿精炼":"矿炉","铁粉碎":"铁碎","源粉碎":"源碎","铁研磨":"B","源研磨":"O","荞研磨":"Q",
        "钢精炼":"R","配件":"P","塑形":"H","封装":"E","灌装":"F",
        "砂叶采种":"砂叶采","砂叶种植A":"砂叶回种","砂叶种植B":"砂叶供种","砂叶粉碎":"砂叶碎",
        "荞花采种":"荞花采","荞花种植A":"荞花回种","荞花种植B":"荞花供种","荞花粉碎":"荞花碎"}

def name(n):
    if n.startswith("协议核心"):return "核心"
    p,i=re.fullmatch(r"(.*?)(\d+)",n).groups()
    return PREFIX[p]+str(int(i)+1)

def replay(seed):
    path=ORIGINAL/f"cycle_{seed}.json";raw=path.read_bytes();c=json.loads(raw)
    g=json.loads((ORIGINAL/c["graph_path"]).read_text());ms,ss,es=graph()
    inventory=defaultdict(deque)
    for i,e in enumerate(es):inventory[e].append(i)
    mapping={};lengths=[0]*len(es)
    for r in g["routes"]:
        dst=name(r["to"])
        if r["from"].startswith("仓库取货口"):
            src=("蓝铁口"+dst[2:]) if dst.startswith("矿炉") else ("源矿口"+dst[2:])
        else:src=name(r["from"])
        e=(src,dst,r["item"]);i=inventory[e].popleft();mapping[r["id"]]=i;lengths[i]=r["length"]
    assert all(not v for v in inventory.values())
    a=TimestampWorld(lengths,prepared=False);b=AgeWorld(lengths,prepared=False)
    physical,belts=units(ms,ss,es,lengths);physical+=belts;random.Random(seed+99).shuffle(physical)
    a.rebuild(physical,False);b.rebuild(physical,False)
    A,B=c["state_a"],c["state_b"]
    row_names=[]
    # A carries input quantities in recipe order, remaining steps, done flag,
    # outgoing service order, and the last successful receiving channel.
    for row in A[0]:
        inp,out,rem,ready,send_order,last_in=row
        n=es[mapping[send_order[0]]][0];row_names.append(n)
        assert len(inp)==len(ms[n].needs)
        a.inputs[n]=dict(zip((x for x,v in ms[n].needs),inp));a.output[n]=out
        a.done[n]=0 if ready else (rem if rem else None)
        for rank,e in enumerate(send_order):a.last_send[mapping[e]]=rank-100
        a.last_receive[n]=None if last_in is None else mapping[last_in]
    for src_order in A[2]:
        for rank,e in enumerate(src_order):a.last_send[mapping[e]]=rank-100
    a.last_receive["核心"]=mapping[A[3]] if A[3] is not None else None
    # JSON belt ages are evaluated at the next step index: a just-replenished
    # fast source has remaining=8 and its first belt has age=1. Our snapshots
    # are after the previous step, so subtract one from nonempty belt ages.
    for original_i,row in enumerate(A[1]):
        assert all(age==-1 or 1<=age<=8 for age in row)
        a.belts[mapping[original_i]]=[None if age<0 else 1-age for age in row]
    # B stores named input dictionaries and time-to-completion minus one.
    for j,n in enumerate(row_names):
        k=b.name_id[n];stored=dict(B[0][j]);b.stock[k]=[stored.get(x,0) for x in b.need[k]]
        b.goods[k]=B[1][j];b.clock[k]=0 if B[3][j] else (-1 if B[2][j] is None else B[2][j]+1)
        b.recvlast[n]=None if B[5][j] is None else mapping[B[5][j]]
    for order in B[6]:
        for rank,e in enumerate(order):b.last[mapping[e]]=rank-100
    b.recvlast["核心"]=None if B[5][-1] is None else mapping[B[5][-1]]
    for original_i,row in enumerate(B[4]):
        e=mapping[original_i]
        for k,age in enumerate(row):b.cells[b.start[e]+k]=-1 if age is None else age-1
    initial=compare(a,b);a.check_contract()
    for _ in range(c["period_steps"]):a.step();b.step();compare(a,b);a.check_contract()
    final=a.signature()
    # Ages >=7 at a between-step boundary are equivalent for the next decision.
    def canonical(s):
        return (s[0],tuple(tuple(None if a is None else min(a,7) for a in r) for r in s[1]),s[2],s[3])
    assert canonical(initial)[:3]==canonical(final)[:3],(seed,"material/send state not closed")
    receive_pointer_changed=canonical(initial)[3]!=canonical(final)[3]
    assert dict(a.delivered)==c["delivery"]
    ore=[a.sent[i] for i,(s,d,x) in enumerate(es) if s in ss]
    assert len(ore)==52 and set(ore)=={60}
    expected_refusal=Counter({mapping[r["id"]]:r["refusals"] for r in c["cycle_refusals"]})
    assert sum(a.refused)==c["all_refusals"]
    assert all(a.refused[i]==expected_refusal[i] for i in range(len(es)))
    first_delivery=dict(a.delivered);first_refusals=sum(a.refused)
    # A new legal connection order may change a receiving pointer once. Check
    # an additional full period rather than silently deleting that pointer.
    for _ in range(c["period_steps"]):a.step();b.step();compare(a,b);a.check_contract()
    assert canonical(final)==canonical(a.signature()),(seed,"second period not fully closed")
    assert all(a.delivered[x]==2*n for x,n in first_delivery.items())
    return {"certificate":str(path.relative_to(HERE.parent)),"sha256":hashlib.sha256(raw).hexdigest(),
            "period":c["period_steps"],"dual_decode_initial_equal":True,"dual_transition_steps":a.t,
            "material_state_closure_first_period":True,"direct_tuple_closure_second_period":True,
            "receiving_pointer_changed_after_new_rebuild":receive_pointer_changed,"delivery_per_period":first_delivery,"ore_each":60,
            "route_refusals_match":True,"total_refusals_per_period":first_refusals,
            "clock_decode":"Transport ages in the JSON are next-step ages; subtract one at our between-step boundary. B countdown is one less than A countdown.",
            "limitation":"Stored final channel connection orders are absent; replay uses a new legal physical-unit rebuild order, keeping the stored service history."}

if __name__=="__main__":
    result=[replay(s) for s in (98040,98041,98042)]
    HERE.joinpath("certificate_replay.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
