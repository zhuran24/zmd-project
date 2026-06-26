# 19 — 实施 rhythm (Phase 1.1 经验)

> **流程建议**：本文件不是当前状态表；phase/测试结论须回查权威状态与实际日志。


每 commit 后立刻 Gemini cross-check ([[gemini-review-algorithm-math]]).
大节点 (Phase 1.2 入门收尾 / Phase 1.2 5 family 全 land / Phase 1.3 集成 land)
打包给 GPT pro batch audit ([[big-milestone-gpt-pro-review]]).

每轮 audit:
- prompt 跟 zip 单独给 ([[review-pkg-no-prompt-inside]])
- 包内只放事实素材, 不放 verdict claim / Close 列表 / 引导 reviewer 句
- response 收到立刻 cp 进 `docs/research/.../external_review/`
  ([[external-review-reproducibility]])
- finding 必先 reproduce verify 才 archive
  ([[audit-verify-before-archive]])

---

