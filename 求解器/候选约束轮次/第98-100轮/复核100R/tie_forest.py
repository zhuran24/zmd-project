"""核对：存在没有同刻接通的单位建造次序，当且仅当通道图（无向、计重边）是森林。
编码一：穷举单位排列，看有没有一种排列每个新建单位至多与 1 条已建邻居形成通道。
编码二：并查集判圈（重边即圈）。随机小图逐例比较。"""
import itertools, random, json

def has_strict_order(n, edges):
    for perm in itertools.permutations(range(n)):
        built = set(); ok = True
        for u in perm:
            k = sum(1 for (a, b) in edges if (a == u and b in built) or (b == u and a in built))
            if k > 1: ok = False; break
            built.add(u)
        if ok: return True
    return False

def is_forest(n, edges):
    p = list(range(n))
    def f(x):
        while p[x] != x:
            p[x] = p[p[x]]; x = p[x]
        return x
    for a, b in edges:
        ra, rb = f(a), f(b)
        if ra == rb: return False
        p[ra] = rb
    return True

random.seed(20261002)
cnt = {"cases": 0, "agree": 0, "forest": 0}
for _ in range(3000):
    n = random.randint(2, 6)
    m = random.randint(1, 8)
    edges = []
    for _ in range(m):
        a, b = random.sample(range(n), 2)
        edges.append((a, b))   # 允许重边：两单位间双向通道（如相邻桥接器）
    s = has_strict_order(n, edges); fo = is_forest(n, edges)
    cnt["cases"] += 1; cnt["agree"] += (s == fo); cnt["forest"] += fo
print(cnt)
json.dump(cnt, open("tie_forest.json", "w"))
