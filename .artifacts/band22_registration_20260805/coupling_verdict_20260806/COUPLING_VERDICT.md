# band22 R2 官方 routing 秒级 INFEASIBLE：条款级定位判决书

fork: routing-coupling-hunt，2026-08-06。全部实验脚本与输出在本目录（fork_geom.py /
fork_verify.py / fork_v3tele.py / fork_occ.json；上游 probe_shrink2.core.json）。
只读取证，未改任何 tracked 文件。

## 判决：**(b) 模型比 canonical / 游戏语义更严**——严在「终端 front 格对外商品完全排他」

### 条款级机制链（四条约束合谋，src/models/routing_subproblem.py）

1. **`_add_port_adherence` (:1297-1330)**：每个终端 front 格必须恰好选一个含
   「机身侧流向」的状态（out 口：flow_in 来自机身侧；in 口：flow_out 指向机身侧），
   `sum(vars_for_port) == 1`。
2. **`_add_successor_constraints` (:1236-1252) / `_add_predecessor_constraints`
   (:1274-1291)**：对**任何其他商品**，凡状态含指向机身格的流向即被硬置 0
   （机身格不在该商品 active set；port-front 豁免按 (cell, dir, commodity) 键控，
   只豁免口主商品——:1233/:1244/:1271/:1282）。
3. **`_add_capacity_constraints` (:1119-1122)**：`AddAtMostOne(phys per cell-layer)`
   ——同格共乘必须**同一个物理形状**；而 use 变量是**形状原子**的（一个商品用一个
   形状=流经该形状全部进出边，:1054-1072）。1+2+3 合并：外商品在终端 front 格
   的一切 use 变量恒 0 ⇒ **front 格=外商品的实心障碍**。
4. **`_add_bridge_constraints` (:1124-1143)**：高架只能跨「直线 belt」地面格；
   1 宽走廊里的 front 形状必然含机身侧流向（转弯/分流/汇流，绝非走廊轴直线）
   ⇒ **桥也跨不过去**。

### 5 口极小核的几何证明（fork_geom.py 实测）

五个 front 全部位于 1 宽走廊（南北皆机身、仅东西自由）、全部非直线形（不可跨）。
BFS：把 source_powder 的 3 个 front 从通行图中挖掉后，buckwheat (64,26)→(50,40)
**断连**；任意只挖 2 个都仍连通——与 delta-shrink「五口一个都删不得」精确互锁
（fork_verify.py：V2 两 front 变体 60s 非 INFEASIBLE，吻合预测）。CP-SAT 0.3s 出
INFEASIBLE 是强置零传播后的小割集矛盾，非搜索耗尽。

### 为什么判 (b) 而非 (a)（见证依赖假语义）

- **canonical 现行冻结版**（c3666d78）`semantics.mixed_commodity_flow` 明文：
  "A single physical belt / routing component may be SHARED by multiple
  commodities. Commodity mixing on one component is allowed." 无终端 front 例外。
- **游戏实测**（owner 紫源系列+指针实验）：分流器不筛货、失败侧回退、机器口只吸
  匹配货——即「混流经过机器口、靠消费选择性分拣」是游戏真机制。
- **见证的真实形态**（witness route_components 实录）：
  - (50,40) splitter in:E out:[N,W]——buckwheat 出 N 进机、W 向继续混行；
  - (64,26) merger in:[S,W] out:E——机器输出从 S 注入、与走廊 W 向流汇成混行 E 流；
  - (13,40)/(55,40) 同风格。
  这些形状**都在模型形态表里**；模型拒绝的不是形状，而是「同一形状上按商品选边」
  ——use 变量形状原子性表达不了「buckwheat 走 N、source_powder 走 W」。
- 结论：见证是 canonical 合法+游戏合法的路网；官方模型的可行域是其**真子集**。

### 影响面（超出 band22）

- R2/R1/R3 全家依赖终端混行风格（异商品共享 front 格 70/75/91 个）⇒ 官方门
  在现行模型下**永远**不能注册它们，与预算无关。
- **最优性主张的作用域收窄**：certified lex-最优性/负结果（如 residual-band UNSAT）
  是「模型语义下」的结论；对 canonical/游戏语义，因可行域更大，上界类结论仍安全、
  **最优性与不可行性类结论带作用域条件**。正向可行性证书不受影响。

### 附带发现：单商品单路径 180s TIMEOUT 的原因（任务 5）

