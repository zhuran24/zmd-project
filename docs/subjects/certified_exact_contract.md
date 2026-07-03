# Certified exact contract

`certified_exact` 与 `exploratory` 是分离路径。exact 目标为 `max_lex(area, min_side)`，`min_side >= 6` 是候选 admissibility。flow 子问题只提供诊断，不是 certified gate。

冻结 source-of-truth 输入包括：

- `rules/canonical_rules.json`
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

当前工作树包含 `candidate_placements.json`，大小 `45,774,305` bytes，SHA256 `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`。其它发行包省略该文件时，必须在运行前恢复相同字节。拐角修复前的 `45,773,799` bytes / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本已被取代且 hash-incompatible。旧 SHA256 `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` 已被取代。

候选级 strong status、terminal result 和公开 artifacts 的完整 authority 规则见 `PROJECT_LOCK.md`。特别是 producer 的 in-memory 返回值、generic writer、viewer 或 adapter 都不能单独授予 proof-bearing `CERTIFIED`。
