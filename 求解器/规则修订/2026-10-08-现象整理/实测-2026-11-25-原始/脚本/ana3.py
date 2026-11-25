"""逐帧认一列带子上的物品（深灰方块），连成轨迹，打印每件的行程：什么时刻在哪停、什么时刻动。
用法：ana3.py 帧.npz x中心 y上 y下 [遮挡区 y1-y2 ...]   坐标是屏幕像素；裁图原点 (1180,600)。"""
import sys, time, numpy as np
d = np.load(sys.argv[1]); T = d["t"][:, 0]; F = d["f"]
X0, Y0 = 1180, 600
xc, ya, yb = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
masks = [tuple(map(int, a.split("-"))) for a in sys.argv[5:]]
PITCH = 39.75
def items(frame):
    strip = frame[ya - Y0:yb - Y0, xc - X0 - 6:xc - X0 + 7].astype(float)
    v = strip.max(axis=2).mean(axis=1)
    dark = v < 95
    res, i = [], 0
    while i < len(dark):
        if dark[i]:
            j = i
            while j < len(dark) and dark[j]: j += 1
            if 15 <= j - i <= 25:
                y = (i + j - 1) / 2 + ya
                if not any(a - 12 <= y <= b + 12 for a, b in masks): res.append(y)
            i = j
        else:
            i += 1
    return res
tracks = []   # 每条：[(t,y),...]
for k in range(len(T)):
    for y in items(F[k]):
        best = None
        for tr in tracks:
            t1, y1 = tr[-1]
            if T[k] - t1 < 0.6 and -3 <= y - y1 <= 14 * max(0.05, T[k] - t1) * 2 + 3:
                if best is None or abs(y - y1) < abs(y - best[-1][1]): best = tr
        if best is None: tracks.append([(T[k], y)])
        else: best.append((T[k], y))
fmt = lambda t: time.strftime("%M:%S", time.localtime(t)) + ("%.2f" % (t % 1))[1:]
cellj = lambda y: 16 + (y - 662) / PITCH
print("帧", len(T), fmt(T[0]), "–", fmt(T[-1]))
for tr in tracks:
    if len(tr) < 25: continue
    a = np.array(tr)
    # 分段：停着（0.4 秒内位移 < 2 像素）和走着
    segs, i = [], 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and abs(a[j + 1, 1] - a[i, 1]) < 2.5: j += 1
        if a[j, 0] - a[i, 0] >= 0.5:
            segs.append("停 %s–%s 在格 %.2f" % (fmt(a[i, 0]), fmt(a[j, 0]), cellj(np.median(a[i:j + 1, 1]))))
            i = j + 1
        else:
            j = i
            while j + 1 < len(a) and not (j + 12 < len(a) and abs(a[j + 12, 1] - a[j, 1]) < 2.5): j += 1
            if j > i + 5:
                sl, ic = np.polyfit(a[i:j + 1, 0] - a[i, 0], a[i:j + 1, 1], 1)
                segs.append("走 %s–%s 格 %.2f→%.2f 速度 %.1f" % (fmt(a[i, 0]), fmt(a[j, 0]), cellj(a[i, 1]), cellj(a[j, 1]), sl))
            i = j + 1
    print("件：", "；".join(segs))
