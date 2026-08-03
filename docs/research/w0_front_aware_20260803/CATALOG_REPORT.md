# G1 pattern catalog — 生成报告

- 状态：**甲段交付完成；catalog 已冻结但供给不足，乙段不能直接拿它跑 G1**
- 生成日期：2026-08-03
- 权威：research-only。本文与本文引用的一切数字**不携带任何界**，不进 `U`/`L` 台账，
  `L=absent` 保持不动。

---

## 1. 一句话结论

面积算术预门**没有排除**这个限制档位（可行上界 3392 ≥ 需求 3325），
但**本次生成出的 catalog 自身供给只有 3013，比需求少 312 格**——
拿这份 catalog 去跑 G1 只会得到一个「catalog 太薄」的 INFEASIBLE，
证不出任何关于几何的事。乙段的第一件事是加深 catalog，不是跑 G1。

---

## 2. 运行标识

| 项 | 值 |
|---|---|
| 生成器 | `docs/research/w0_front_aware_20260803/g1_pattern_generator.py` |
| 输出目录 | `/home/zhuran24/zmd-pj/.artifacts/w0_front_aware_20260803/g1_run/` |
| 参数 | `--budget-seconds 5400 --target-seconds 2 --solutions-per-target 3 --workers 4 --seed 0` |
| 实测 wall | 5404.8 s |
| Python / OR-Tools | 3.13.13 / 9.15.6755 |
| manifest sha256 | `dbcb32efc9e93fb2532c331e0acb4ac2e0e78cf140ad111f2560fda176534005` |

各 region class catalog 文件 sha256：

| 文件 | 字节 | sha256 |
|---|---|---|
| `BOTTOM_I1.json` | 1,028,807 | `a4541df8b263fd5e1d2d0c9c40e5dad7138a32daa8a3e14490cf7ceed4bdf55f` |
| `BOTTOM_I2.json` | 933,607 | `e586caf3084e811f1cdb0f4ce9e886f6abff3390d62cca4671b8b93a52fcb2b5` |
| `BOTTOM_I3.json` | 1,117,637 | `f789193b4f0e6e75f7dae607b7c5386536c4a49ad876ddfc61e71af7b9067f57` |
| `BOTTOM_I4.json` | 992,600 | `b6ebae293de08b74f91c8e6b39dafcd1e66821836311f3ebadf8ba24765cc092` |
| `CLEAN.json` | 1,314,185 | `91b298edf62682601baa3b35504d9be6a56d2d62a2412c95ffee631dbc11ea4b` |
| `CORE.json` | 367 | `52d57718e9f53535e6cf2f2da6ff95c99de8a0c78ea6aa7372da70a14ec36bb5` |
| `CORNER.json` | 716,895 | `3a4c3095cc52de456a50180cd162d0b00ab9c98fe06c9c7dd55471e4dbbd4d9a` |
| `LEFT_J1.json` | 979,762 | `1b5bf7b1c1cdf6200b246dc01eb36f1e1af1cede4fd4b0cf94df14633d09c250` |
| `LEFT_J2.json` | 1,000,288 | `41b75a86a24d4db860c7fea032af7a43fe4c0be65fd22bb0f51fd0274f5c0e38` |
| `LEFT_J3.json` | 957,593 | `683388079ff32e1e41b87ba328c11d59831a3b3228d4f115006b93412d74fac0` |

---

## 3. catalog 规模

`patterns` 是去重后的**签名**数（签名 = bucket 计数向量 + 是否带孔；同签名的
pattern 对 master 完全可互换，所以只留一个）。

