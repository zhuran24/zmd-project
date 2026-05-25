# Validation

已在当前容器中使用 `zmd_deps_v3.zip` 提供的本地 wheel 依赖运行验证。没有使用新增硬件、商业软件或付费云资源。

## 命令与结果

```bash
python -m py_compile src/search/benders_loop.py src/models/master_model.py src/models/exact_coordinate_master.py scripts/preflight_gate.py src/tests/test_ghost_anchor_filter.py src/tests/test_anchor_slice_resume_manifest.py
# [OK] py_compile modified files

python -m ruff check src/search/benders_loop.py src/models/master_model.py src/models/exact_coordinate_master.py scripts/preflight_gate.py src/tests/test_ghost_anchor_filter.py src/tests/test_anchor_slice_resume_manifest.py
# All checks passed!

python -m compileall -q src scripts
# [OK] compileall src scripts

python -m pytest -q -p no:randomly src/tests/test_anchor_slice_resume_manifest.py src/tests/test_ghost_anchor_filter.py src/tests/test_benders_cut_replay_condition_lifecycle.py src/tests/test_master_hint_persistence.py src/tests/test_exact_outer_skip_unknown.py src/tests/test_master_extract_bound_state.py src/tests/test_exact_campaign_bound_state.py src/tests/test_lbbd_epsilon_stage_tag.py
# 61 passed
```

## 说明

当前环境的 `pytest-randomly` 插件会在测试启动阶段触发外部库 seed 范围异常，所以验证命令使用 `-p no:randomly` 隔离该插件。相关代码路径、切片 manifest、cut replay、hint persistence、outer unknown 语义和 exact campaign 状态测试均已通过。

未在本次交付中运行 70x70 生产级长时 campaign，因此没有声称已拿到最终游戏解或完成 14h/168h 实测。补丁目标是提供严格安全的搜索树降难机制。
