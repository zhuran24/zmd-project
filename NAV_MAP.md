# 代码导航图

这张图只描述当前工作树的调用和 authority 边界。模块名本身不构成 soundness 证明；证明范围以
`PROJECT_LOCK.md` 和机器义务为准。代码资产分类、历史源码逻辑隔离和维护者实现索引见
`docs/项目说明/24_repository_asset_governance.md`。文档知识层的稳定入口是
`docs/START_HERE.md`；当前状态只看 `docs/CURRENT.md`，结论与证据目录只看 `docs/CATALOG.md`。 Adapter 边界与入口见 [`src/adapters/README.md`](src/adapters/README.md)。文档维护契约由 `.docsystem/manifest.json` 与各目录 `DOC_POLICY.json` 提供，统一通过 `devtools/docctl.py` 查询和检查。

## 入口与求解链

```text
main.py
  -> src/search/outer_search.py
       producer: 枚举候选、运行 Benders/LBBD、只提交 CANDIDATE_PROPOSED
       -> src/search/benders_loop.py
            -> src/models/exact_coordinate_master.py / master_model.py
               front-clear lift (EXACT_MASTER_FRONT_CLEAR_LIFT, 默认 OFF):
               demand SSOT = src/models/port_binding.py::routing_visible_port_demands
               generic-input 商品 = 普通 routed commodity（producer output → provider physical input）
            -> src/models/binding_subproblem.py          certified gate
               provider capacity SSOT = 已哈希 preprocess_plan 同字节快照的完整
               generic_input_slots_by_operation map（跨 outer/session 整图比较）
               box_sink: 3 个实体输入口 / 3 个实体输出口
               protocol_core: 14 个实体输入口 / 6 个实体输出口
            -> src/models/routing_subproblem.py          certified gate
            -> src/models/flow_subproblem.py             diagnostic-only
            -> src/search/independent_infeasibility_reverifier.py
               whole-layout nogood 独立复验，不确认则不落 cut
       -> src/search/certified_frontier.py
          strict full-frontier projection/evidence
       -> src/search/candidate_proof_replay.py
          strong-status sink replay（不替代 fixed-witness identity）
       -> src/search/certified_artifact_contract.py
          runtime artifact/source/hash contract
       -> src/search/pr2_l0_micro_verifier_core.py
          -> src/search/pr2_l0_true_verifier_child.py
             isolated L0 verification child
       -> src/search/terminal_fixed_witness_capsule.py
       -> src/search/terminal_fixed_witness_verifier.py
          固定发布 witness 的 binding/routing 复验
       -> src/search/exact_parallel_scheduler.py
          parallel candidate waves；coordinator-only persistence
       -> src/search/exact_campaign.py
          checkpoint/resume + ExactCampaign.supervisor_seal() 唯一终端 CERTIFIED mint（生产 caller = scripts/run_supervisor_seal.py 独立命令；main.py 普通完成仍止于 CANDIDATE_PROPOSED）
       -> src/search/certified_surface.py
          owner-gated phase resolver + sealed campaign 验证 + canonical public publisher
```

## 发布链

```text
CANDIDATE_PROPOSED checkpoint
  -> proposal-ready marker
  -> scripts/run_supervisor_seal.py（独立生产命令，从 marker 驱动 supervisor；非 main.py 顺手）
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
| `src/models/` | master、binding、routing；flow 为诊断模块；`pose_bool_exact_master.py` 是 active env-gated alternative，但 certified mode 显式禁用且不是 public certified backend |
| `src/cuts/` | cut family registry、生成、独立校验、typed lowering 与生命周期；哪些 family 当前 active、shadow-only、retired 或获 production admission，只从 `docs/CURRENT.md` 与对应机器/owner 源读取 |
| `src/io/` | strict JSON、序列化和 delivery manifest 基础设施，不单独拥有公开认证权 |
| `src/render/`, `src/adapters/` | postprocess/delivery surface，必须消费中央验证后的 authority |
| `src/tests/` | 单元、回归和 soundness 红测 |
| `rules/`, `data/preprocessed/` | canonical rules 与冻结输入；`preprocess_plan.json` 的完整 provider map 和 candidate 实体端口几何同属 certified snapshot |
| `data/proof_obligations/` | P1.2 机器义务、sink inventory、allowlist |
| `data/review_gates/` | owner-only phase gate 与显式 manual decision；当前值由 `docs/CURRENT.md` 投影 |
| `data/repository_governance/` | 代码资产与文档系统的 governance schema/manifest；只治理 inventory、操作契约和开发投影，不授予 proof authority |
| `.docsystem/manifest.json` | 文档系统唯一固定自举入口，定位 policy、原则、指南、ADR、actions 与恢复面 |
| `devtools/docctl.py` | 按目标路径生成最小操作卡，维护 framework core，并检查本次文档 diff |
| `devtools/check_repository_code_assets.py` | Git-visible 代码资产重算与 fail-closed 分类/投影检查 |
| `.rgignore` | developer `rg` 的历史源码与 retirement-candidate 投影；full/security gate 不读取它 |

## 建议阅读顺序

1. `PROJECT_LOCK.md`
2. `docs/certified_proof_chain_analysis.md`
3. `src/search/outer_search.py`
4. `src/search/exact_campaign.py::ExactCampaign.supervisor_seal`
5. `src/search/certified_artifact_contract.py` + `pr2_l0_micro_verifier_core.py` + `pr2_l0_true_verifier_child.py`
6. `src/search/certified_surface.py::publish_verified_certified_delivery_surface`
7. `src/cuts/frozen_artifacts.py` + `src/cuts/state_snapshot.py` + `src/cuts/lifecycle.py::step_8_apply_to_master`
8. `scripts/check_p1_2_proof_obligations.py`
9. `docs/项目说明/24_repository_asset_governance.md`（维护、搜索、lint、pytest discovery 或历史证据边界）