| region class | 倍数 | usable | packing ceiling | patterns | 菜单总长 | 已尝试 | 出解 | 原始解 | 重复签名 | 剥落 | 派生子集 | solve 秒 | 菜单跑完 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--:|
| `BOTTOM_I1` | 1 | 171 | 134 | 156 | 670 | 221 | 148 | 442 | 1544 | 238 | 1258 | 628.4 | 否 |
| `BOTTOM_I2` | 1 | 171 | 134 | 140 | 670 | 221 | 147 | 439 | 1568 | 214 | 1269 | 621.4 | 否 |
| `BOTTOM_I3` | 1 | 172 | 134 | 167 | 682 | 221 | 141 | 423 | 1480 | 205 | 1224 | 555.6 | 否 |
| `BOTTOM_I4` | 1 | 171 | 134 | 152 | 670 | 221 | 146 | 437 | 1533 | 217 | 1248 | 621.1 | 否 |
| `CLEAN` | 16 | 188 | 146 | 186 | 862 | 221 | 142 | 421 | 1485 | 237 | 1250 | 566.1 | 否 |
| `CORE` | 1 | 70 | 0 | 0 | 54 | 54 | 0 | 0 | 0 | 0 | 0 | 0.0 | **是** |
| `CORNER` | 1 | 158 | 118 | 116 | 542 | 221 | 129 | 387 | 1248 | 168 | 977 | 465.9 | 否 |
| `LEFT_J1` | 1 | 171 | 134 | 145 | 670 | 221 | 145 | 435 | 1511 | 222 | 1221 | 623.7 | 否 |
| `LEFT_J2` | 1 | 171 | 134 | 148 | 670 | 221 | 146 | 438 | 1545 | 227 | 1255 | 621.8 | 否 |
| `LEFT_J3` | 1 | 172 | 134 | 144 | 682 | 220 | 142 | 424 | 1483 | 231 | 1203 | 558.6 | 否 |

**合计 1354 个签名。** 违规拒绝（连通性 / 死体 / 其他）**全部为 0**：
生成器出的解在剥落之后一律通过 evaluator，没有一个 pattern 是被判违规丢掉的。

`CORE` 的 `complete: true` 是真结论不是超时：`R-CORE-FRONT-RESERVE` 把 20 个口前格
留空后该区域放不下任何本体，54 个目标全部无 pose，**219 台机器必须挤进其余 24 个区域**。
其余九类的 `complete: false` 是 5400 s 预算闸切断的，切在菜单的第 220 名
（菜单按「距该区域census 比例份额的距离」排序，所以跑到的是最该跑的前 26–33%）。

### bucket 分布

catalog 全部 pattern 里各 bucket 的出现次数：

| bucket | 次数 |
|---|---:|
| `M3_1i3o+2i1o` | 3773 |
| `M5_1i2o` | 1233 |
| `M6_5i1o` | 1129 |
| `M3_1i2o+2i1o` | 136 |
| `M6_4i1o` | 91 |
| `M6_3i1o` | 66 |
| `M3_1i1o` | 86 |
| `M5_1i1o` | **0** |

`M5_1i1o` 一次都没出现：catalog 里每一台 5×5 都至少做到 1i2o。
八个 bucket 里有一个是空的，这本身不是问题（bucket 是能力上封顶的分类，
`M5_1i2o` 覆盖 `M5_1i1o` 能服务的一切类），但它说明 5×5 的能力从来不是瓶颈。

带孔 pattern 共 435 个（`CLEAN` 61、`BOTTOM_I3` 59、`BOTTOM_I4` 52、`LEFT_J1` 48、
`LEFT_J3` 47、`LEFT_J2` 46、`BOTTOM_I1` 45、`BOTTOM_I2` 43、`CORNER` 34）。

---

## 4. 算术预门：面积上不排除

每个 region class 跑一次「最大化 body 面积」的 CP-SAT——计数自由、每台按其模板
最便宜的 capability level、含 front 能力约束与 `R-POWER-LOCAL`、**不含**自由空间
连通性、不含孔、不含类普查——得到的是**供给上界**：

| region class | 数量 | packing ceiling | 状态 |
|---|---:|---:|---|
| `CLEAN` | 16 | 146 | OPTIMAL |
| `LEFT_J1`–`J3` / `BOTTOM_I1`–`I4` | 7 | 134 | OPTIMAL |
| `CORNER` | 1 | 118 | OPTIMAL |
| `CORE` | 1 | 0 | 无可行 pose |

