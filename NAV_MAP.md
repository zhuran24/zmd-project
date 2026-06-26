# 代码导航图

这张图只描述当前工作树的调用和 authority 边界。模块名本身不构成 soundness 证明；证明范围以 `PROJECT_LOCK.md` 和机器义务为准。

## 入口与求解链

```text
main.py
  -> src/search/outer_search.py
       producer: 枚举候选、运行 Benders/LBBD、只提交 CANDIDATE_PROPOSED
       -> src/search/benders_loop.py
            -> src/models/exact_coordinate_master.py / master_model.py
            -> src/models/binding_subproblem.py          certified gate
            -> src/models/routing_subproblem.py          certified gate
            -> src/models/flow_subproblem.py             diagnostic-only
            -> src/search/independent_infeasibility_reverifier.py
               whole-layout nogood 独立复验，不确认则不落 cut
       -> src/search/certified_frontier.py
          strict full-frontier projection/evidence
       -> src/search/terminal_fixed_witness_capsule.py
       -> src/search/terminal_fixed_witness_verifier.py
          固定发布 witness 的 binding/routing 复验
       -> src/search/exact_campaign.py
          checkpoint/resume + ExactCampaign.supervisor_seal() 唯一终端 CERTIFIED mint（当前无生产 caller）
       -> src/search/certified_surface.py
          P1.2 open gate + sealed campaign 验证 + canonical public publisher
```

## 发布链

```text
CANDIDATE_PROPOSED checkpoint
  -> proposal-ready marker
  -> [OPEN: production supervisor CLI/launcher]
  -> ExactCampaign.supervisor_seal()
  -> supervisor-sealed disk authority
  -> publish_verified_certified_delivery_surface()
  -> data/solutions/final_solution.json
  -> data/blueprints/optimal_blueprint.json
  -> data/solutions/certified_delivery_manifest.json
```

generic serializer、blueprint exporter、manifest writer、viewer/report builder 和 IndustrialPlanner adapter 都不是独立发布 authority。它们只能写非 canonical 路径，或由中央 publisher 在验证后的事务内调用。

## 目录

| 目录 | 当前角色 |
|---|---|
| `src/search/` | outer producer、campaign、frontier、fixed-witness、supervisor seal、中央发布面 |
| `src/models/` | master、binding、routing；flow 为诊断模块 |
| `src/cuts/` | cut 生成、校验与生命周期；`step_8_apply_to_master` 仍是后续 P1.3 集成边界 |
| `src/io/` | strict JSON、序列化和 delivery manifest 基础设施，不单独拥有公开认证权 |
| `src/render/`, `src/adapters/` | postprocess/delivery surface，必须消费中央验证后的 authority |
| `src/tests/` | 单元、回归和 soundness 红测 |
| `rules/`, `data/preprocessed/` | canonical rules 与冻结输入 |
| `data/proof_obligations/` | P1.2 机器义务、sink inventory、allowlist |
| `data/review_gates/` | owner 手动 phase gate；当前仍阻塞 |

## 建议阅读顺序

1. `PROJECT_LOCK.md`
2. `docs/certified_proof_chain_analysis.md`
3. `src/search/outer_search.py`
4. `src/search/exact_campaign.py::ExactCampaign.supervisor_seal`
5. `src/search/certified_surface.py::publish_verified_certified_delivery_surface`
6. `scripts/check_p1_2_proof_obligations.py`
