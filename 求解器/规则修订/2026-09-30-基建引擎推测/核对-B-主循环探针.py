#!/usr/bin/env python3
"""设计-B 主循环核对；独立编写，仅使用 Python 标准库。

不是游戏模拟器，不导入、运行项目内核或任何社区模拟器。
只考察设计-B.md:90-109 的阶段、当前元件前挪和单遍判定。
必要补足均显式记在结果中，不把补足当成设计原文：
* 运输单位容量：n 格带最多 n 件；间距至少 8 刻度。
* 入带时离出口 8n 刻度；出生步不前挪；达到 0 可送。
* 分流器/汇流器用同样的一格滞留模型，避免按裸伪代码瞬间转移。
* 未写出的普通收发用容量检查；不增补下游使动、不补失败重试。
* 为隔离阶段问题，位置逐件展开；不实现原文“只改第一个间距”。
* 换料的存货格容量 50、单格只放一种物品，配方时长 8 步。

文件路径和出处哈希用于定位核对版本；不会修改任何输入资料。
"""

from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import permutations
from pathlib import Path
import json

ROOT = Path('/home/zhuran24/zmd-research-fresh')
OUT = ROOT / '求解器/规则修订/2026-09-30-基建引擎推测'


class 带段:
    def __init__(self, 长度=1):
        self.长度 = 长度
        self.物品 = []  # [离出口的刻度, 收下步号, 物品名]

    def 收得下(self):
        return len(self.物品) < self.长度 and (
            not self.物品 or self.物品[-1][0] <= 8 * self.长度 - 8
        )

    def 收下(self, 步, 名='源矿'):
        assert self.收得下()
        self.物品.append([8 * self.长度, 步, 名])

    def 前挪(self, 步):
        for i, 货 in enumerate(self.物品):
            if 货[1] == 步:
                continue
            if 货[0] > 0 and (i == 0 or 货[0] - 1 >= self.物品[i - 1][0] + 8):
                货[0] -= 1

    def 可送(self):
        return bool(self.物品) and self.物品[0][0] == 0

    def 送出(self):
        assert self.可送()
        return self.物品.pop(0)[2]

    def 核查(self):
        assert len(self.物品) <= self.长度
        assert all(0 <= p[0] <= 8 * self.长度 for p in self.物品)
        assert all(b[0] - a[0] >= 8 for a, b in zip(self.物品, self.物品[1:]))


def 迟滞(长度, 顺序):
    # 另一支已堵死，用固定的 S 与 B 同层次序隔离主循环。
    # T 是 B 后仍有的物流元件；终点永远收得下。
    图 = {'S': 带段(1), 'B': 带段(长度), 'T': 带段(1)}
    下游 = {'S': 'B', 'B': 'T', 'T': None}
    排序 = ('T', 'S', 'B') if 顺序 == '上游先算' else ('T', 'B', 'S')
    输出 = []
    总步数, 舍前 = 40000, 10000
    for 步 in range(总步数):
        for 名 in 排序:
            当前 = 图[名]
            当前.前挪(步)
            if 当前.可送():
                d = 下游[名]
                if d is None:
                    当前.送出()
                    输出.append(步)
                elif 图[d].收得下():
                    图[d].收下(步, 当前.送出())
        # 阶段4的无限库存源，仅填 S；不参与元件阶段。
        if 图['S'].收得下():
            图['S'].收下(步)
        for 段 in 图.values():
            段.核查()
    稳态 = [s for s in 输出 if s >= 舍前]
    间隔 = Counter(b - a for a, b in zip(稳态, 稳态[1:]))
    assert len(间隔) == 1
    实际 = Fraction(8, next(iter(间隔)))
    预期 = Fraction(8 * 长度, 8 * 长度 + 1) if 顺序 == '上游先算' else Fraction(1)
    return {
        'n': 长度, '次序': 顺序, '稳态间隔': dict(间隔),
        'R': str(实际), '社区目标R': str(预期), '一致': 实际 == 预期,
        '总步数': 总步数, '舍前步数': 舍前,
    }


