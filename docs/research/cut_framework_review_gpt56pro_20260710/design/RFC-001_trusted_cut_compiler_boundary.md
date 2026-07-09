# RFC-001：把可信边界收口为 typed validate-and-compile

状态：评审建议稿，不应盲目 apply。

## 1. 问题

当前规范把 validator 描述成唯一 trust point，但生产链至少还信任以下组件：BState 构造器、scope 完整性、cert/body 一致性、family compiler、master add API、ghost 条件文字绑定与 CP-SAT 语义。当前 F1 validator 读取 `geometric_payload`，Step 8 却读取 `cert.cert_payload`；生产入口又忽略 `validate_cut_integrity()` 的错误返回，已经证明“验证一个对象、编译另一个对象”可发生。

此外，`Cut` 同时保存 body 与 cert 两份可独立变更的表达，`BState` 是可变对象且使用裸四元组表达 ghost，family 数量和可编译能力则散落在 Literal、validator 表、Step 8 分支和文档中。当前 API 允许调用方手工拼接一条 gauntlet，漏一步不会被类型系统阻止。

## 2. 决策

引入一个不可绕开的原子入口：

```python
@dataclass(frozen=True)
class ValidatedStateSnapshot:
    source_digest: str
    artifact_hashes: Mapping[str, str]
    ghost: GhostRect
    blocked_cells_digest: str
    exterior_blocks_digest: str
    oracle_capabilities: frozenset[str]
    family_inputs: Mapping[str, object]

@dataclass(frozen=True)
class ConstraintPlan:
    family: str
    schema_version: int
    semantic_fingerprint: str
    model_scope: ModelScope
    operation: str
    parameters: Mapping[str, object]

@dataclass(frozen=True)
class CompiledCut:
    cut_id: str
    proof_digest: str
    scope_digest: str
    snapshot_digest: str
    plan: ConstraintPlan

ValidateAndCompileResult = CompiledCut | CutRejection


def validate_and_compile_cut(
    envelope: CutEnvelope,
    snapshot: ValidatedStateSnapshot,
    registry: FamilyCapabilityRegistry,
) -> ValidateAndCompileResult:
    ...
```

`CompiledCut` 的构造器不公开。只有 `validate_and_compile_cut()` 可以创建它。master 只接受 `CompiledCut`，不再接受原始 `Cut`。

## 3. Cut schema v2

v2 不再保存两份平行真相。建议形态：

```python
@dataclass(frozen=True)
class CutEnvelope:
    cut_id: str
    family: str
    family_schema_version: int
    proof_payload: bytes
    proof_hash: str
    scope: ScopeManifest
    provenance: CutProvenance
```

body 是 proof 的规范化投影，不作为第二份可写字段。用于展示、evaluate 或编译的 body 都由 family plugin 的纯函数生成：

```python
proof = plugin.parse_and_validate_proof(envelope.proof_payload, snapshot)
body = plugin.derive_body(proof)
plan = plugin.compile(body, proof, snapshot)
plugin.validate_plan(plan, proof, snapshot)
```

v1 兼容层可以继续接收 `geometric_payload`/`literals`，但必须先验证其与 proof 的规范投影严格相等，再丢弃 v1 body。补丁 0001 是这个兼容层的最低限度封口，不是最终架构。

## 4. ScopeManifest 必须声明完整依赖

当前 `artifact_hashes` 是由 cut 自报的字典，subset 校验使 cut 能删除不利依赖。v2 改为 family schema 定义依赖名，cut 只携带值：

```python
@dataclass(frozen=True)
class ScopeManifest:
    scope_schema_version: int
    family: str
    ghost_policy: Literal["agnostic", "bound"]
    ghost_rect_digest: str | None
    blocked_cells_digest: str | None
    exterior_blocks_digest: str
    source_digest: str
    dependency_hashes: tuple[DependencyHash, ...]
    oracle_abstraction_version: str
    assumptions: tuple[Assumption, ...]
```

