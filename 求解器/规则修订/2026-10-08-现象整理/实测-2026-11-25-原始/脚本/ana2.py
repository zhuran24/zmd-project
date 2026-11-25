"""从 grabseq 的帧里逐件量：每件物品的中心越过格 18 中心线（y=741）的时刻 c（按匀速外推），和速度。
用法：ana2.py 帧.npz [x中心=名字 ...]  默认两条带：1284=带32(准入口) 1363=带34(不限)"""
import sys, numpy as np
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
            if 14 <= j - i <= 26:
                y = (i + j - 1) / 2 + YA - 15
                if YA <= y <= YB: res.append(y)
            i = j
        else:
            i += 1
    return res
import time
print("帧数", len(T), "从", time.strftime("%H:%M:%S", time.localtime(T[0])) + ("%.2f" % (T[0] % 1))[1:], "到", time.strftime("%H:%M:%S", time.localtime(T[-1])), "帧间隔中位 %.3f" % np.median(np.diff(T)))
allitems = {}
for xc, name in cols:
    det = []
    for k in range(len(T)):
        for y in items(F[k], xc):
            det.append((T[k] - (y - 741) / V, T[k], y))
    det.sort()
    groups, cur = [], []
    for x in det:
        if cur and x[0] - cur[-1][0] > 0.6:
            groups.append(cur); cur = []
        cur.append(x)
    if cur: groups.append(cur)
    out = []
    for g in groups:
        a = np.array(g)
        if len(a) < 12: continue
        sl = np.polyfit(a[:, 1] - a[0, 1], a[:, 2], 1)[0] if len(a) > 20 else float("nan")
        out.append((np.median(a[:, 0]), a[:, 0].std(), len(a), sl))
    allitems[name] = out
ref = None
for name, out in allitems.items():
    if "不限" in name and out: ref = out[0][0]
if ref is None:
    ref = min(o[0][0] for o in allitems.values() if o)
for name, out in allitems.items():
    print(name)
    for c, sd, n, sl in out:
        print("  越线 %s%s  相对参照 %+7.2f 步 (对8取余 %.2f)  散 %.2f步  帧 %d  速度 %.1f 像素/秒" % (
            time.strftime("%H:%M:%S", time.localtime(c)), ("%.3f" % (c % 1))[1:], (c - ref) / 0.25, ((c - ref) / 0.25) % 8, sd / 0.25, n, sl))
print("参照（第一件不限带）越线时刻对 2 秒取余 = %.3f 秒 = %.2f 步；对 1 秒取余 %.3f" % (ref % 2, (ref % 2) / 0.25, ref % 1))
