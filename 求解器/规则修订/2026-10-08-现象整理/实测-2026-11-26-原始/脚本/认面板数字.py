"""把连续截的「累计通过数量」那一块逐帧归成几种样子，打出每一种从哪一刻到哪一刻。
用法：认面板数字.py 样子库.npz 帧1.npz [帧2.npz …]
样子库.npz 没有就新建：每碰到一种和库里都不像的样子就加进去、存一张图（同名的 -编号.png），以后各次都用同一个库，编号的意思不变。
帧.npz 是 实测-2026-11-25-原始/脚本/grabseq.py 存的。"""
import os, sys, time
import numpy as np
from PIL import Image

lib_path = sys.argv[1]
THR = 9.0
reps = list(np.load(lib_path)["reps"]) if os.path.exists(lib_path) else []


def hms(x):
    return time.strftime("%M:%S", time.localtime(x)) + ("%.3f" % (x % 1))[1:]


for p in sys.argv[2:]:
    d = np.load(p)
    t, f = d["t"][:, 0], d["f"]
    seq = []
    for fr in f:
        a = fr.astype(np.int16)
        ds = [float(np.abs(a - r.astype(np.int16)).mean()) for r in reps]
        if ds and min(ds) < THR:
            seq.append(int(np.argmin(ds)))
        else:
            reps.append(fr.copy())
            Image.fromarray(fr[:, :, ::-1]).save(lib_path[:-4] + f"-{len(reps) - 1}.png")
            seq.append(len(reps) - 1)
    runs, s = [], 0
    for i in range(1, len(seq) + 1):
        if i == len(seq) or seq[i] != seq[s]:
            runs.append((seq[s], t[s], t[i - 1], i - s))
            s = i
    print(os.path.basename(p), "｜", " ".join(f"[{k}]{hms(a)}–{hms(b)[3:]}({n})" for k, a, b, n in runs if n >= 2))
np.savez_compressed(lib_path, reps=np.array(reps))
