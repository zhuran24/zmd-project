"""Independent transcription of 98S2 section 2 and snapshot recipes.
No derivation-seat code is imported. All indices here are one based.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Machine:
    kind: str
    needs: tuple
    product: str
    amount: int = 1
    duration: int = 8

def graph():
    machines, sources, routes = {}, {}, []
    def m(name, kind, needs, product, amount=1, duration=8):
        machines[name] = Machine(kind, tuple(needs.items()), product, amount, duration)
    def e(src, dst, item):
        routes.append((src, dst, item))
    for i in range(1, 35):
        sources[f"蓝铁口{i}"] = "蓝铁矿"
        m(f"矿炉{i}", "精炼炉", {"蓝铁矿":1}, "蓝铁块")
        m(f"铁碎{i}", "粉碎机", {"蓝铁块":1}, "蓝铁粉末")
        e(f"蓝铁口{i}", f"矿炉{i}", "蓝铁矿")
        e(f"矿炉{i}", f"铁碎{i}", "蓝铁块")
        e(f"铁碎{i}", f"B{(i+1)//2}", "蓝铁粉末")
    sources["核心"] = "源矿"
    for i in range(1, 19):
        src = "核心" if i <= 6 else f"源矿口{i}"
        sources[src] = "源矿"
        m(f"源碎{i}", "粉碎机", {"源矿":1}, "源石粉末")
        e(src, f"源碎{i}", "源矿")
        e(f"源碎{i}", f"O{(i+1)//2}", "源石粉末")
    for i in range(1, 18):
        m(f"B{i}", "研磨机", {"蓝铁粉末":2, "砂叶粉末":1}, "致密蓝铁粉末")
        m(f"R{i}", "精炼炉", {"致密蓝铁粉末":1}, "钢块")
        e(f"B{i}", f"R{i}", "致密蓝铁粉末")
        e(f"R{i}", f"P{i}" if i <= 6 else f"H{(i-5)//2}", "钢块")
    for i in range(1, 10):
        m(f"O{i}", "研磨机", {"源石粉末":2, "砂叶粉末":1}, "致密源石粉末")
        e(f"O{i}", f"E{(i+2)//3}", "致密源石粉末")
    for i in range(1, 7):
        m(f"P{i}", "配件机", {"钢块":1}, "钢制零件")
        m(f"H{i}", "塑形机", {"钢块":2}, "钢质瓶")
        m(f"Q{i}", "研磨机", {"荞花粉末":2, "砂叶粉末":1}, "细磨荞花粉末")
        e(f"P{i}", f"E{(i+1)//2}", "钢制零件")
        f = (i+1)//2 if i <= 4 else i-2
        e(f"H{i}", f"F{f}", "钢质瓶")
        e(f"Q{i}", f"F{f}", "细磨荞花粉末")
    for i in range(1, 4):
        m(f"E{i}", "封装机", {"钢制零件":10, "致密源石粉末":15}, "高容谷地电池", duration=40)
        e(f"E{i}", "核心", "高容谷地电池")
    for i in range(1, 5):
        m(f"F{i}", "灌装机", {"钢质瓶":10, "细磨荞花粉末":10}, "精选荞愈胶囊", duration=40)
        e(f"F{i}", "核心", "精选荞愈胶囊")
    sand = [["B1","B2","O1"],["O2","O3"],
            ["B3","B4","O4"],["O5","O6"],
            ["B5","B6","O7"],["O8","O9"],
            ["B7","B8","B9"],["B10","Q1","Q2"],
            ["B11","B12","B13"],["B14","Q3","Q4"],
            ["B15","B16","Q5"],["B17"],["Q6"]]
    for plant, count, k in [("砂叶",13,3),("荞花",6,2)]:
        seed, powder = plant+"种子", plant+"粉末"
        for i in range(1,count+1):
            c,a,b,p = [f"{plant}{suffix}{i}" for suffix in ["采","回种","供种","碎"]]
            m(c,"采种机",{plant:1},seed,2)
            m(a,"种植机",{seed:1},plant)
            m(b,"种植机",{seed:1},plant)
            m(p,"粉碎机",{plant:1},powder,k)
            for src,dst,item in [(c,a,seed),(c,b,seed),(a,c,plant),(b,p,plant)]:
                e(src,dst,item)
            dests = sand[i-1] if plant == "砂叶" else [f"Q{i}"]*(2 if i<=5 else 1)
            for dst in dests:
                e(p,dst,powder)
    for src,dst,item in routes:
        assert src in machines or src in sources
        assert dst == "核心" or item in dict(machines[dst].needs)
        assert (machines[src].product if src in machines else sources[src]) == item
    return machines,sources,routes

AREA = {"粉碎机":9,"精炼炉":9,"配件机":9,"塑形机":9,
        "种植机":25,"采种机":25,"研磨机":24,"封装机":24,"灌装机":24}

if __name__ == "__main__":
    import json, networkx as nx
    from collections import Counter
    from pathlib import Path
    ms,ss,es=graph()
    g=nx.Graph()
    g.add_edges_from((a,b) for a,b,_ in es)
    planar, cert=nx.check_planarity(g, counterexample=True)
    result={"machines":dict(Counter(m.kind for m in ms.values())),
            "machine_count":len(ms),"body_area":sum(AREA[m.kind] for m in ms.values()),
            "routes":len(es),"planar_necessary_test":planar,
            "source_units":len(ss),"core_ore_routes":sum(a=="核心" for a,_,_ in es)}
    if not planar:
        result["kuratowski_edges"] = list(cert.edges())
    Path(__file__).with_name("graph_check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
