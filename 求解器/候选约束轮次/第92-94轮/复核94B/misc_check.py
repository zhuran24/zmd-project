#!/usr/bin/env python3
"""复核94B 抽查用小算术：增机面积界 1089、无桥 1036/1035、角桩与 921 偶数性。"""
import json
def legal(A, hi=68):
    return [(w, A // w) for w in range(6, hi + 1) if A % w == 0 and 6 <= A // w <= hi and w <= A // w]
out = {}
K68 = 4900 - (3291 + 9 + 25) - 81 - 138           # 粉碎机 69、采种机 17
out["增机 T+F+A+4P"] = K68
out["增机 4A+14P<="] = 4 * K68 - 921
out["增机 P=10 A<="] = (4 * K68 - 921 - 140) / 4
out["1090 合法尺寸"] = legal(1090)
out["1089 合法尺寸"] = legal(1089)
out["无桥无箱面积上界"] = 4900 - 3291 - 81 - 138 - 40 - 314
out["无桥有箱面积上界"] = 4900 - 3291 - 81 - 138 - 40 - 306 - 9
out["T>=209(q 放运输单位)"] = -(-(829 + 4) // 4)
out["4(T+F)+2J 为偶数，>=921 即 >=922"] = True
json.dump(out, open("misc_check.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
