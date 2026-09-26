# 复核80 编码一：CP-SAT 布尔编码（占格 AtMostOne + 空邻格指示变量 + 条件 BoolOr）
import argparse, json, time, sys
from ortools.sat.python import cp_model
from pole_geom import enumerate_options


def build(wall, cap, threshold=None, maximize=False, fix=None, extra_cap=None, unit=False):
    opts = enumerate_options(wall)
    if unit:
        for o in opts:
            o["wt"] = 1
    m = cp_model.CpModel()
    u = [m.NewBoolVar(f"u{i}") for i in range(len(opts))]
    cover = {}
    for i, o in enumerate(opts):
        for g in o["cells"]:
            cover.setdefault(g, []).append(i)
    for g, lst in cover.items():
        if len(lst) > 1:
            m.AddAtMostOne([u[i] for i in lst])
    free = {}

    def freevar(g):
        if g not in free:
            v = m.NewBoolVar(f"f{g}")
            # 该格空（不被任何选中机身占用）当且仅当 v=1
            m.Add(v + sum(u[i] for i in cover[g]) == 1)
            free[g] = v
        return free[g]

    for i, o in enumerate(opts):
        for side in o["sides"]:
            if any(g not in cover for g in side):
                continue  # 有一个邻格根本不可能被机身占用，恒可用
            m.AddBoolOr([freevar(g) for g in side]).OnlyEnforceIf(u[i])
    m.Add(sum(u) <= cap)
    obj = sum(o["wt"] * u[i] for i, o in enumerate(opts))
    if threshold is not None:
        m.Add(obj >= threshold)
    if maximize:
        m.Maximize(obj)
    if fix is not None:
        for i in fix:
            m.Add(u[i] == 1)
    return m, u, opts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wall", action="store_true")
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--threshold", type=int, default=None)
    ap.add_argument("--maximize", action="store_true")
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--name", default="run")
    ap.add_argument("--unit", action="store_true")
    a = ap.parse_args()
    cap = a.cap if a.cap is not None else (14 if a.wall else 23)
    t0 = time.time()
    m, u, opts = build(a.wall, cap, a.threshold, a.maximize, unit=a.unit)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = a.seconds
    s.parameters.num_workers = a.workers
    s.parameters.log_search_progress = True
    s.log_callback = lambda line: print(line, flush=True)
    st = s.Solve(m)
    res = dict(name=a.name, unit=a.unit, wall=a.wall, cap=cap, threshold=a.threshold, maximize=a.maximize,
               n_options=len(opts), status=s.StatusName(st), wall_seconds=time.time() - t0,
               objective=(s.ObjectiveValue() if a.maximize and st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None),
               bound=(s.BestObjectiveBound() if a.maximize else None))
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        chosen = [i for i in range(len(opts)) if s.Value(u[i])]
        res["solution"] = [dict(cat=opts[i]["cat"], w=opts[i]["w"], h=opts[i]["h"], axis=opts[i]["axis"],
                                x=opts[i]["x"], y=opts[i]["y"]) for i in chosen]
        res["weighted"] = sum(opts[i]["wt"] for i in chosen)
        res["count"] = len(chosen)
    json.dump(res, open(f"{a.name}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "solution"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