def 换料(案例):
    # 案例1：两个满速入口分别供 a、b；共用一个存货物品格。
    # 案例2：一个满速混带交替 a、b。
    # 案例3：两个满速入口分别供 a、b，配方各消耗两件；另一原料足量。
    用量 = 2 if 案例 == 3 else 1
    下一可送 = {'a': 1, 'b': 1}
    混带下一步, 混带物品 = 1, 'a'
    存货种类, 存货件数 = None, 0
    进行中 = None
    成品 = []
    下游下次可收 = 1
    记录 = {'收料': [], '开工': [], '完成': [], '上带': []}
    上次收料 = 'b'  # 等价于以 b、a 接通、初次从第二条 a 开始。
    for 步 in range(1, 121):
        # 阶段1：生产完成，整批入取货物品格；本例从不满格。
        if 进行中 and 进行中[1] == 步:
            名 = 进行中[0]
            成品.append(名.upper())
            记录['完成'].append([步, 名.upper()])
            进行中 = None
        # 阶段2：物流入口单遍。失败的物品保留，下步再试。
        试送 = ([混带物品] if 案例 == 2 else
                (['a', 'b'] if 上次收料 == 'b' else ['b', 'a']))
        for 名 in 试送:
            到时 = 混带下一步 if 案例 == 2 else 下一可送[名]
            if 步 >= 到时 and 存货件数 < 50 and 存货种类 in (None, 名):
                存货种类, 存货件数 = 名, 存货件数 + 1
                记录['收料'].append([步, 名])
                if 案例 == 2:
                    混带下一步 = 步 + 8
                    混带物品 = 'b' if 名 == 'a' else 'a'
                else:
                    下一可送[名] = 步 + 8
                    上次收料 = 名
                break  # 集中收货按下标只收一件。
        # 阶段3：普通制造单位送货。
        if 成品 and 步 >= 下游下次可收:
            记录['上带'].append([步, 成品.pop(0)])
            下游下次可收 = 步 + 8
        # 阶段5：开始能开始的制造。
        if 进行中 is None and not 成品 and 存货件数 >= 用量:
            名 = 存货种类
            存货件数 -= 用量
            if 存货件数 == 0:
                存货种类 = None
            进行中 = (名, 步 + 8)
            记录['开工'].append([步, 名.upper()])
    A = [s for s, 名 in 记录['开工'] if 名 == 'A']
    周期 = A[1] - A[0]
    目标 = {1: 16, 2: 16, 3: 18}[案例]
    assert all(b - a == 目标 for a, b in zip(A, A[1:]))
    assert all(名 == ('A' if i % 2 == 0 else 'B')
               for i, (_, 名) in enumerate(记录['开工']))
    return {'案例': 案例, '周期': 周期, '前六次事件': {k: v[:6] for k, v in 记录.items()}}


def 满箱(箱数, 箱序):
    # 合法串联：上游带 -> 箱1 -> 一格带 -> 箱2 -> ... -> 出带 -> 终点。
    # 不采用非运输单位互相直连。无线传输关闭，箱初始300件。
    带 = [带段(1) for _ in range(箱数 + 1)]
    for 段 in 带:
        段.物品 = [[0, -1, '源矿']]
    库存 = [300] * 箱数
    源第一次收 = None
    for 步 in range(箱数 + 12):
        # 阶段2：从下游往上游扫描带。每根带只尝试一次。
        for i in reversed(range(箱数 + 1)):
            段 = 带[i]
            段.前挪(步)
            if not 段.可送():
                continue
            if i == 箱数:
                段.送出()
            elif 库存[i] < 300:
                库存[i] += 1
                段.送出()
                if i == 0 and 源第一次收 is None:
                    源第一次收 = 步
        # 阶段3：箱的次序全枚举。
        for i in 箱序:
            if 库存[i] and 带[i + 1].收得下():
                库存[i] -= 1
                带[i + 1].收下(步)
        assert all(0 <= n <= 300 for n in 库存)
        for 段 in 带:
            段.核查()
    assert 源第一次收 == 箱数
    return 源第一次收


def 三上游(排序):
    源 = {k: 带段(1) for k in ('左分流器', '传送带', '右分流器')}
    for 名, 段 in 源.items():
        段.物品 = [[0, -1, 名]]
    汇 = 带段(1)
    输出 = Counter()
    for 步 in range(24000):
        # 汇流器先于三上游。仅传送带可参加集中收货，本例只有一个候选。
        汇.前挪(步)
        if 汇.可送():
            名 = 汇.送出()
            if 步 >= 4000:
                输出[名] += 1
        for 名 in 排序:
            段 = 源[名]
            段.前挪(步)
            if 段.可送() and 汇.收得下():
                汇.收下(步, 段.送出())
        # 三个独立无限库存源在阶段4送货。
        for 名, 段 in 源.items():
            if 段.收得下():
                段.收下(步, 名)
    assert set(输出) == {排序[0]}
    assert sum(输出.values()) == 2500
    return {'判定序': list(排序), '输出计数': dict(输出), 'R': '1'}


