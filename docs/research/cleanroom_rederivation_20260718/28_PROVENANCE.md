# 28 — band22 三处承重洞：意外重复咨询的第二份独立回件（2026-08-04）来源与性质

| 项目 | 值 |
|---|---|
| 收件时间 | 2026-08-04 |
| 通道 | owner 把 GPT Pro 会话产出的 zip 落到 `~/下载/` 后喂入主线线程 |
| 性质 | **同一份 v1 送包（SHA256 `730d38c7f4c37a7b0757fb8d8565550070d0ba5b2c8e539eb2a89523b6b0ee77`）被意外发出第二次**，由另一个独立 GPT Pro 会话作答。与 27 号回件互为**独立样本**（同题、同材料、互不可见），不是 27 号的修订版 |
| 存档内容 | `28_band22_dup_answer_20260804/`（10 个文件，整目录逐字复制，未做任何改动；zip 内顶层目录 `w0_band22_consultation_answer/` 的内容被平铺到本目录） |
| 回件 zip | `~/下载/w0_band22_consultation_answer.zip`，36,261 B，SHA256 `3aeda15636afb3d25194c967fc12d3e1805c3dc4f95c62a0a7c63a18ce3cb2cc` |
| 提问包源目录 | `.artifacts/w0_consult_packs_20260804/band22_holes/`（同 27 号，v1） |
| 核实状态 | **research-only 外脑产出，我方未做任何独立复算或对抗审查** |

## 存档文件与逐字校验

| 文件 | 字节 | SHA256 |
|---|---:|---|
| `w0_band22_holes_consultation_response.md` | 35,483 | `3ce3e999061a1267a0c1823a2c4237c8048a71600c9703a4f46832eae201994a` |
| `w0_band22_local_patch_01_03.json` | 17,756 | `0073334ac6a4967a4746126848dd0193123552c8d0c042aef507155777197c54` |
| `validate_w0_local_patch.py` | 8,609 | `a2ed89e92e65406841fa7e9945566f2d5b8b26f08d4108730f05bf449f9f1181` |
| `validate_w0_local_patch_output.txt` | 357 | `e56b8aed08fd1ef53a91ba884d30129c24411479707a0851b7aafffb1b5cad7b` |
| `verify_w0_direct4_power_obstruction.py` | 5,058 | `87f9a29fcb3d16b402ddfa871d454dbbc8a5ff9caeeb4b7e2deec29cb1f3ab5e` |
| `verify_w0_direct4_power_obstruction_output.txt` | 636 | `4283559330ef39c5471a121e7e9b5a0b1ab6f5b0ec44b84a6a87396395cc0585` |
| `authority_06_problem_instance.json` | 92,201 | `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c` |
| `recompute_rerun.txt` | 12,409 | `c3ed1732c7ce005d6e0e7374ab0e670afebb2ddeb4334a477dc96dc9ed5f66b0` |
| `README.md` | 1,217 | `b428ba284b5a68097bd53c43fcb840c875812b1cd09485a816008313836d043d` |
| `SHA256SUMS` | 881 | `4d5b7ea4ced8d65f16f685e8c2402de210bce7ad19764c9afcf274d7099a4366` |

包内自带 `SHA256SUMS` 列了除自身外的 9 个文件；逐条与落盘字节比对，**9/9 一致**。

## 订正便条：这一份**看到了**（与 27 号不同）

27 号那份对方只拿到 v1、未见 owner 事后贴出的口头订正。本份报告 §1 标题就是「三处勘误的吸收结果」，逐条列出采用值，说明 **owner 对这个会话也贴了订正便条**（此前记为「未知」，现由回件正文坐实）。但**第三条的内容与 27 号记录的不同**：

