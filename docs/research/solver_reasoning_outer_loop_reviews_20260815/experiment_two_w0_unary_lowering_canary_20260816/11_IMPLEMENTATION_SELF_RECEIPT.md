# W0 一元 lowering 金丝雀实现自检凭据

> **日期：** 2026-08-16
> **状态：** `IMPLEMENTED_READY_FOR_FROZEN_RUN`
> **协议身份：** `0339c745b6c7f498fc989398de380a78578fc785`
> **边界：** 本凭据只证明 research-surface 实现与开发自检齐备；不替代正式三臂运行，也不预告最终判词。

## 实现坐标

| 文件 | 职责 |
|---|---|
| `05_LOWERING_CONTRACT_V1.json` | 一元 target、trigger、reject-set 等值与禁止差分 |
| `06_check_endpoint_metrics.py` | 纯标准库 endpoint evaluator 合成灵敏度检查 |
| `07_check_lowering_contract.py` | 纯标准库 CpModel snapshot 差分与 lowering 等值检查 |
| `08_CANARY_MANIFEST.json` | 输入、代码、W0、旧前缀、运行参数与环境身份 |
| `09_w0_unary_lowering_canary.py` | 单臂研究 harness；不修改现有 model 源码 |
| `10_launch_w0_unary_lowering_canary.py` | 三臂顺序发射、endpoint 前后快照、独立检查与聚合判词 |

## 边界核验

- tracked `src/`、`scripts/`、规则、认证和发布面零修改；
- lowering 只在 research harness build 完现有 `PortBindingModel` 后追加；
- 下游 exact routing precheck、routing solve 与 point-nogood fallback 均保留；
- 通用 D3/D4 没有入口、开关或状态变化；
- 全量 journals 只写 local-optional `.artifacts` 根。

## 开发自检

### Endpoint evaluator

11/11 合成控制全部 PASS，包括面积与 `min_side` 双关键字、单点／整 band 排除、幂等、stale context、`L=ABSENT`、热点迁移、`NOT_REACHED` 与一元域删除。

### Lowering contract

独立 proto checker 复算：

- baseline：17,190 variables、289 constraints；
- treatment：17,190 variables、290 constraints；
- 原变量、原约束、search strategies、objective、assumptions、hint、symmetry 全部等值；
- 唯一新增约束为 `w0_j041_force_unused`；
- 目标变量为 index 17,156，名字 `slot_boundary_port_041:out:0___unused__`；
- pre-existing target `ExactlyOne` 位于 constraint index 273；
- `ExactlyOne(target domain) ∧ unused=1` 与 `¬Active_041` 等值。

判词：`PASS / EQUAL_TO_ACTIVE_041_TRIGGER_SET`。

### 25-event 树外三臂开发跑

| arm | 结果 | proposals | J true | routing |
|---|---|---:|---:|---:|
| A | `EVENT_CAP_REACHED` | 25 | 25 | 0 |
| B | `EVENT_CAP_REACHED` | 25 | 25 | 0 |
| C | `SOLVER_TIMEOUT_BINDING` | 0 | 0 | NOT_REACHED |

A/B 的 ordered selection digest 完全相同；25 个事件均为 `front_blocked`，local-signature 分布完全相同，每个 point nogood 为 285 literals。C 的 model snapshot contract PASS，但在冻结 20 秒第一次 binding solve 内没有终态或 proposal。

另一次 1007-cap baseline 开发探针因外层工具 300 秒上限被中断；中断前 progress 为 950 proposals、950 个 J trigger、全部 `front_blocked`、0 routing solve。该探针不是正式收据，不进入最终判词；它只用于确认正式运行需要后台 launcher 与 `.DONE` 终态纪律。

## 预期风险，不改判据

开发跑已经暴露“局部 family 被一元约束消掉，但 binding 求解成本可能塌进第一次 proof search”的候选热点迁移。冻结协议已把这种形态归入 `INCONCLUSIVE` 或成本回归，而不是事后把 `J true=0` 单独升级为成功。正式运行仍按原协议执行，不缩短 1007 baseline／observer，也不提高 treatment 单次 solve cap。
