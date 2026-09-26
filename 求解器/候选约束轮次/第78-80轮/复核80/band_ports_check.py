# 复核80：右下条带 B=列49..69、行1..16 内的下边取货口端口数（47 种边带），及唯一非取货口格 q 的位置
def middles(gap):
    cells = [i for i in range(70) if i != gap]
    return [cells[j + 1] for j in range(0, 69, 3)]
res = []
for g in range(0, 70, 3):          # 左边空格 g，下边空格在角（下边 70 格中第 0 格被左边取货口占用或本身为空）
    res.append(("左", g, sum(49 <= m <= 69 for m in middles(0))))
for h in range(3, 70, 3):          # 下边空格 h，左边在角
    res.append(("下", h, sum(49 <= m <= 69 for m in middles(h))))
print(len(res), "种；B 内下边端口数取值：", sorted({r[2] for r in res}))
