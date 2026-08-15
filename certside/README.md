# certside/ — 轴 B 证书侧：binding PB sidecar（Phase 0+1）

> **这是什么**：对生产链 binding INFEASIBLE 判决的**异构离线复验**——从冻结
> 工件独立重建 PB/OPB 编码 → RoundingSat 重解出 VeriPB 证明 → 独立检查器复核
> → 对账。纯 diagnostic：**不进认证 TCB、不写 proof 路径、不影响任何 gate**
>（同 formal/ 的锁面地位；16 号 §6.4 政策原样有效）。
> 设计权威：`docs/research/p3_0c_binding_pb_sidecar_design_v1.md`（内容 v2，
> 经双会话对抗审回收；审查归档 `docs/research/p3_0c_sidecar_reviews_20260705/`）。
> 原始规划坐标：`docs/history/status/00_master_roadmap_pre_phase3_20260812.md` §2b；当前后续工作见 `docs/项目说明/ROADMAP.md` 的 proof logging 工作线。

## 目录

| 文件 | 作用 |
|---|---|
| `binding_canonical_semantics_v1.md` | 语义规范（源码逐行核对版；三层来源声明：冻结数据/硬编码 TCB/pending 前端） |
| `sidecar/emitter.py` | 独立 OPB emitter（**零 import src/**；输入校验 fail-closed + 域枚举独立重实现 + 结构化 varmap/conmap + 组合护栏） |
| `sidecar/runner.py` | WSL 求解检查链（判定协议：结论行 anchored 唯一匹配，禁退出码判定） |
| `sidecar/witness_checker.py` | OPB-level witness 独立复验（不调用 emitter 约束生成） |
| `sidecar/canonical_witness_checker.py` | canonical-level witness 复验（从原始输入语义独立验证；应有对象集合第二实现；SAT 二段升级 → DIVERGED_CANDIDATE） |
| `sidecar/run_acceptance.py` | 合成验收 harness（30 checks：UNSAT/canaries/INPUT_INVALID/双向突变/工具链与 canonical-checker 红测） |
| `sidecar/frontend.py` | 冻结工件解析前端（**零 import src/**；strict-JSON exact-decimal + operation profile 独立重推 + 五工件全长 sha256） |
| `sidecar/parity_check.py` | profiles 对拍脚本（⚠ 刻意 import 生产当 oracle，是验证 harness 非 sidecar 组件；PARITY OK: 21/21 profiles 精确一致） |
| `sidecar/real_sample.py` | 真实工件端到端样本（mandatory 实例全放；R1 core-only、R2 core+box，均应 SAT+witness） |
| `sidecar/patch_rs_logger.py` | RoundingSat 上游缺陷本地补丁（见下） |

## 状态（2026-07-18，Batch 3+5 语义迁移）

- **迁移后结构验收 30/30 全绿**（本机 OR-Tools solver shim，覆盖 emitter、OPB、
  双层 witness checker 与全部红测；输出仅在 `/tmp`）。Windows→WSL 专用的
  RoundingSat→VeriPB→CakePB 完整 proof 链仍须在对应工具链环境复跑；
  `run_acceptance.py` 的正式输出目录 `work/` 为生成产物、不入库。
- 覆盖：UNSAT 4 类（计数鸽笼/多商品溢出/正需求零槽哨兵编码）全 CONFIRMED
  （正式 proof 链复跑后才可重新声明 proof-backed）；FEASIBLE canaries 6 全
  SAT + 双层 witness 复验（OPB-level + canonical-level）升 `DIVERGED_CANDIDATE`；
  另含 protocol_core 14 实体进口 canary；非法输入 11 类全 fail-closed 拒绝；
  双向突变红测 4/4 被抓（含 over-constraint
  使 canary 翻 UNSAT——sidecar 最危险 bug 类的哨兵）；canonical checker 自身
  红测 5/5（篡改计数/双选/binding cell 或 generic slot 出 pose/漏变量全被精准拒）。
- **CakePB（第四层纵深）已接入且默认开**：每个 CONFIRMED 都经过
  RoundingSat → veripb → elaborate(kernel) → **cake_pb（形式化验证 checker）**
  四层，任一环节非唯一 `s VERIFIED UNSATISFIABLE` 结论行即降级 UNKNOWN
  （cake_pb 失败时 exit code 亦为 0，判定只认输出文本）。含 17k 变量真实模型
  实测通过。前置依赖 = RoundingSat 本地补丁 **v2**（rup 必须在 output 段之前，
  kernel parser 严格按段序——见 patch_rs_logger.py）。
- **P1.2 已于 2026-07-07 收口；Phase 0 采集侧待单独排期**（owner 2026-07-05 拍板，选项 b）。
- **冻结工件解析前端已落地**（frontend.py）：五工件 strict-JSON exact-decimal
  独立解析、operation profile 独立重推（Fraction 精确 ceil），与生产
  OPERATION_PORT_PROFILES 对拍，并额外核对
  `generic_input_slots_by_operation={protocol_core:14, box_sink:3}`；generic input
  已从单一 wireless 虚拟槽迁移为所选 pose 上带 `x/y/dir` 的实体进口。
  `real_sample.py` 的新判据为 R1 mandatory core-only SAT、R2 core+box SAT；
  真实工件应在候选池完成 Batch 3+5 重生成后运行。
- **真实生产判决对账仍不可做**（by design）：需要 canonical sample record
  （verdict/scope/ordinal 字段）——采集侧改造动生产文件，属 P3.0c 轴 B 的
  Phase 0 自身排期、待 owner 批；与已关闭的 P1.2 无关。
  在此之前 frontend 能对任意布局出 OPB 并跑链路，但产出只是 sidecar 自身判定、
  不与生产 verdict 关联。

## 工具链复现（WSL Ubuntu-24.04）

```bash
apt-get install -y libgmp-dev libboost-dev zlib1g-dev
git clone https://gitlab.com/MIAOresearch/software/roundingsat ~/cert_toolchain/roundingsat
python3 <repo>/certside/sidecar/patch_rs_logger.py   # 必须：见下方缺陷说明
cd ~/cert_toolchain/roundingsat && mkdir -p build && cd build && cmake -DCMAKE_BUILD_TYPE=Release .. && make -j
git clone https://gitlab.com/MIAOresearch/software/VeriPB ~/cert_toolchain/VeriPB
cargo install --path ~/cert_toolchain/VeriPB          # veripb 3.0.2（Rust 主线）
```

**RoundingSat 上游缺陷（master d4edbf7，本地已 patch）**：parse 期平凡矛盾
（如 2 变量的 `= 3` 行）走 `Logger::unsat()` 时不 log 任何推导，conclusion
指向 init dummy（`rup >= 0`，trivially true），veripb 正确拒绝。patch 在
conclusion 前补 `rup >= 1 ;`（全路径 sound）。**未打 patch 的 RoundingSat
会让这类样本全部 PROOF_REJECTED**（fail-closed，不产生假 PASS，但复验失效）。

**工具链怪癖（判定协议的由来，均实测坐实）**：veripb 检查失败 exit code 仍 0；
RoundingSat UNSAT exit code 为 1、SAT 默认不打 witness（需 `--print-sol=1`）；
proof-log 模式要求扩展 OPB 头且 `#equal=` 必须精确等于等式行数。

## 跑验收

```powershell
python certside/sidecar/run_acceptance.py   # 需上述 WSL 工具链就位
```
