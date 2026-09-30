"""设计推测的独立微型探针（2026-09-30）。

只运行本文件自写的模型，不导入、执行社区代码或项目内核。
上游先判定的次序可来自分流器另接一只堵满断尾元件：断尾组先编号，
分流器与流通带同层，分流器先接通；恒满断尾无成功收发，探针省去其常量状态。
下游先判定则是普通纯链的合法层序。只核主循环，不另实现全布局的登记与 BFS。
待核设计没有定义 advance_once、accept、制造缓存和计时；这里分别列出补齐条件，
以区分“在某种补齐下可以产生”与“设计文字已经唯一推出”。
结果写入同目录的 核对-C-探针结果.json。
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations
from pathlib import Path
import hashlib
import json
import re

目录 = Path(__file__).resolve().parent
资料 = Path('/home/zhuran24/zmd-research-fresh/参考资料/天师府学院及赤石科学院成果公开文档')

@dataclass
class 物品:
    位置: int
    本步动过: int = -1
    来自: str = ''

class 终点:
    def __init__(self):
        self.数量 = 0
        self.来源 = {}
    def 前挪(self, 步):
        pass
    def 收下(self, 货, 步):
        self.数量 += 1
        self.来源[货.来自] = self.来源.get(货.来自, 0) + 1
        return True

class 元件:
    def __init__(self, 名字, 格数=1, 分流=False, 满=False, 移后即送=False, 重试未动=False):
        self.名字, self.格数, self.分流 = 名字, 格数, 分流
        self.内容 = [物品(8*i+7, 来自=名字) for i in range(格数)] if 满 else []
        self.去向 = None
        self.上游 = []
        self.指针 = 0
        self.挪过 = -1
        self.收过 = -1
        self.移后即送 = 移后即送
        self.重试未动 = 重试未动
    def 前挪(self, 步):
        if self.挪过 == 步 and not self.重试未动:
            return
        self.挪过 = 步
        前方 = None
        for 货 in reversed(self.内容):
            if 货.本步动过 != 步:
                新位置 = min(货.位置+1, 8*self.格数-1)
                if 前方 is not None and 新位置//8 == 前方//8:
                    新位置 = 货.位置
                if 新位置 > 货.位置:
                    货.位置, 货.本步动过 = 新位置, 步
            前方 = 货.位置
    def 可送(self, 步):
        return bool(self.内容 and self.内容[-1].位置 == 8*self.格数-1 and
                    (self.移后即送 or self.内容[-1].本步动过 != 步))
    def 收下(self, 货, 步):
        if self.内容 and self.内容[0].位置 < 8:
            return False
        self.内容.insert(0, 物品(0, 步, 货.来自))
        self.收过 = 步
        return True
    def 判定(self, 步):
        self.前挪(步)
        if not self.可送(步):
            return
        下游 = self.去向
        下游.前挪(步)
        if self.分流 or not isinstance(下游, 元件) or len(下游.上游) <= 1:
            if 下游.收下(self.内容[-1], 步):
                self.内容.pop()
                if self.重试未动:
                    self.前挪(步)
            return
        if 下游.收过 == 步:
            return
        for 偏移 in range(1, len(下游.上游)+1):
            编号 = (下游.指针+偏移) % len(下游.上游)
            供货方 = 下游.上游[编号]
            供货方.前挪(步)
            if 供货方.可送(步) and 下游.收下(供货方.内容[-1], 步):
                供货方.内容.pop()
                下游.指针 = 编号
                break
    def 补货(self, 步):
        self.收下(物品(0, 来自=self.名字), 步)
    def 状态(self):
        return (tuple((货.位置, 货.来自) for 货 in self.内容), self.指针)


def 迟滞(长度, 上游先, 移后即送=False, 重试未动=False):
    终 = 终点()
    上 = 元件('分流器', 分流=True, 满=True, 移后即送=移后即送, 重试未动=重试未动)
    带 = 元件('传送带', 长度, 满=True, 移后即送=移后即送, 重试未动=重试未动)
    末 = 元件('末端元件', 满=True, 移后即送=移后即送, 重试未动=重试未动)
    上.去向, 带.去向, 末.去向 = 带, 末, 终
    带.上游, 末.上游 = [上], [带]
    次序 = [末, 上, 带] if 上游先 else [末, 带, 上]
    见过 = {}
    for 步 in range(100000):
        for 件 in 次序:
            件.判定(步)
        上.补货(步)
        状态 = tuple(件.状态() for 件 in [上, 带, 末])
        if 状态 in 见过:
            旧步, 旧数 = 见过[状态]
            周期, 出货 = 步-旧步, 终.数量-旧数
            return {'带长': 长度, '上游先': 上游先, '移后即送': 移后即送,
                    '周期步数': 周期, '周期出货': 出货,
                    '满速比': str(Fraction(8*出货, 周期)),
                    '目标': str(Fraction(8*长度, 8*长度+1) if 上游先 else Fraction(1))}
        见过[状态] = (步, 终.数量)
    raise AssertionError('未找到周期')


def 三上游(次序):
    终 = 终点()
    汇 = 元件('汇流器', 满=True)
    输入 = [元件('左分流器', 分流=True, 满=True),
          元件('传送带', 满=True), 元件('右分流器', 分流=True, 满=True)]
    汇.去向 = 终
    汇.上游 = [输入[1]]  # 按设计，只登记非分流器；不是按出口数判断。
    for 件 in 输入:
        件.去向 = 汇
    for 步 in range(1600):
        汇.判定(步)
        for i in 次序:
            输入[i].判定(步)
        for 件 in 输入:
            件.补货(步)
        if 步 == 799:
            基线 = 终.来源.copy()
    增量 = {件.名字: 终.来源.get(件.名字, 0)-基线.get(件.名字, 0) for 件 in 输入}
    return {'判定序': [输入[i].名字 for i in 次序], '后800步出货': 增量,
            '独占者': max(增量, key=增量.get)}

class 箱:
    def __init__(self):
        self.库存 = 50
        self.下游 = None
    def 前挪(self, 步):
        pass
    def 收下(self, 货, 步):
        if self.库存 == 50:
            return False
        self.库存 += 1
        return True
    def 出货(self, 步):
        self.下游.前挪(步)
        if self.库存 and self.下游.收下(物品(0, 来自='协议储存箱'), 步):
            self.库存 -= 1


def 满箱(数量, 箱序):
    终 = 终点()
    箱组 = [箱() for _ in range(数量)]
    带组 = [元件('传送带'+str(i), 满=True) for i in range(数量+1)]
    带组[0].去向 = 箱组[0]
    for i, 容器 in enumerate(箱组):
        容器.下游 = 带组[i+1]
        带组[i+1].去向 = 箱组[i+1] if i+1 < 数量 else 终
    for 步 in range(数量+10):
        for 件 in reversed(带组):
            件.判定(步)
        if not 带组[0].内容:
            return {'箱数': 数量, '箱判定序': list(箱序), '首件进入首箱步数': 步}
        for i in 箱序:
            箱组[i].出货(步)
    raise AssertionError('首箱未腾位')


def 换料(例, 内部延迟):
    # 明示的补齐：输入槽只容一种物料、容量50，非分流器输入轮询；
    # 每条输入带成功交货后等8步才能交下一件；完成产物等待下次出货回合。
    用量 = 2 if 例 == 3 else 1
    单带 = 例 == 2
    可供 = [1] if 单带 else [1, 1]
    单带下件 = 'a'
    指针 = 1  # 两带接通序取 b、a，第一次从第二条 a 试。
    槽种 = None
    槽量 = 0
    在制 = None
    待出 = None
    开工, 收料, 出货 = [], [], []
    for 步 in range(1, 100):
        # 物流收料（设计第90行）；每步最多收一件（设计第100行）。
        候选 = [0] if 单带 else [(指针+1)%2, 指针]
        for 口 in 候选:
            料 = 单带下件 if 单带 else ['a', 'b'][口]
            if 可供[口] <= 步 and 槽量 < 50 and (槽种 is None or 槽种 == 料):
                槽种, 槽量 = 料, 槽量+1
                可供[口] = 步+8
                指针 = 口
                收料.append([步, 料])
                if 单带:
                    单带下件 = 'b' if 料 == 'a' else 'a'
                break
        # 出货→结束→开始（设计第91-92行），不使用项目规则的结束前置。
        if 待出 is not None:
            出货.append([步, 待出])
            待出 = None
        if 在制 is not None and 在制[1] == 步:
            待出 = 在制[0].upper()
            在制 = None
        if 在制 is None and 待出 is None and 槽量 >= 用量:
            开工.append([步, 槽种.upper()])
            在制 = (槽种, 步+内部延迟)
            槽量 -= 用量
            if 槽量 == 0:
                槽种 = None
    同配方 = [时刻 for 时刻, 品种 in 开工 if 品种 == 'A']
    return {'例': 例, '内部结束延迟步': 内部延迟, '开工前6项': 开工[:6],
            '收料前8项': 收料[:8], '出货前6项': 出货[:6],
            '同配方周期': [b-a for a, b in zip(同配方, 同配方[1:])][:4]}


def 桥轴登记():
    # 直接按设计第70-72行：先更新全部去向，再在唯一下游等于新去向时追加。
    去向 = []
    名单 = {'上桥': [], '下游传送带': []}
    过程 = []
    for 新去向 in ['上桥', '下游传送带']:
        去向.append(新去向)
        唯一下游 = 去向[0] if len(去向) == 1 else None
        if 唯一下游 == 新去向:
            名单[新去向].append('下桥')
        过程.append({'新接通': 新去向, '唯一下游': 唯一下游,
                     '上桥收货名单': list(名单['上桥'])})
    return 过程


def 原文引用清单():
    文本 = (目录/'证据.md').read_text()
    清单 = []
    for 段 in re.split(r'(?m)^### E', 文本)[1:]:
        编号 = int(re.match(r'\d+', 段).group())
        出处行 = re.findall(r'(?m)^- 出处：(.+)$', 段)[0]
        引用 = []
        for 文件, 范围 in re.findall(r'`([^`]+?):([\d,—\-]+)`', 出处行):
            行数 = len((资料/文件).read_text().splitlines())
            for 块 in 范围.replace('—', '-').split(','):
                数 = list(map(int, 块.split('-')))
                assert 1 <= 数[0] <= 数[-1] <= 行数, (编号, 文件, 范围)
            引用.append({'文件': str(资料/文件), '行': 范围})
        清单.append({'编号': 'E'+str(编号), '出处': 引用})
    assert len(清单) == 101
    return 清单


def 附件断言读取():
    # 只解析附件为数据，绝不执行其代码。
    文 = (资料/'附件/test_priority_with_stash.txt').read_text()
    文 = re.sub(r'/\*.*?\*/', '', 文, flags=re.S)
    文 = re.sub(r'//[^\n]*', '', 文)
    数据 = json.loads(文)
    return [{'放置序': 键,
             '分流器下游': ''.join('1' if x else '0' for x in 值['assertions'][0]['value'][0]),
             '汇流器下游': ''.join('1' if x else '0' for x in 值['assertions'][1]['value'][0])}
            for 键, 值 in 数据.items()]


def 主程序():
    结果 = {
        '核对对象哈希': {名: hashlib.sha256((目录/名).read_bytes()).hexdigest()
                      for 名 in ['设计-C.md', '证据.md']},
        '迟滞_按设计每元件每步只前挪一次_另补物品去重': [迟滞(n, 顺) for n in range(1, 7) for 顺 in [True, False]],
        '对照_转移后允许未动的物品再次尝试前挪': [迟滞(n, 顺, 重试未动=True) for n in range(1, 7) for 顺 in [True, False]],
        '迟滞_只按元件去重而不禁止移后转移': [迟滞(n, True, True) for n in range(1, 4)],
        '换料_内部七步延迟': [换料(i, 7) for i in [1, 2, 3]],
        '换料_照标称八步延迟': [换料(i, 8) for i in [1, 2, 3]],
        '满箱_真实运输连接': [满箱(k, 序) for k in range(1, 7)
                                for 序 in ([tuple(range(k)), tuple(reversed(range(k)))])],
        '三上游': [三上游(序) for 序 in permutations(range(3))],
        '桥轴由单去向变双去向_原登记代码': 桥轴登记(),
        '证据出处范围检查': 原文引用清单(),
        '协议储存箱环_只读附件的24项断言': 附件断言读取(),
        '离线批时长估算秒': 3600/11.8,
        '仅50件积存且初始为零的条件估算_件每小时': [50/12, 50/8],
        '批次补算305秒所需核心运算秒_假设1毫秒每游戏秒': (3600/11.8)*0.001,
    }
    for 项 in 结果['对照_转移后允许未动的物品再次尝试前挪']:
        assert 项['满速比'] == 项['目标'], 项
    原模型 = 结果['迟滞_按设计每元件每步只前挪一次_另补物品去重']
    assert all(项['满速比'] == '8/9' for 项 in 原模型 if 项['带长'] >= 2)
    assert sum(项['满速比'] != 项['目标'] for 项 in 原模型) == 10
    assert [项['同配方周期'][0] for 项 in 结果['换料_内部七步延迟']] == [16, 16, 18]
    assert all(项['首件进入首箱步数'] == 项['箱数'] for 项 in 结果['满箱_真实运输连接'])
    assert all(项['独占者'] == 项['判定序'][0] and sum(项['后800步出货'].values()) == 100
               for 项 in 结果['三上游'])
    目的 = 目录/'核对-C-探针结果.json'
    目的.write_text(json.dumps(结果, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({键: 值 for 键, 值 in 结果.items()
                      if 键 not in ['证据出处范围检查', '协议储存箱环_只读附件的24项断言']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    主程序()
