# 独立复核「传输按仓库余量判定」：一次触发对物品 x 的发送量与零条件
# 仓库同种只占一格、上限 80000、格数不限 => 余量 f = 80000 - 仓库现有 x
# 箱 6 格各 <=50，同种可分占多格；按格号从小到大送，送不完留原格（边界清单口径）；
# 另用逆序与任意顺序核对：合计发送与次序无关
import itertools, random
def send(cells, f, order):
    s = 0
    for i in order:
        t = min(cells[i], f - s); s += t
    return s
viol = 0; cnt = 0
for cells in itertools.product(range(0, 51, 7), repeat=3):
    for f in list(range(0, 160)) + [80000]:
        n = sum(cells)
        for order in itertools.permutations(range(3)):
            s = send(cells, f, order); cnt += 1
            if s != min(n, f) or ((s == 0) != (n == 0 or f == 0)): viol += 1
random.seed(1)
for _ in range(200000):
    cells = [random.choice([0, random.randint(0, 50)]) for _ in range(6)]
    f = random.choice([0, random.randint(0, 300), 80000 - random.randint(0, 80000)])
    order = random.sample(range(6), 6); n = sum(cells)
    s = send(cells, f, order); cnt += 1
    if s != min(n, f) or ((s == 0) != (n == 0 or f == 0)): viol += 1
# 周期合计：各次发送非负、合计为 0 => 每次为 0
print("cases", cnt, "violations", viol, "box cap", 6*50)