| # | 本份报告吸收的订正 | 27 号 PROVENANCE 记的第三条 |
|---|---|---|
| ① | band14 的 5×5 slit 容量 `≤11` | 同 |
| ② | 模型 B 孔洞净耗：`a=1` 为 20，`2≤a≤64` 为 25 | 记作「`a=1`」与「孔洞净耗 20 不是 35」两条 |
| ③ | 四条 4 高带分配数为 **35 个标号解、归并 11 类，不是 9 种** | 未记 |

也就是说两个会话拿到的订正措辞/条目并不完全相同，引用任何一份的前提数字前先核对它实际吸收的是哪一版。

## 对方自述的要点（转录，未核实）

1. 逐洞结论：洞①选 A（坐标级容量修复）、洞③选 A（final 输入与 feeder/riser 修复）、洞②选 B。
2. 带高序改为 `(5,3,4,3,5,3,4,3,5,3,5,3,4,4)`，15 条走廊 `y=(1,7,11,16,20,26,30,35,39,45,49,55,59,64,69)`，台数 `3×3=132 / 5×5=49 / 6×4=38`。
3. **洞②给出不可行定理**：在「走廊行全部保留给 transport、电杆 2×2 机身必须整体落在制造带自由格」这一口径（报告称 D0）下，**判死全部「相邻两条 4 高带承载核心 + 模型 A 或模型 B 孔洞」的带内杆直连宏族**，并称其覆盖不等式已由 `verify_w0_direct4_power_obstruction.py` 有限状态穷举复核（输出 `RESULT: every Model A and Model B hole position/residue is impossible under the stated scope`）。
4. 因此对方**明确声明本包不是完整可行 witness**：洞①/洞③的坐标补丁在该口径下不存在带内电杆解。
5. 自称仍存活的出口两条：允许少量电杆占用走廊行并给环局部绕行；或改用不属于「相邻 4+4 直连」族的核心接口（报告称 N1）。两条都没有 strict-checker 见证。
6. 自跑的 `validate_w0_local_patch.py` 输出 `PATCH_VALIDATION: PASS`，但脚本自己打印 `NOT CHECKED: power coverage, operation binding, full strict connectivity`。

## 与 27 号的分歧（重要，未裁决）

同一道题的两个独立样本给出**方向相反的结论**：

- **27 号**：交出坐标级方案 A witness，含 25 根电杆，自称是该布局下的精确最小值 —— 即宣称带内杆方案可行。
- **28 号（本份）**：证明「相邻 4+4 直连 + 模型 A/B 孔洞 + 带内杆」整族在 D0 口径下不可行 —— 即宣称同类方案不可能。

两者未必直接矛盾（口径可能不同：27 号把孔洞挪到 band12、带序 `(4,3,3,3,3,3,3,4,4,4,5,5,5,5)`，28 号的定理有明确 scope 假设「corridor 行全保留 + 杆整体在制造带内」），但**这正是需要我方亲自复算才能分辨的点**：要么 27 号的 witness 违反了 28 号定理的某条前提（则定理 scope 成立、witness 需重新验其杆位），要么 28 号定理有洞。在做出这项复算之前，两份都不得被当作既定事实引用。

## 性质与边界

**research-only 外脑产出，未经我方核实。** 本目录只做逐字存档，不构成复核结论：

- 对方**没有**我方 official strict checker 的 CLI / schema / build；包内 JSON 与两个 .py 都是它自造格式与自造校验器，不是 authoritative 证书，`PATCH_VALIDATION: PASS` 与 `RESULT: ... impossible` 都只是它自跑自评。
- 报告里全部【已证明】【强论据】【猜测】标注均为对方自述的证据等级，我方一条都没验；引用前必须自己先算一遍。
- 不携带任何 authority：不改变 `U=(1188,18)`、`L=absent`，不登记任何界，不触碰 cut / production / certified 状态，也不触碰 `PROJECT_LOCK.md` 的任何 `F-*`/`PCR-*`/`CUT-*` 条款。
- 先例纪律（19 号、147.4 两次）：外脑推理文书入库不等于采信，承重引用前要过 refute 席，数字前提要标证据等级。
