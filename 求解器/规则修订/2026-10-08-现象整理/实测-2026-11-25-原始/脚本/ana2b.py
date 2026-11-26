"""同 ana2.py，但只用方块宽 14–16 像素的帧（物品没有和斜穿带子的亮线、图标叠在一起的帧），
并且把越线时刻相差不到 0.3 秒的检测归成一件。用法：ana2b.py 帧.npz [x中心=名字 ...]"""
import sys, time, numpy as np
d = np.load(sys.argv[1]); T = d["t"][:, 0]; F = d["f"]
X0, Y0 = 1180, 600
PITCH = (900 - 741) / 4.0
V = PITCH / 2.0
cols = [(1284, "带32(准入口)"), (1363, "带34(不限)")]
if len(sys.argv) > 2:
    cols = [(int(a.split("=")[0]), a.split("=")[1]) for a in sys.argv[2:]]
YA, YB = 785, 900
def items(frame, xc):
    strip = frame[YA - 15 - Y0:YB + 15 - Y0, xc - X0 - 6:xc - X0 + 7].astype(float)
    v = strip.max(axis=2).mean(axis=1)
    dark = v < 95
    res, i = [], 0
    while i < len(dark):
        if dark[i]:
            j = i
            while j < len(dark) and dark[j]: j += 1
            if 14 <= j - i <= 16:
                y = (i + j - 1) / 2 + YA - 15
                if YA <= y <= YB: res.append(y)
            i = j
        else:
            i += 1
    return res
fmt = lambda c: time.strftime("%H:%M:%S", time.localtime(c)) + ("%.3f" % (c % 1))[1:]
for xc, name in cols:
    det = sorted((T[k] - (y - 741) / V) for k in range(len(T)) for y in items(F[k], xc))
    groups, cur = [], []
    for x in det:
        if cur and x - cur[-1] > 0.3:
            groups.append(cur); cur = []
        cur.append(x)
    if cur: groups.append(cur)
    print(name)
    for g in groups:
        if len(g) < 8: continue
        a = np.array(g)
        print("  越线 %s  帧 %3d  标准差 %.3f 秒  最大减最小 %.3f 秒" % (fmt(np.median(a)), len(a), a.std(), a.max() - a.min()))
