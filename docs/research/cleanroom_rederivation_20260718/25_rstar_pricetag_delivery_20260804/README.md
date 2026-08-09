# R-* 价签精算交付包

本交付包按 `00_ASK.md` 完成九条充分限制的价签、前提集、撤退线和判定实验设计；`authority=false`，不登记任何界，账本不变。【已证明】

主报告是 `RSTAR_PRICETAG_REPORT.md`，其中含完整总表、依赖图、隐藏前提审计、九条逐项精算和不超过一页的全局判读。【已证明】

| 文件 | 用途 |
|---|---|
| `RSTAR_PRICETAG_REPORT.md` | 主报告 |
| `patch_A_total_table.md` | 可直接替换的九行总表 |
| `patch_B_04_derived_theorems.merge.json` | 对九条 theorem 只增不改的 JSON 片段 |
| `04_derived_theorems.patched.json` | 补丁 B 的完整应用结果 |
| `patch_C_03_slack_audit_rows.merge.json` | 2 条无条件行与 5 条 G1 条件行 |
| `03_slack_audit_table.patched.md` | 补丁 C 的完整应用结果 |
| `patch_D_experiment_specs.md` | 九份实验规格，含伪代码、常量、规模、预算和三分判读 |
| `apply_price_tag_patches.py` | 幂等应用 B/C，拒绝覆盖不同旧值 |
| `price_tag_arithmetic_audit.py` | 标准库复算候选域与关系域数字 |
| `price_tag_arithmetic_results.json` | 算术复算结果 |
| `validate_delivery.py` / `validation_results.json` | 结构、JSON、旧字段保持、幂等性与关键算术的自校验 |

应用补丁的命令如下，源目录应是压缩包中含 `03_slack_audit_table.md` 与 `04_derived_theorems.json` 的 `rstar_pricetag` 目录。【已证明】

```bash
python apply_price_tag_patches.py \
  --source-dir /path/to/rstar_pricetag \
  --patch-dir /path/to/rstar_pricetag_delivery \
  --output-dir /path/to/patched-output
```

复核交付包的命令如下。【已证明】

```bash
python validate_delivery.py \
  --delivery-dir /path/to/rstar_pricetag_delivery \
  --source-dir /path/to/rstar_pricetag
```

本批实际执行的是无求解器算术与坐标枚举；补丁 D 中的 CP-SAT 项是纸面判定实验规格，未在本批施工。【已证明】

所有百分比都绑定冻结基线 H0，且分别标明候选位姿、矩形见证、覆盖关系或 catalog 口径；它们不能混成一个全局“解被删比例”。【已证明】
