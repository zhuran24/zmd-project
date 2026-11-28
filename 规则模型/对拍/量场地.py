"""量预构建 lake exe 对拍的一份成功输出，含进程启动、读取和输出。"""
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import time

from 生成场地 import SEED, document, example, piece

ROOT = Path(__file__).resolve().parents[1]


def layout(n):
    ps = []
    for y in range(70):
        for x in range(1, 61):
            ps.append(piece(len(ps), x, y, "传送带", "左", "右"))
        if y % 4 == 0:
            ps.append(piece(len(ps), 61, y, "制造", "精炼炉", "右"))
        if len(ps) >= n:
            break
    ps = ps[:n]
    random.Random(SEED).shuffle(ps)
    return ps


if __name__ == "__main__":
    subprocess.run(["lake", "build", "对拍"], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "输入.json"
        for n in (300, 1000, 2000):
            path.write_text(document([example(layout(n))]))
            times = []
            for _ in range(3):
                start = time.perf_counter()
                result = subprocess.check_output(["lake", "exe", "对拍", path], cwd=ROOT)
                times.append(time.perf_counter() - start)
                history = json.loads(result)["历史"]
                assert sum(e[0] == "建成" for e in history) == n
            print(f"{n} 件，{len(history)} 个事件，" + " / ".join(f"{t:.3f}" for t in times)
                  + f" 秒，中位数 {statistics.median(times):.3f} 秒", flush=True)