CP 模型只有**局部**支撑约束（假环流可满足局部约束），全局连通靠 `solve()`
(:1860-1990) 的「复验-拒绝」循环兜底：incumbent ~0.4s 一个、全是假环流，60s 内
**134 个 incumbent / 133 次拒绝 / 58 条割**（fork_v3tele.py 遥测）。1222 格开放域
环流空间巨大，割收敛慢——是护栏循环磨，不是模型全局强制。含义：即使补上混流
表达力，routing 在此规模的可行性求解还需性能工作（环流消除约束或换编码）。

### 修复方向（供主线/owner 决策，未实施）

- **模型侧**（撬动大、代价大）：use 变量按「边」而非「形状」建（商品×格×进边/出边），
  形状由聚合边用量导出——重塑 routing 子问题（sealed 面，freeze-ritual+soundness 审查）；
- **规则侧**（若 owner 游戏实测推翻「front 格上放分流器混行」的可行性）：canonical
  增终端 front 排他条款，模型现状即忠实——但现有游戏证据方向相反；
- **过渡**：④路对三见证的登记结论按「模型语义下不可注册、canonical 语义下未裁决」
  双口径记账。

---

## 主线归档批注（2026-08-06，非 fork 原文）

1. **抽验**：机制链条款 2 的豁免键控已主线亲手核实（`_add_successor_constraints`
   :1233 / `_add_predecessor_constraints` :1271——sink/source_port_fronts 查表键含
   commodity，外商品机身侧流向硬置零属实）。条款 1/3/4 与几何/变体证据此前主线
   已独立走过一遍（probe_* 系列，本目录）。
2. **方向性订正（承重）**：原文「上界类结论仍安全」**有误**，与其后半句自相矛盾。
   正确方向：模型可行域 ⊂ canonical 可行域 ⇒ **可行性见证/下界类结论安全**
   （模型合法⇒canonical 合法）；**上界/不可行性/最优性类结论带作用域条件**
   （canonical 更大空间可能存在混流布局击穿模型内证出的「不可能更好」）。
   影响待盘点项：SMM4 U=(1188,18)、VeriPB residual-band UNSAT、各负锚点——
   各证书是否实际带条件取决于其证明是否使用了 routing 约束（纯几何/装箱层
   证明不受影响），逐证书盘点挂后续批。
3. 全部探针脚本随档（probe_* 为主线所写，fork_* 为分身所写）。

## 主线订正二（2026-08-06，向 owner 讲解时复算发现）

原文「BFS：挖掉 source_powder 的 3 个 front 后断连；任意只挖 2 个都仍连通」**后半句不准确**。
主线独立复算（见 maze_map.txt 与本批注下方数据）：真正起封锁作用的是两个 sink front
(13,40) 与 (55,40)——**只堵这两格即可把 buckwheat 源汇断连**；(19,18)（source_powder
的 out front）对封锁无贡献，它留在 5 口极小核里是因为收缩实验的合法性不变量
（每商品须保源保汇），不是因为它是墙。复算数据：堵三格→无路；放开(19,18)→仍无路；
放开(13,40)→有路且必经该格（路长161）；放开(55,40)→有路且必经该格（路长137）。
机制判决 (b) 不受影响（封锁真实存在，且恰由终端排他规则造成）；本条属叙述精度订正
——今晚 fork 文书第三处此类病（前两处：方向性口误、见 CERT_SCOPE_AUDIT 批注背景）。

## 主线批注三（2026-08-06 晚，owner 游戏语义定谳后的翻案动议）

owner 补足关键游戏语义：**机器入口无选择权**（此前已答过一次、主线在上下文压缩中遗失）；
缓存格一格一种货、耗尽后照单全收，错货进入后加工则污染下游、不能加工则槽位中毒。
推论：混流经过门口格在最坏情况下不安全（缓冲空窗期必有吞错货机会），故本判决书的 (b)
（模型比 canonical 严=保真缺口）**面临翻案**为「(a)-修正：模型的 front 排他是对游戏语义
的正确保守编码，写宽的是 canonical 的无例外混流条款」。band22 见证若依赖「分流器筛货/
机器挑货」假语义则为真死。终裁前置（simulator-first SOP）：①分流器对堵住但非拒收出口
是否回退；②空缓存格是否照单全收；③限制口是否在 canonical 设施宇宙。证书作用域盘点
（CERT_SCOPE_AUDIT）结论不受本翻案影响（现役证书本就不依赖 routing 层）。

## 批注四（终裁指针，2026-08-06 晚补）

批注三所列三条终裁前置当晚全部齐备，终裁已下：**(b) 翻案为 (a)-修正**（模型门口
排他=对游戏语义的正确保守编码；band22 三见证双语义下真死）。终裁文书=同目录
`REVERDICT_A_REVISED_20260806.md`（含口岸三分法两次补遗与速率引理附录及其批注）。
本文书原判与批注一/二/三按审计链纪律保留原文。