`supply_upper_bound = 16×146 + 7×134 + 118 = 3392`，`demand = 3325`，**slack = 67 格（2%）**，
十个 ceiling 全部 `proved_optimal`。判决 `NOT_EXCLUDED_BY_AREA`。

**读法（fail-closed 方向唯一）**：这个上界故意高估，所以 `supply < demand` 会否定
整个限制档位，而 `supply ≥ demand` **什么也不排除**。当前是后者。

### 试过但不 binding 的加强：本地度数条件

给上界模型补一条「每个被承诺的 front 格必须至少保留一个自由的正交邻格」——
这是 evaluator 的存活判据的**必要**后果（自由空间分量大小 ≥2 的格必有自由邻格），
所以加上它得到的仍是 sound 上界，只会更紧。

实测：**十个 class 的 ceiling 一格没降，总量仍是 3392。**
本地度数不是瓶颈；真正杀死本体的是自由空间**分裂成多个分量**这件全局的事，
而那正是 G2 的活。这条负结果的用处是：别再花时间往 G1 的上界模型里塞局部松弛，
要更紧的界只能上真连通性。

---

## 5. catalog 自身的供给：短缺 312 格

上一节算的是「区域**能**装多少」。这一节算的是「**这份 catalog** 能供多少」：
每个 region class 取它 catalog 里 body 面积最大的那个 pattern，乘以该类的倍数求和。
同类区域几何全等、各自独立选一个 pattern，所以这个和就是本 catalog 能达到的最大总 body 面积。

| region class | 倍数 | ceiling | catalog 最好 | 差 |
|---|---:|---:|---:|---:|
| `CLEAN` | 16 | 146 | 128 | −18 |
| `BOTTOM_I1` | 1 | 134 | 126 | −8 |
| `BOTTOM_I2` | 1 | 134 | 119 | −15 |
| `BOTTOM_I3` | 1 | 134 | 117 | −17 |
| `BOTTOM_I4` | 1 | 134 | 125 | −9 |
| `LEFT_J1` | 1 | 134 | 125 | −9 |
| `LEFT_J2` | 1 | 134 | 125 | −9 |
| `LEFT_J3` | 1 | 134 | 120 | −14 |
| `CORNER` | 1 | 118 | 108 | −10 |
| `CORE` | 1 | 0 | 0 | 0 |

`catalog 供给 = 16×128 + 126+119+117+125+125+125+120+108 = 3013`，
`demand = 3325`，**短缺 312 格（9.4%）**。

所以：**在本 catalog 上跑 G1 必然 INFEASIBLE，而且这个 INFEASIBLE 只说明 catalog 薄。**
按章程 §9 的措辞纪律，它不允许被写成关于几何或限制档位的任何结论。

### 类需求方向的对照（松界，全部通过）

按 repo 端口语义（slot 数，不是品类数）逐类核对「最大可供 / 需求」——
每类取各区域 catalog 里能服务该类的本体数最多的那个 pattern 求和。
这是个**松**的必要条件（各类的最好 pattern 不可能同时被选中），只用来排除显然的短缺：

| 类 | 需求 | 最大可供（松） | |
|---|---:|---:|:--|
| `3L` | 109 | 168 | OK |
| `3O2` | 6 | 168 | OK |
| `3O3` | 11 | 168 | OK |
| `3I2` | 6 | 168 | OK |
| `5L` | 32 | 88 | OK |
| `5O2` | 17 | 88 | OK |
| `6I3` | 32 | 72 | OK |
| `6I4` | 3 | 72 | OK |
| `6I5` | 3 | 72 | OK |

九类全部通过。短缺**不在能力维度，在面积维度**。

---

## 6. 短缺的机制：密度与存活的对立

短缺不是「预算不够所以没搜到好 pattern」这么简单。把 `CLEAN` 菜单里 body 面积
恰好顶到 ceiling 的目标单独拎出来、用 30–90 s（而不是生成时的 2 s）重解，得到：

