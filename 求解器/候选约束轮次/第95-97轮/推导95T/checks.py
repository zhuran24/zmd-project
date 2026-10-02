"""95T arithmetic, construction-order and two independent density checks."""
from pathlib import Path
from fractions import Fraction as F
from itertools import permutations, product
from collections import deque
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
OLD = ROUND.parent / "第92-94轮"


def arithmetic_fraction():
    battery, capsule = F(3, 5), F(11, 20)
    parts, bottles = 10*battery, 10*capsule
    dense_ore, fine_flower = 15*battery, 10*capsule
    steel = parts + 2*bottles
    iron_powder, ore_powder = 2*steel, 2*dense_ore
    flower_powder = 2*fine_flower
    leaf_powder = steel+dense_ore+fine_flower
    flower_crush, leaf_crush = flower_powder/2, leaf_powder/3
    rates = [iron_powder+ore_powder+flower_crush+leaf_crush,
             iron_powder+steel, leaf_powder, bottles, parts,
             2*(flower_crush+leaf_crush), flower_crush+leaf_crush,
             battery, capsule]
    machines = [math.ceil(q*d) for q, d in zip(rates, [1]*7+[5, 5])]
    return {"machines": machines, "rates": list(map(str, rates)),
            "batch_counts_20_ticks": [int(20*q) for q in rates],
            "mixture_ports": [math.ceil(F(x+y, 2)) for x, y in [(3,2),(3,1),(2,1),(2,2)]],
            "stock": [64, int(4*flower_crush), int(4*leaf_crush)],
            "plant_inventory": [50-3*k for k in [1,2,3]],
            "D_bound": 49+50+49+1+1,
            "D_maximum": 50+50+50+1+1+50//2,
            "C_bound": str(F(50+50+50+1+1)+F(49,2)-F(1,2)),
            "seed_machine_all_single": math.ceil(F(16*9, 8)),
            "grinder_switch_limit": int(8*(32-F(63,2))),
            "grinder_every_batch_count": math.floor(9*(32-F(63,2))),
            "full_phases": math.perm(8, 6),
            "box_closed_window": 3*(40//8+1),
            "first_50_starts_last": 49*8, "first_empty_lower_bound": 50*8}


def arithmetic_integer():
    # Independent integer material balance in a 20-tick production cycle.
    parts = 12*10
    dense = 12*15
    bottles = 11*10
    fine = 11*10
    steel = parts+2*bottles
    grind = steel+dense+fine
    leaf = grind//3
    flower = fine
    counts = [2*steel+2*dense+leaf+flower, 3*steel, grind,
              bottles, parts, 2*(leaf+flower), leaf+flower, 12, 11]
    capacity = [20]*7+[4,4]
    need = [next(n for n in range(100) if n*c >= b) for b,c in zip(counts,capacity)]
    port_counts = []
    for x,y in [(3,2),(3,1),(2,1),(2,2)]:
        n = 0
        while 2*n < x+y:
            n += 1
        port_counts.append(n)
    phases = sum(1 for p in permutations(range(8), 6))
    # Interval scheduling instead of the closed-form division.
    dp = [0]*49
    for t in range(41):
        dp[t+8] = max(dp[t+8], dp[t]+1)
        dp[t+1] = max(dp[t+1], dp[t])
    per_port = max(dp)
    # Enumerate the small independent inventory inequalities used in the proofs.
    lower = min(a+b+c+ca+cc for a,b,c,ca,cc in product(range(49,51),range(50,51),range(49,51),[1],[1]))
    upper = max(a+b+c+ca+cc+o/2 for a,b,c,ca,cc,o in product([0,50],[0,50],[0,50],[0,1],[0,1],[0,50]))
    result = {"machines": need, "rates": [str(F(n,20)) for n in counts],
              "batch_counts_20_ticks": counts, "mixture_ports": port_counts,
              "stock": [2*32, 2*(2*flower//20), 2*(2*leaf//20)],
              "plant_inventory": [50-k-k-k for k in [1,2,3]],
              "D_bound": lower, "D_maximum": int(upper),
              "C_bound": str((2*50*3+2+2+49-1)//2),
              "seed_machine_all_single": next(n for n in range(50) if 8*n >= 16*9),
              "grinder_switch_limit": (32*160-8*630)//20,
              "grinder_every_batch_count": max(a for a in range(33) if 18*32-2*a >= 9*63),
              "full_phases": phases, "box_closed_window": 3*per_port,
              "first_50_starts_last": sum([8]*49), "first_empty_lower_bound": sum([8]*50)}
    return result


def orders():
    # Actual channel time is the later construction time of its two units.
    certs = []
    for seq in [("core","sourceA","sourceB","M","U","S","N","P","Q"),
                ("core","sourceA","sourceB","M","S","N","U","P","Q")]:
        rank = {v:i for i,v in enumerate(seq)}
        edges = [("U","M"),("S","M"),("S","N"),("P","S"),("Q","U")]
        times = {a+"->"+b: max(rank[a],rank[b]) for a,b in edges}
        assert times["S->M"] < times["S->N"]
        certs.append({"non_belt_build_order": seq, "times": times,
                      "first_of_S_U": "S" if min(times["S->M"],times["S->N"]) < times["U->M"] else "U",
                      "belts": "all belt units follow these units; outgoing belt connections are later"})
    assert {x["first_of_S_U"] for x in certs} == {"S","U"}
    # Independent channel-formation event scan, not a max() computation.
    for x in certs:
        built, events = set(), {}
        for t,u in enumerate(x["non_belt_build_order"]):
            built.add(u)
            for edge in x["times"]:
                if edge not in events and set(edge.split("->")) <= built:
                    events[edge] = t
        assert events == x["times"]
    levels = []
    for m in range(2, 9):
        for k in range(2, 9):
            # Dead terminal has no outgoing channel, hence is not eligible
            # when its predecessor counts layers.
            dead = [None]*k
            dead[-1] = 1
            dead[-2] = 1
            for j in range(k-3,-1,-1):
                dead[j] = dead[j+1]+1
            active = [None]*m
            active[-1] = 1
            for j in range(m-2,-1,-1):
                active[j] = active[j+1]+1
            assert dead[0]+1 == k and active[0] == m
            levels.append([k,m,dead[0]+1,active[0]])
    # With source first, either receiving unit may be built first.
    grade = []
    for seq in [("source","merger","ordinary"),("source","ordinary","merger")]:
        rank = dict(zip(seq,range(3)))
        grade.append({"build_order": seq, "merger_channel": max(rank["source"],rank["merger"]),
                      "ordinary_channel": max(rank["source"],rank["ordinary"])})
    return {"density": certs, "dead_branch_layer_cases": levels,
            "equal_layer_order_witness": "Build splitter and dead-branch first unit before all belts; build active band's terminal belt last. Splitter's first output predates the active band's output.",
            "grade_reversal": grade}


LENGTHS = {"R":1,"T":2,"M":1,"N":1,"S":1,"U":1,"P":1,"Q":1,"LA":16,"LB":16}
DEST = {"R":"warehouse","T":"warehouse","M":"R","N":"T","U":"M","P":"S","Q":"U","LA":"P","LB":"Q"}


class DenseTimestamp:
    def __init__(self, first):
        self.order = ["R","T","M","N"] + (["S","U"] if first=="S" else ["U","S"]) + ["P","Q","LA","LB"]
        self.cells = {n:[None]*v for n,v in LENGTHS.items()}
        self.next_gate = {"P":0,"Q":0}
        self.split = 1
        self.stock = 80000
        self.count = [0,0,0]

    def accept(self, dest, t):
        if dest == "warehouse":
            if self.stock == 80000:
                return False
            self.stock += 1
            return True
        if self.cells[dest][0] is not None or (dest in self.next_gate and t < self.next_gate[dest]):
            return False
        self.cells[dest][0] = t
        if dest in self.next_gate:
            self.next_gate[dest] = t+40
        return True

    def step(self, t):
        for n in self.order:
            cells = self.cells[n]
            if cells[-1] is not None and t-cells[-1] >= 8:
                if n == "S":
                    for j in [self.split,1-self.split]:
                        if self.accept(["M","N"][j],t):
                            cells[-1] = None
                            self.count[j] += 1
                            self.split = 1-j
                            break
                elif self.accept(DEST[n],t):
                    cells[-1] = None
                    if n == "U": self.count[2] += 1
            for j in range(len(cells)-2,-1,-1):
                if cells[j] is not None and t-cells[j]>=8 and cells[j+1] is None:
                    cells[j+1],cells[j] = t,None
        for n in ["LA","LB"]:
            if self.stock and self.cells[n][0] is None:
                self.stock -= 1
                self.cells[n][0] = t

    def state(self,t):
        return (tuple(tuple(-1 if v is None else min(8,t-v) for v in self.cells[n]) for n in LENGTHS),
                tuple(max(0,self.next_gate[n]-t) for n in ["P","Q"]),self.split,self.stock)


class DenseCountdown:
    def __init__(self, first):
        self.names = list(LENGTHS)
        self.ids = {n:i for i,n in enumerate(self.names)}
        self.cargo = [[-1]*LENGTHS[n] for n in self.names]
        self.wait = [0,0]
        self.turn = deque(["N","M"])
        self.stock = 80000
        self.count = [0,0,0]
        self.order = [self.ids[n] for n in (["R","T","M","N"]+(["S","U"] if first=="S" else ["U","S"])+["P","Q","LA","LB"])]

    def step(self,t):
        if t:
            self.wait = [max(0,x-1) for x in self.wait]
            for cells in self.cargo:
                for j,a in enumerate(cells):
                    if a >= 0: cells[j] = min(8,a+1)
        for q in self.order:
            name = self.names[q]
            cells = self.cargo[q]
            if cells[-1] == 8:
                targets = list(self.turn) if name=="S" else [DEST[name]]
                for target in targets:
                    gate = ["P","Q"].index(target) if target in ["P","Q"] else None
                    okay = (self.stock<80000 if target=="warehouse" else self.cargo[self.ids[target]][0]<0)
                    if gate is not None and self.wait[gate]>0: okay=False
                    if okay:
                        if target=="warehouse": self.stock+=1
                        else: self.cargo[self.ids[target]][0]=0
                        if gate is not None: self.wait[gate]=40
                        cells[-1]=-1
                        if name=="S":
                            self.count[0 if target=="M" else 1]+=1
                            self.turn.remove(target)
                            self.turn.append(target)
                        elif name=="U": self.count[2]+=1
                        break
            empty = len(cells)-1
            while empty:
                if cells[empty]<0 and cells[empty-1]==8:
                    cells[empty]=0
                    cells[empty-1]=-1
                empty-=1
        for name in ["LB","LA"]:
            q=self.ids[name]
            if self.stock>0 and self.cargo[q][0]<0:
                self.cargo[q][0]=0
                self.stock-=1

    def state(self,t):
        return (tuple(tuple(c) for c in self.cargo),tuple(self.wait),0 if self.turn[0]=="M" else 1,self.stock)


def density():
    results = []
    for first in ["U","S"]:
        a,b = DenseTimestamp(first),DenseCountdown(first)
        seen = {}
        trace = []
        stock_min_a = stock_min_b = 80000
        for t in range(2000):
            a.step(t); b.step(t)
            assert a.state(t)==b.state(t) and a.count==b.count,(first,t)
            stock_min_a = min(stock_min_a, a.stock)
            stock_min_b = min(stock_min_b, b.stock)
            s=a.state(t)
            if s in seen:
                old,counts=seen[s]
                period=t-old
                delta=[x-y for x,y in zip(a.count,counts)]
                result={"first":first,"repeat_step_ends":[old,t],"period_steps":period,
                        "counts":[int(x) for x in delta],"rates":[str(F(8*x,period)) for x in delta],
                        "warehouse":a.stock,"minimum_warehouse":stock_min_a,"states_compared":t+1}
                assert stock_min_a == stock_min_b == 79966
                assert result["rates"] == (["0","1/5","1/5"] if first=="U" else ["1/10","1/10","1/5"])
                results.append(result)
                break
            seen[s]=(t,a.count.copy())
            if t>=120:
                trace.append({"step":t,"count":a.count.copy(),"state":s})
        else:
            raise AssertionError("cycle not found")
        (HERE/("density_trace_"+first+".json")).write_text(json.dumps(trace,ensure_ascii=False,indent=2)+"\n")
    return results


def main():
    a,b=arithmetic_fraction(),arithmetic_integer()
    assert a==b,(a,b)
    result={"arithmetic":a,"arithmetic_encodings_equal":True,"orders":orders(),"density":density()}
    cs=json.loads((ROUND/"第92轮候选清单.json").read_text())
    assert len(cs)==35
    manifest=[]
    files=list((ROUND/"前提快照").glob("*"))+[ROUND/"临时规则.md",ROUND/"第92轮候选清单.json",ROUND/"修正清单.json"]
    files += sorted({Path(c["derive_report"]) for c in cs})
    files += [OLD/"推导92C-临时规则续轮.md"]
    for p in files:
        content=p.read_bytes()
        manifest.append({"path":str(p),"sha256":hashlib.sha256(content).hexdigest(),"bytes":len(content),"lines":len(content.splitlines())})
    result["inputs"]=manifest
    result["candidate_index"]=[{"id":i,"group":c["group"],"name":c["name"],"kind":c["kind"],"derive_report":c["derive_report"]} for i,c in enumerate(cs,1)]
    (HERE/"checks.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"arithmetic":a,"density":result["density"],"candidates":len(cs),"status":"PASS"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
