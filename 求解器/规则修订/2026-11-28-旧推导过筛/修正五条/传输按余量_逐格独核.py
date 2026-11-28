from fractions import Fraction

# 归纳检查在已经核过的前缀之后追加一格。不同物品的仓库余量互不占用。
checks = 0
for slots_before in range(6):
    for previous in range(50 * slots_before + 1):
        for free in (*range(302), 80000):
            previous_sent = min(previous, free)
            for added in range(51):
                sent = previous_sent + min(added, free - previous_sent)
                total = previous + added
                assert sent == min(total, free)
                assert (sent == 0) == (total == 0 or free == 0)
                checks += 1

battery, capsule = Fraction(18,30), Fraction(33,60)
blue = battery * 10 * 2 + capsule * 10 * 2 * 2
source = battery * 15 * 2
limit = 2 * (70 // 3) + 6
assert blue + source == limit
print(checks, blue, source, limit)