| 菜单名次 | 目标 body 面积 | CP-SAT | 原始本体 | 剥落后本体 | 剥落后面积 |
|---:|---:|---|---:|---:|---:|
| 107 | 146 | OPTIMAL | 11 | 2 | **50** |
| 163 | 145 | OPTIMAL | 9 | 4 | 84 |
| 191 | 145 | OPTIMAL | 9 | 4 | 100 |
| 196 | 145 | OPTIMAL | 11 | 4 | 67 |
| 130 / 224 | 146 / 145 | INFEASIBLE（proved） | — | — | — |

名次 107 是最刺眼的一行：CP-SAT **最优地**摆出了 11 台、面积正好 146 的排布，
evaluator 一过，只剩 2 台活的、面积 50。

原因是生成器的**建模内 front 代理弱于 evaluator 的存活判据**：
模型只要求被承诺那一侧留够 `required` 个空 front 格，而 evaluator 还要求这些格
落在自由空间**分量**里。密度顶到 ceiling 时自由空间碎成小块，front 格名义上空着、
实际上够不着，本体就死了。

这解释了两件事：
- 为什么 `rejected_dead_body = 0` 而 `stripped_to_smaller` 高达 168–238——
  死体不是被拒绝，是被剥掉，剥完剩下一个更小的合法 pattern；
- 为什么 catalog 最好只到 128：最好的 pattern 来自**中密度**目标，
  顶密度目标反而剥得只剩一半。

补上 §4 那条本地度数约束再测一遍：名次 107 从 50 升到 68、163 从 84 升到 100，
但 196 反而从 67 掉到 49，**最好存活面积两边都是 100**。
局部加强不解决这个问题，和 §4 的负结果同源。

---

## 7. 乙段接手时的既定事实

1. **catalog 是甲/乙冻结线**，schema 的五个 `w0_g1_*_v1` 常量不得改字段；
   要扩就并列加 `_v2`。
2. **catalog loader 铁律**：`load_pattern` 对每个 pattern 重跑 evaluator、重算签名，
   与文件自报不符即 fail-closed 拒绝整份 catalog。文件里的签名只是缓存，永远不被信任。
3. **本 catalog 供给不足 312 格**，直接跑 G1 无信息量。先加深，再跑。
4. 加深方向按证据排序：
   - 预算闸只跑完菜单前 26–33%，把 `--budget-seconds` 抬到能跑完全菜单
     （按 220 名次 / 5400 s 的实测速率，862 名次的 `CLEAN` 需要约 5.9 倍，
     十类并跑约 8–9 小时）——这是最省事但**不一定够**的一招，
     因为 §6 说明高密度目标本身就会剥落；
   - 真正对症的是把建模内的 front 代理提到 evaluator 的强度，
     即把自由空间分量条件搬进模型（局部度数已证不 binding，见 §4/§6）；
   - 或者松掉一条充分限制（登记表里的 `R-*`），但那要重走三极性登记，
     且新档位下 §4 的预门要重算。
5. `CORE` 承载 0 台是已证事实（54 个目标全部无 pose），不必重测。
6. 独立审计器 `front_viability_audit.py` 与生成链零共享代码，
   `--self-test` 通过（两个 toy 几何 PASS、第二格突变被拒、15 条 issue code）；
   它对真实 W0 剖面重生成的固定家具与 `g1_region_model` 的 219 / 66 格逐格相等。
   乙段的任何 G1 输出都应当过它一遍。

---

## 8. 复现

```bash
env -u PYTHONPATH -u PYTHONHOME /home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python \
  docs/research/w0_front_aware_20260803/g1_pattern_generator.py \
  --output-dir /home/zhuran24/zmd-pj/.artifacts/w0_front_aware_20260803/g1_run \
  --budget-seconds 5400 --target-seconds 2 --solutions-per-target 3 --workers 4 --seed 0
```

`--seed 0` 固定 CP-SAT 随机种子，菜单顺序是纯函数，预算闸切在确定的名次上，
所以同参数重跑得到同一份 catalog。
