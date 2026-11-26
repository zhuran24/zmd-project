"""连续截游戏画面的几块，只存变了的帧，截完打出每一块各次变的时刻。
用法：[THR=5] 抓几块.py 秒数 输出.npz x1 y1 x2 y2 [x1 y1 x2 y2 …]
每一块：和上一张存下的帧比，平均像素差超过 THR（环境变量，默认 5）才存一张新的（也就算变了一次）。块小、字小的时候把 THR 调低。
npz 里：t（每帧的时刻、截这一帧用了多久）、k0、k1…（每帧对着这一块存下的第几张）、f0、f1…（这一块存下的帧）。
打出的时刻是「头一张已经是新样子的帧」的时刻；末尾一行是帧数、每帧平均隔多久、最长的一次隔了多久（卡顿看这个）。"""
import os, sys, time
sys.path.insert(0, os.path.expanduser("~/mytools/endfield-mcp"))   # 操控工具的目录，用它的 efctl.grab 截图
import numpy as np
import efctl as c

THR = float(os.environ.get("THR", "5"))
dur = float(sys.argv[1]); out = sys.argv[2]
v = list(map(int, sys.argv[3:]))
boxes = [v[i:i + 4] for i in range(0, len(v), 4)]
ts = []
keep = [[] for _ in boxes]      # 存下的帧
idx = [[] for _ in boxes]       # 每帧对着第几张
chg = [[] for _ in boxes]       # 变的时刻
end = time.time() + dur
while time.time() < end:
    t1 = time.time()
    try:
        a = c.grab(wait=3)
    except Exception:
        continue
    t2 = time.time()
    tm = (t1 + t2) / 2
    ts.append((tm, t2 - t1))
    for n, (x1, y1, x2, y2) in enumerate(boxes):
        fr = a[y1:y2, x1:x2]
        if not keep[n] or float(np.abs(fr.astype(np.int16) - keep[n][-1].astype(np.int16)).mean()) > THR:
            if keep[n]:
                chg[n].append(tm)
            keep[n].append(fr.copy())
        idx[n].append(len(keep[n]) - 1)
d = {"t": np.array(ts)}
for n in range(len(boxes)):
    d[f"k{n}"] = np.array(idx[n]); d[f"f{n}"] = np.array(keep[n])
np.savez_compressed(out, **d)


def hms(x):
    return time.strftime("%M:%S", time.localtime(x)) + ("%.3f" % (x % 1))[1:]


for n in range(len(boxes)):
    print(f"块{n}", " ".join(hms(x) for x in chg[n]))
gaps = np.diff(np.array(ts)[:, 0]) if len(ts) > 1 else np.array([0.0])
print(len(ts), "帧", "平均隔", round(float(gaps.mean()), 3), "最长隔", round(float(gaps.max()), 3), "秒")
