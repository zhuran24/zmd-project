# P2.0 吞吐认证特化设计稿批（2026-08-07）

**性质**：研究层设计稿批。不改生产代码、不改锁面、不改 canonical。落地立项待 owner 过目。

## 读这个目录的顺序

| 文件 | 是什么 | 给谁 |
|---|---|---|
| `OWNER_DECISION_SUMMARY.md` | 一页决策摘要：结论 + 要 owner 定的事 | **先读这个** |
| `P2_0_SPECIALIZED_DESIGN_V1.md` | 完整设计稿（10 节 + 附录），承重文本 | 实现者 / 审查席 |
| `rate_table.py` + `_receipt.json` + `_stdout.log` | 速率常数表（表 A/B/C/D/E） | 复跑验证 |
| `split_free_probe.py` + 收据 + 日志 | 前件族是否为空的探针 | 复跑验证 |
| `maxmin_segment_probe.py` + 收据 + 日志 | 细流段厚度与混流窗口的探针 | 复跑验证 |

## 一句话结论

「目标钉死 ⇒ 速率是常数 ⇒ 流量谓词退化成常数系数线性账」这个立项命题，**前半段成立、后半段不成立**：速率确实全是可精确复算的有理常数，但「常数系数挂 use 变量」需要网络级纯流，而网络级纯流被本批两个探针证伪（6 种商品、占 37% 路由流量，在任何最小车道分配下都必然分流；由此产生 15 对不同中间品的合法混流窗口）。

真正的塌缩在**求解结构**：多商品流可分解成「逐商品单商品流 + 格位打包」，单商品流的不可行证书是**最小割**（组合对象），省掉 v2 §4.3 那套有理 Farkas 基建。

**推荐路线**：双侧夹逼——上界侧用与车道分配无关的松弛（flowbound 线的 `A ≤ 1167` 现成可用），见证侧用受限族；两边相遇即闭合全局 lex 最优性，不需要新引理。

## 复跑

```bash
cd /home/zhuran24/zmd-pj
python           docs/research/p2_0_specialized_20260807/rate_table.py
.venv/bin/python docs/research/p2_0_specialized_20260807/split_free_probe.py
.venv/bin/python docs/research/p2_0_specialized_20260807/maxmin_segment_probe.py
```

后两个需 `ortools`（走 `.venv`）。`maxmin_segment_probe.py` 复用 `split_free_probe.py` 的 `solve_duty()`，两文件须同目录。三个脚本全部 `Fraction` 精确、零浮点；`rate_table.py` 内含与 `.artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber_receipt.json` 的逐字符互证断言与 266 实例普查断言，断言不过直接抛错。

`maxmin_segment_probe.py` 跑约数分钟（对下界二分、每步一个 CP-SAT 可行性问题）。

## 已知欠账

1. **未过独立 refute 席**。本批是起草席自产的承重推理文书，按仓库家规（`memory/referee-authored-docs-blind-spot.md`）入库前应过一道对抗审查。预判攻击面已写在设计稿 §9.3，方便审查席直接打。
2. **生产规模行数未实测**（设计稿 Q1）。所有「行数可接受」的工程判断在它闭合前是【假设】。

## 对外部线的两条净输入

- **给 flowbound 线一条禁令**：`L ≥ Σ_k ceil(F_k/C) = 308`（比现役聚合的 305 紧）**依赖「每格单商品」这个限制**，不可进无条件上界链；只能记进「受限族内上界」台账。详见设计稿 §4 末与 §8。
- **给 flowbound 线一条互证**：`F_route = 9,135` / `F_target = 9,169.5` 本批第三次独立复算通过（flow_account → OB1 → 本批）。
- **给 mixflow / U-01 线**：混流只可能发生在分流细流段（不在主干），这对需防的场景是一条收窄；`item_admission_port_exclusion` 的裁决结论不受影响，但理由 (a) 的措辞建议精确到「最小车道之间」。详见设计稿 §7。
