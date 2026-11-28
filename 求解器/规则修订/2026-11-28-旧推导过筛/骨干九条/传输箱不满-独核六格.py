from heapq import heappush, heappop

def minimum_fills(k):
    empty = (0,) * 6
    cost = {empty: 0}
    queue = [(0, empty)]
    while queue:
        n, slots = heappop(queue)
        if n != cost[slots]:
            continue
        if 0 not in slots and len(set(slots)) < k:
            return n, slots
        edges = []
        for i, color in enumerate(slots):
            if color:
                edges.append((0, i, 0))
                break
        for incoming in range(1, k + 1):
            for i, color in enumerate(slots):
                if color == incoming:
                    break
                if not color:
                    edges.append((1, i, incoming))
                    break
        for w, i, color in edges:
            nxt = slots[:i] + (color,) + slots[i+1:]
            if n+w < cost.get(nxt, float("inf")):
                cost[nxt] = n+w
                heappush(queue, (n+w, nxt))

# Single-port scheduling on j consecutive movement phases, last opportunity
# is either unused or used with its previous seven opportunities excluded.
dp = [0]
for j in range(1, 41):
    dp.append(max(dp[j-1], 1+dp[max(0, j-8)]))
assert all(x == (j+7)//8 for j, x in enumerate(dp))
print("40 phases:", [ports * dp[40] for ports in (1,2,3)])
print("capacity:",6*50)
for k in (3,4):
    print(k, minimum_fills(k))
