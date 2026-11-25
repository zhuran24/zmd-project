"""连续截游戏画面的一块，存带时刻的帧。用法：grabseq.py 秒数 输出.npz x1 y1 x2 y2"""
import os, sys, time
sys.path.insert(0, os.path.expanduser("~/mytools/endfield-mcp"))   # 操控工具的目录，用它的 efctl.grab 截图
import numpy as np
import efctl as c
dur = float(sys.argv[1]); out = sys.argv[2]
x1, y1, x2, y2 = map(int, sys.argv[3:7])
ts, fr = [], []
end = time.time() + dur
while time.time() < end:
    t1 = time.time()
    try:
        a = c.grab(wait=3)
    except Exception as e:
        continue
    t2 = time.time()
    ts.append(((t1 + t2) / 2, t2 - t1))
    fr.append(a[y1:y2, x1:x2].copy())
np.savez_compressed(out, t=np.array(ts), f=np.array(fr))
print(len(fr), "帧", "平均每帧", round(dur / max(1, len(fr)), 3), "秒")
