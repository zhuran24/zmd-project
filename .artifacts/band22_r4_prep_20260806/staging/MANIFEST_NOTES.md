# band22 第四轮设计包 MANIFEST 说明（2026-08-06）

| 文件 | 性质 | 来源 |
|---|---|---|
| `00_TASK_BRIEF.md` | 任务书（终版，规则段=owner 公理终审版） | 本轮新作 |
| `06_canonical_rules.json` | FROZEN | 主仓 `rules/canonical_rules.json` @ HEAD，sha=c3666d78…（**含 08-05 严格空语义条款**——上轮包内为条款补写前旧快照，本轮已换正版） |
| `06b_preprocess_plan.json` | FROZEN | 主仓 `rules/preprocess_plan.json`，sha=5c669c4f… |
| `07_generic_io_requirements.json` | FROZEN | 主仓 `data/preprocessed/generic_io_requirements.json` |
| `08_mandatory_exact_instances.json` | FROZEN | 主仓 `data/preprocessed/mandatory_exact_instances.json`（266 实例） |
| `09_problem_instance.json` + `10_problem_instance.schema.json` | 衍生 | 沿用上轮包（几何/端口描述，与空语义条款无涉；空矩形定义以任务书硬约束为准） |
| `rate_lemma_recompute.py` + `rate_lemma_receipt.txt` | 速率表 | 满率口径 10/17、17 条残道逐条、复算脚本随包可复跑 |

见证 JSON schema：沿用上轮 `band22_strict_witness_v2` 结构（10_problem_instance.schema.json 同轮约定）；坐标系注记：**y 轴向北增长（N=y+1）**。
交付合同（任务书内）：报告一切数字必须脚本从工件生成、每个结论附字段路径引用。
