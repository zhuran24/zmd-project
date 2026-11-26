"""看连续截的一块画面是在哪些时刻变的。用法：看面板帧.py 帧.npz [输出图的前缀] [阈值，默认 6]
帧.npz 是 实测-2026-11-25-原始/脚本/grabseq.py 存的（t：每帧的时刻和截这一帧用了多久；f：裁下来的那一块）。
相邻两帧的平均像素差超过阈值就算变了一次，打出变之前最后一帧、变之后头一帧的时刻；给了前缀就把每一段的头一帧存成图，好拿去认字。"""
import sys, time
import numpy as np

d = np.load(sys.argv[1])
t, f = d["t"], d["f"].astype(np.int16)
prefix = sys.argv[2] if len(sys.argv) > 2 else None
thr = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0


def hms(x):
    return time.strftime("%H:%M:%S", time.localtime(x)) + ("%.3f" % (x % 1))[1:]


print(len(f), "帧，", hms(t[0, 0]), "到", hms(t[-1, 0]), "，每帧平均隔", round(float(np.diff(t[:, 0]).mean()), 3), "秒，截一帧平均", round(float(t[:, 1].mean()), 3), "秒")
seg = [0]
for i in range(1, len(f)):
    diff = float(np.abs(f[i] - f[seg[-1]]).mean())      # 和这一段头一帧比，慢慢变的也认得出
    if diff > thr:
        print("第", len(seg), "次变：", hms(t[i - 1, 0]), "还是旧的，", hms(t[i, 0]), "已经是新的（差", round(diff, 1), "）")
        seg.append(i)
if prefix:
    from PIL import Image
    for k, i in enumerate(seg):
        Image.fromarray(d["f"][i][:, :, ::-1]).save(f"{prefix}-{k}.png")
    print("各段头一帧存成", prefix + "-0.png 起", len(seg), "张")
