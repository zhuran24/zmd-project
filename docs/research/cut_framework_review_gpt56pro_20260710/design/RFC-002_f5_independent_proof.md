# RFC-002：F5 改为可独立验证的 proof kind，移除 adapter 共同失效

状态：评审建议稿，不应盲目 apply。

## 1. 问题

F5 的 generator 经 `SubProblemOracleAdapter.query_liftable()` 得到 INFEASIBLE；validator 随后从同一个进程全局 registry 取回同名 adapter，再调用同一个 `query_liftable()`。这不是独立验证，只是第二次询问同一份实现。若 adapter 的数学逻辑、输入映射或依赖捕获有系统性错误，generator 与 validator 会共同接受错误结论。

当前第一个生产 adapter 还把 `group_id -> operation_type` 映射保存在构造时私有字段中。该映射不在 `LiftableScope`、CutScope 或 cert 中。生产代码按 adapter 名从全局 registry 复用已有实例，所以第二个 controller/session 可能复用上一份 mandatory_groups 映射。registry 的“同名幂等”实现实际是静默覆盖，也没有指纹检查。

因此，在“oracle 按 Byzantine 对待，validator 不调用 oracle”的原规范下，当前 F5 不满足 trust model。

## 2. 立即策略

在独立 proof verifier 落地前，F5 不应从 unsafe map 晋升。最保守做法是：

```python
ENABLED_CUT_FAMILIES = {"region_capacity", "shape_packing_hall", "power_hitting_set"}
# pattern_nogood waits for binding_empty_domain_v1 proof verifier
```

仍可在 shadow 模式生成 F5，记录 proof、拒绝原因和预期 plan，但不 mutate master。

## 3. 为 binding_empty_domain_v1 定义专用 proof

当前可 lift 的结论非常窄，适合直接做 proof-bearing family，而不是泛化成“可重问任意 subproblem oracle”。建议 cert：

```python
@dataclass(frozen=True)
class BindingEmptyDomainProofV1:
    proof_kind: Literal["binding_empty_domain_v1"]
    group_id: str
    operation_type: str
    facility_type: str
    pose_id: str
    pose_payload_hash: str
    operation_profile_hash: str
    required_input_slots: tuple[tuple[str, int], ...]
    required_output_slots: tuple[tuple[str, int], ...]
    input_port_cells: tuple[Cell, ...]
    output_port_cells: tuple[Cell, ...]
    enumeration_semantics_version: str
    binding_domain_count: Literal[0]
```

scope 必须绑定：mandatory group 的 operation_type 映射、operation profile 数据、candidate pose、canonical facility mapping，以及会改变 binding 枚举语义的所有 feature axis。不能把 mapping 藏在 adapter 实例里。

## 4. 独立 verifier

新增一个无 registry、无 callback、无环境变量读取的 verifier，例如：

```python
def verify_binding_empty_domain_v1(
    proof: BindingEmptyDomainProofV1,
    snapshot: ValidatedStateSnapshot,
) -> VerifiedPatternNogood | Rejection:
    # 1. 从 snapshot 重新取 group/op/facility/pose/profile，并与 proof 哈希一致
    # 2. 验证 operation_type 支持 exact pose-level binding
    # 3. 独立检查端口数量下界
    # 4. 用 verifier 自己的匹配/枚举实现证明不存在完整 binding
    # 5. 只产出单字面 presence nogood
```

“独立”至少要求 verifier 不调用 `SubProblemOracleAdapter.query_liftable()`，不读取 registry，不信任 adapter 的 witness。对于当前 empty-domain 结论，verifier 可用一个小型二分图匹配或穷举器直接证明 profile slot 与 pose port cell 之间不存在合法完全匹配。若复用 `enumerate_pose_level_port_bindings()`，该函数就必须被明确列入 TCB，并另外用第二实现做 differential tests；否则仍是共同失效。

当前 adapter 的结论通常能缩到单字面。对于单字面 proof，删除最小化与 canonical slot relabel 都不是安全性所需，可先绕开通用 F5 minimizer。未来接入真正多字面 pattern proof 时，再给每种 `proof_kind` 独立 verifier。

## 5. 去掉全局可变 registry

建议把 adapter registry 降级为 generator 侧插件，不参与 validator：

```python
class GeneratorPluginRegistry:
    def create(self, name: str, snapshot: ValidatedStateSnapshot) -> GeneratorPlugin:
        ...
```

每次按当前 snapshot 构建，实例不可跨 controller/session 复用。若出于性能必须缓存，cache key 至少包括：adapter name/version、source_digest、mandatory group operation mapping digest、feature-axis digest。注册同名不同指纹必须抛错，不能静默覆盖。

validator dispatch 则只按 cert `proof_kind` 进入闭集 proof verifier：

```python
PROOF_VERIFIERS = {
    "binding_empty_domain_v1": verify_binding_empty_domain_v1,
}
```

## 6. 通用 F5 的未来形态

若未来要保留多种 subproblem 产生的 pattern nogood，cert 必须携带可离线验证的 proof，而不是 adapter 名：

```text
pattern_nogood_v2
  forbidden_pattern
  proof_kind
  proof_payload
  scope_manifest
```

可接受的 proof kind 例子：

* `binding_empty_domain_v1`：独立枚举/匹配验证。
* `routing_cut_certificate_v1`：显式割或不可达 witness，独立图算法验证。
* `cp_unsat_core_v1`：若子求解器能输出可检查 proof，验证 proof；只给“INFEASIBLE”状态不够。

未知 proof kind 一律 HOLD/QUARANTINE，不调用外部 oracle尝试“看看能否重现”。

## 7. 红测

1. 恶意 adapter 对任何 core 都返回 INFEASIBLE，generator 可生成 shadow cut，但 verifier 必须拒绝。
2. adapter 构造时 mapping A，随后 state 使用 mapping B，proof 必须因 scope digest 不符拒绝。
3. 两个 controller 顺序运行，不得共享 adapter 私有映射。
4. 同名不同 version/fingerprint 注册必须抛错。
5. 环境变量在 generate 与 validate 之间变化，verifier 结果不受影响。
6. verifier 与生产 binding 枚举器在穷举小 pose/profile 集上 differential 等价。

## 8. 代价

仅为 `binding_empty_domain_v1` 写专用 proof、独立匹配 verifier和红测，约 2 至 4 人日。迁移成完整通用 proof-kind 框架约 4 至 7 人日。若要求通用 CP/路由子问题输出并验证正式 proof，量级可能上升到 1 至 3 周，取决于求解器可提供的证据格式。