def 准入口窗口(步长秒, 限额):
    # 字面阶段5才清零；阶段2只按当前计数检查，没增补按时钟提前清零。
    窗口起点, 件数 = None, 0
    放行 = []
    for 步 in range(2000):
        秒 = 步 * 步长秒
        if 件数 < 限额:
            if 窗口起点 is None:
                窗口起点 = 秒
            件数 += 1
            放行.append(秒)
        if 窗口起点 is not None and 秒 - 窗口起点 >= 10:
            窗口起点, 件数 = None, 0
    起点 = 放行[::限额]
    周期 = 起点[1] - 起点[0]
    return {'步长秒': 步长秒, '限额': 限额, '满输入窗口周期秒': 周期,
            '平均每分钟放行': 60 * 限额 / 周期,
            '目标每分钟': 6 * 限额, '前两个窗口': 放行[:2 * 限额]}


def 附件断言读取():
    # 只读文本数据，不执行附件代码；这里只提取24个键与两条期望数组。
    import re
    p = ROOT / '参考资料/天师府学院及赤石科学院成果公开文档/附件/test_priority_with_stash.txt'
    rows = []
    ls = p.read_text().splitlines()
    for i, line in enumerate(ls):
        m = re.match(r'\s*"([scl\-,r ]+)": \{', line)
        if not m:
            continue
        块 = ls[i:i + 46]
        vals = []
        for j, v in enumerate(块):
            a = re.search(r'"value": \[\[([a-z, ]+)\]\]', v)
            if a:
                vals.append({'行': i + j + 1, '序列': ''.join('1' if x.strip() == 'true' else '0'
                                                                     for x in a[1].split(','))})
        assert len(vals) == 2
        rows.append({'放置序': m[1], '键行': i + 1, '分流器': vals[0], '汇流器': vals[1]})
    assert len(rows) == 24
    assert all(r['汇流器']['序列'] == '011111' for r in rows)
    return rows


def main():
    迟滞结果 = [迟滞(n, 序) for n in range(1, 7) for 序 in ('上游先算', '下游先算')]
    箱结果 = []
    for n in range(1, 7):
        次数 = 0
        for 序 in permutations(range(n)):
            满箱(n, 序)
            次数 += 1
        箱结果.append({'箱数': n, '已枚举箱输出次序': 次数, '源第一次可输入步': n,
                        '相对末端放行晚步数': n})
    根文件 = [OUT / '设计-B.md', OUT / '证据.md', Path(__file__)]
    result = {
        '口径': '独立最小补足探针，不是设计源码、游戏实测或sim2运行；迟滞结果只检验不增补下游使动的写法。',
        '输入SHA256': {str(p): sha256(p.read_bytes()).hexdigest() for p in 根文件},
        '必要补足': __doc__,
        '迟滞': 迟滞结果,
        '换料': [换料(i) for i in (1, 2, 3)],
        '满箱串联': 箱结果,
        '三上游': [三上游(s) for s in permutations(('左分流器', '传送带', '右分流器'))],
        '准入口': [准入口窗口(dt, q) for dt in (0.25, 2) for q in (1, 5)],
        '两秒粗步_若到期时直接检查': {'10秒窗口粗步数': 5, '取整误差秒': 0,
                                    '说明': '10是2的整数倍，第一件与起止均在粗步边界，不能推出平均加1秒。'},
        '间距更新反例': {'前挪前出口距离': [0, 8, 24], '下游堵住': True,
                         '每件最多前挪1刻度_间距至少8_前挪后': [0, 8, 23],
                         '前挪前间距': [8, 16], '前挪后间距': [8, 15],
                         '结论': '第二个间距必须更新；只改带头和第一个间距不足以表达此状态。'},
        '离线积料估算': {'假设': '起始取货格空、持续30/min生产，唯一瓶颈降速造成50件积料，忽略其他缓存。',
                         '8小时到满_降速比例': 50 / (30 * 8 * 60),
                         '12小时到满_降速比例': 50 / (30 * 12 * 60),
                         '降速9%到满分钟': 50 / (30 * 0.09),
                         '降速17%到满分钟': 50 / (30 * 0.17)},
        'E99原附件24条_仅读取断言': 附件断言读取(),
    }
    p = OUT / '核对-B-主循环结果.json'
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('迟滞', '换料', '满箱串联', '三上游', '准入口', '离线积料估算')},
                     ensure_ascii=False, indent=2))
    print('结果文件：' + str(p))


if __name__ == '__main__':
    main()
