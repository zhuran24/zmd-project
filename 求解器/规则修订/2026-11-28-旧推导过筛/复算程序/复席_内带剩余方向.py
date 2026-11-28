# 各带缺格、跨度均独立取值，是对真实布局的放宽。
fewest = 23
for gap in range(0, 70, 3):
    occupied = [r for r in range(70) if r != gap]
    sources = set(occupied[1::3])
    regular = {r for r in sources if r-3 in sources and r+3 in sources}
    for b in range(2, 65):
        for h in range(6, 10):
            if b+h <= 70:
                eligible = regular - set(range(b, b+h))
                fewest = min(fewest, len(eligible))
print("剔除任意至多九行跨度后普通左源格最少剩", fewest)
