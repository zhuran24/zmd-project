# B Component 4: Bitset kernel 选型

## 为什么需要 high-perf bitset

70 × 70 grid = 4900 cells. cell set 操作是 B 设计 hot path:

- propagation 时 `placement.cells & free_mask` (cell exclusivity check)
- cut resolve 时 `cells(p) ∩ cut.region` (region capacity 检查)
- backtrack 时 `cell_owner` undo (state rewind)
- cross-candidate replay 时 cell mask 比对

4900 bit = **77 × 64-bit words**. 一次位运算 1 word ~ 1 ns native, Python
list 操作 ~ 100 ns each cell, 总差 **100×**.

PoC 阶段每 candidate 调 cut store ~10K-100K resolve 次, 每次 ~ 10 bitset
op. native bitset = ~ 1-10 ms per candidate; Python list bitset = ~ 100 ms
- 1 s per candidate. 27 anchor × ~ 0.5 s 差 = ~15 s/sweep 差 — PoC 可接受.

168h production campaign 跑 ~ 1000 anchor × 0.5s = ~10 min/sweep 差 — 仍可
接受. 但 cut store size 可能 10K-100K cut, resolve N × M scale 后差距放大,
production 阶段 native 必需.

## 选项对比

### Option A: Rust pyo3

```rust
#[pyclass]
struct Bitset(Vec<u64>);

#[pymethods]
impl Bitset {
    fn and(&self, other: &Bitset) -> PyResult<Bitset> {
        Ok(Bitset(self.0.iter().zip(other.0.iter()).map(|(a, b)| a & b).collect()))
    }
    // ...
}
```

**Pro**:
- 性能 native (Rust 跟 C++ 同 tier)
- memory safe (rustc 编译期防 segfault)
- pyo3 build infra mature, `maturin build --release` 一键
- 跨 platform binary wheels (linux/macos/win)
- 项目 dev 团队没 Rust 经验是劣势但学习曲线 ~1 week 起步

**Con**:
- Rust 学习曲线
- build pipeline 加 rustc 依赖 (CI/CD 要装 Rust toolchain)
- debug 难度比 numpy 高

### Option B: C++ pybind11

```cpp
class Bitset {
    std::vector<uint64_t> words;
public:
    Bitset operator&(const Bitset& other) const {
        Bitset result;
        for (size_t i = 0; i < words.size(); ++i)
            result.words[i] = words[i] & other.words[i];
        return result;
    }
};

PYBIND11_MODULE(bitset_cpp, m) {
    py::class_<Bitset>(m, "Bitset")
        .def(py::init<>())
        .def("and_", &Bitset::operator&);
}
```

**Pro**:
- 性能跟 Rust 同 tier (modern compiler 优化几乎一样)
- 项目 dev 团队 C++ 经验 likely 比 Rust 多
- pybind11 mature, 大量 OSS project 用 (numpy/scipy/PyTorch 部分)
- SIMD intrinsics 直接可用 (e.g. `__m256i` 一次 256 bit)

**Con**:
- memory unsafe (segfault 风险)
- build pipeline 加 C++ compiler 依赖
- header-only library complexity (template heavy)

### Option C: numpy uint64 array

```python
import numpy as np

class Bitset:
    def __init__(self, n_cells=4900):
        self.words = np.zeros((n_cells + 63) // 64, dtype=np.uint64)
    
    def __and__(self, other):
        result = Bitset(0)
        result.words = self.words & other.words
        return result
```

**Pro**:
- 0 external dependency (numpy 项目已用)
- 0 build pipeline 改动
- Python-level debug 容易
- numpy 内部 C-impl SIMD 部分自动用

**Con**:
- 性能 ~ 10-20% native (numpy overhead per op ~ 1 μs)
- 对大量小 op 不利 (e.g. resolve 时 inner loop 调 100 次 `and`)
- 无法用 SIMD intrinsics 直接控
- Python GIL 限制并发 (Rust/C++ 可释放 GIL)

### Option D (混合): numpy PoC + Rust/C++ production

PoC 阶段用 numpy 验算法正确, hot path 识别后换 Rust/C++. 这是 scipy 等
大型 project 的常见路径.

**Pro**:
- PoC 启动 0 ramp-up
- 性能 profile 后再 optimize, 避免过度工程
- Rust/C++ work 留到算法稳定后 (避免重写)

**Con**:
- 双语言维护 (PoC 跟 production 不一致)
- 切换时机难判 (过晚 → numpy 成 bottleneck 久; 过早 → 算法还在变)

## 项目方倾向

**项目方判断: 倾向 Option D (numpy PoC + Rust/C++ production)**, 因为:

1. PoC 阶段算法正确性 > 性能. numpy 调试容易, 让重点放在 cut family 正
   确性 + master state machine sound
2. PoC 性能 ~ 1 s / candidate 仍可接受 (27 anchor × 1 s = 27 s/sweep, 168
   h campaign 内可忽略)
3. Production 切到 native 时, 算法 contract 已稳, rewrite 在 well-defined
   interface 内
4. Rust vs C++ 在 production 阶段决定:
   - 若团队有 Rust 经验 → Rust pyo3 (memory safety + build infra)
   - 若团队偏 C++ → pybind11 + SIMD intrinsic
   - 项目方目前**没强偏好**, 待 PoC 阶段 profile + 团队 skill 评估再定

## Stress test 视角

- numpy PoC 是否够 production scale 跑通? 不够的话, 哪个 hot path 是切
  native 的关键 lever?
- Rust 跟 C++ 在此 problem 上的实际性能差是否显著? (e.g. SIMD intrinsics
  在 4900-bit bitset 上是否有意义)
- 70×70 grid 是否还有更高效的 spatial data structure? (e.g. quadtree /
  Morton order)
- 跨 candidate replay 时 bitset 持久化序列化 schema?

## 跟现有 src 的关系

现有 `src/models/master_model.py` + `pose_bool_exact_master.py` 用 CP-SAT
自己内部 propagator, 没显式 bitset 数据结构. B 设计 bitset kernel 是新
组件, 不复用现有 src 内部.

但 candidate placement preprocessing `data/preprocessed/candidate_placements.json`
内 pose 已 cell list 形式, 可在 PoC 阶段直接转 bitset 不需要重新 generate.

## 实施 phase 建议

- **PoC Phase 1-3 (master state machine + 5 cut family 实施)**: numpy uint64
- **Production Phase 4+ (端到端 sweep + 性能 profile)**: profile hot path
  → 决定 Rust 或 C++
- **168h campaign 切到 native (Phase 5+)**: 完整 rewrite hot path 模块

## 风险评估

- numpy PoC 性能 ~ 10x slower than native — PoC 阶段可接受
- 切 native 时 schema 兼容: numpy bitset interface 设计成 abstract, native
  实施按相同 interface
- bitset 大小 4900 bit 对所有 3 选项都 trivial (memory 几 MB even 100K cuts)

## 不确定性

- 4900 bit 不是大数据 — bitset 性能可能不是 bottleneck, 真正 bottleneck
  在算法 (e.g. component reachability cut 跑 Tarjan)
- → stress test 可以验是否 bitset kernel 选型是 premature optimization,
  应优先 profile 算法 hot path 再选 kernel
