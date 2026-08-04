# 27 — band22 三处承重洞修补交付包回件（2026-08-04）来源与性质

| 项目 | 值 |
|---|---|
| 收件时间 | 2026-08-04 |
| 通道 | owner 把 GPT Pro 会话产出的交付包（zip）落到 `~/下载/` 后喂入主线线程 |
| 存档内容 | `27_band22_witness_delivery_20260804/`（3 个文件，逐字复制，未做任何改动） |
| 回件 zip | `~/下载/band22_three_holes_delivery_bundle.zip`，34,279 B，SHA256 `1f07ef2e687940a5de3472b32374f6b91339c31876aaabaee7444693ddb8584c` |
| 实际送出的提问包（v1） | SHA256 `730d38c7f4c37a7b0757fb8d8565550070d0ba5b2c8e539eb2a89523b6b0ee77`（对方在报告 §0 里回引的就是这个 hash，可确认它拿到的是 v1） |
| v1 之后的三处口头订正 | owner 在送出 v1 后另贴便条给对方：①band14 slit 上限 ≤11；②模型 B 中 `a=1`；③孔洞净耗 20（不是 35）的标号解 |
| 未送出的提问包（v2） | `~/下载/w0_band22_holes_20260804.7z`，44,489 B，SHA256 `d0e01f687ef85a2255e4b5c082441c56f4591e37881826f7a421e6943355c428`；这一版把上面三处订正写进了材料，但**没有发出**，对方从未见过 |
| 提问包源目录 | `.artifacts/w0_consult_packs_20260804/band22_holes/`（`00_ASK.md`、`01_construction_verbatim.md`、`02_audit_three_holes.md`、`03_rules_excerpt.md`、`04_board_and_demand.md`、`05_recompute_check.py`、`05_recompute_output.txt`、`06_problem_instance.json`） |

## 存档文件与逐字校验

| 文件 | 字节 | SHA256 |
|---|---:|---|
| `band22_three_holes_repair_report.md` | 32,393 | `481c2404f5b1b335e30f9822184e31b7cdacc9ca1f277f40bd57087a499f2d9e` |
| `band22_repaired_design_witness_not_checker_schema.json` | 638,455 | `c8e47b4482475f02e3bcae36d96d153366055003ffb5a469c00c8b5a9dd28245` |
| `band22_delivery_manifest.json` | 995 | `18e6c4784e529f892582fae04b2ff3177e24a15f80facfbb3c50b8877b4ca314` |

前两个文件的 hash 与包内自带的 `band22_delivery_manifest.json` 所记一致（逐条比对通过）。zip 内无顶层目录，三个文件平铺存档。

## 对方自述的五个要点（转录，未核实）

1. 交出的是**坐标级方案 A**（V0-A 补丁）：14 条带 + 15 条单格走廊 + 交替极性 + 单一有向环 + live-pose 精确端口覆盖。
2. 带序改成 `(4,3,3,3,3,3,3,4,4,4,5,5,5,5)`，核心锚点 `(60,36)`、朝向 `inputs_east_west`。
3. **孔洞挪到偶数号 band12**（`H=[1,6]×[51,57]`），靠重用原本已排除的 `x=1` 返回列与天然 `x=2` riser，把孔洞净耗做到 20 格（不是原稿的 25 格）。
4. **25 根电杆**，自称是该布局下的精确最小值。
5. 全量端口重编译后的 transport 组件计数 `straight=596, turn=16, merger=274, splitter=257, cross=0`，合计 1143；并声明先前记录的 `991/29/84/39` 是稀疏原型计数、以本次为准。

manifest 里另附对方自跑的 reload 自检：`errors=0`、266 mandatory 设施、25 电杆、3644 机身格、1143 route component、628 激活端口、219/219 制造机受电、19/19 商品路由，且明确标注 `official_checker_ran: false`。

## 性质与边界

**research-only 外脑产出，未经我方核实。** 本目录只做逐字存档，不构成复核结论：

- 对方**没有拿到我方 official strict checker 的 CLI、序列化 schema 或 build**，因此那张 JSON 是它自定义的 witness 格式（文件名里的 `not_checker_schema` 是它自己标的），不能直接喂我方 checker，也不是 authoritative 证书。
- 报告里所有【已证明】【强论据】标注、格数账、杆数最小性、组件计数、端口覆盖结论全部是对方自述；本文书写就时我方未做任何独立复算或对抗审查，引用任何一条前必须自己先算一遍。
- 对方看到的是 **v1 材料**，不含上面列出的三处 owner 订正；凡涉及 band14 slit 上限、模型 B 的 `a=1`、孔洞净耗 20/35 这三点的结论，都要按「对方在旧前提下作答」重新校对。
- 不携带任何 authority：不改变 `U=(1188,18)`、`L=absent`，不登记任何界，不触碰 cut / production / certified 状态，也不触碰 `PROJECT_LOCK.md` 的任何 `F-*`/`PCR-*`/`CUT-*` 条款。
- 先例纪律（19 号、147.4 两次）：外脑推理文书入库不等于采信，承重引用前要过 refute 席，数字前提要标证据等级。