registry 中的 family manifest 给出 `required_dependencies`。验证采用集合严格相等：缺项、多项、重复项、未知项都拒绝。所有 proof 边界 digest 使用完整 SHA-256，不截断为 64 bit。若某个 digest 只用于缓存，可另设 `cache_key_64`，不能与 proof identity 共用字段。

补丁 0003 对 schema v1 使用“完整 artifact map 严格相等”作为保守止血。长期应按 family 精确依赖，以免无关 artifact 变化造成全量失效。

## 5. FamilyCapabilityRegistry 取代“冻结 9 族”

family 的数学语义可以冻结，但 family 数量不应成为不变量。建议显式状态：

```python
class CapabilityStage(Enum):
    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"
    COMPILABLE = "compilable"
    ENABLED = "enabled"
    RETIRED = "retired"

@dataclass(frozen=True)
class FamilyCapability:
    name: str
    mode: Literal["literal", "geometric"]
    proof_schema_version: int
    validator_version: str
    compiler_version: str | None
    stage: CapabilityStage
    required_dependencies: frozenset[str]
```

registry 是 code-generated authority，CI 校验 validator、compiler、测试和文档声明一致。F8 可正常标记 RETIRED，而不需要同时维护“不可删”与“已删除”两套权威。

## 6. 实际 TCB 声明

建议把“validator 唯一 trust point”替换为：

> Cut generator 与搜索 oracle 均不可信。可信计算基包括 snapshot builder、canonical/schema parser、family proof verifier、typed compiler、master apply adapter、model-scope binding，以及发布前 replay。所有组件必须最小化、版本化、可独立测试；任何失败均不得产生 master mutation。

master mutation 前的顺序固定为：

1. 冻结 snapshot，并计算 snapshot digest。
2. envelope schema 与完整性校验。
3. scope 完整性与 currentness 校验。
4. family proof 独立验证。
5. 从已验证 proof 派生 body 与 ConstraintPlan。
6. plan 防御性复验。
7. 记录 PREPARED ledger event。
8. master 原子 apply，记录 APPLIED event。

步骤 1 至 6 全部是纯函数，不能调用 master mutation。步骤 8 失败时不能留下部分约束；每个 master adapter 要么先完整解析和解析所有变量再 Add，要么通过 builder transaction/模型重建保证原子性。

## 7. 数据类型硬化

建议新增：

```python
@dataclass(frozen=True)
class GhostRect:
    x: int
    y: int
    width: int
    height: int

@dataclass(frozen=True)
class GroupSnapshot:
    group_id: str
    demand: int
    pose_domain: frozenset[str]
    selected_poses: tuple[str, ...]
```

`ValidatedStateSnapshot` 只能由 builder 在完整校验后创建，内部 collection 使用不可变容器。这样可消除宽高位置错误和验证后状态被原地改写的 TOCTOU。

## 8. 迁移顺序与代价

阶段 A，约 1 至 2 人日：应用补丁 0001 至 0003，生产入口改为单函数 wrapper，Step 8 再做完整性防御；保持 v1 schema。

阶段 B，约 3 至 5 人日：实现 snapshot、registry、ConstraintPlan，迁移 F1/F6/F7。三族 compiler 相对直接，先不迁移 F5。

阶段 C，约 3 至 7 人日：按 RFC-002 迁移 F5；删除生产调用方对 adapter registry 的依赖。

阶段 D，约 2 至 4 人日：切换持久化 schema v2，保留只读 v1 importer，生成 capability manifest 和文档表。

全量活跃四族迁移的量级约 5 至 9 人日，取决于现有 reseal 和发布门成本。若连同 ledger/model epoch 一并做，见 RFC-003。

## 9. 必须增加的测试

1. validator 读取的 proof 与 compiler 读取的 proof 必须是同一个不可变对象。
2. 任意 envelope bit flip、body/proof 漂移、依赖缺项都不得调用 master。
3. snapshot 构造后修改输入 dict/list 不得改变 snapshot digest。
4. 非方形 ghost 的 width/height round-trip。
5. registry 中 ENABLED family 必须同时有 verifier、compiler、master adapter 和恶意输入测试。
6. 对每个 family 做 differential test：ConstraintPlan 的语义与 master adapter 实际约束在小实例上等价。
