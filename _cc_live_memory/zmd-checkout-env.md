---
name: zmd-checkout-env
description: zmd 当前 Windows checkout 环境事实索引——无 venv/Python/auto-push/pytest/CI/记忆同步等子主题, 见各子节点
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

zmd 项目当前 Windows checkout(`C:\claude pj\zmd_pj`)的环境事实总览(2026-06-10 盘点接手自 Codex,后续持续更新)。每条事实已拆成聚焦子节点以提高召回:

- [[zmd-env-checkout-location]] — 工作区路径 + 旧 D:\追光\zmd 已失效
- [[zmd-env-python]] — 无 .venv;主环境=python.org 3.13.14 的 `python`;--no-deps 克隆;商店版 python3.13 备份
- [[zmd-env-store-python-alias-pitfall]] — 商店 Python 自动升级弄坏 `python` alias 的坑 + pre-commit 误报 STALE
- [[zmd-env-exit-code-falsepass]] — PowerShell `&` + Write-Host 把 exit code 洗成 0 的假通过坑
- [[zmd-env-auto-push]] — post-commit hook 自动 push(commit ≈ 发布)
- [[zmd-env-memory-sync]] — pre-commit memory sync 现状 + 共维护文件手动双写三处
- [[zmd-env-candidate-placements]] — candidate_placements.json 外置/可再生 + 旧版带病不可作恢复源
- [[zmd-env-patch-dir]] — 补丁包/ 目录性质
- [[zmd-env-pytest-isolation]] — 全量 pytest 必须独占跑 + xdist 加速跑法
- [[zmd-env-test-baseline]] — 全量测试基线=全绿 + 今后 failed 无豁免
- [[zmd-env-ci-gate]] — CI preflight gate + pytest 盖不到的三类检查
- [[zmd-env-email-bomb]] — owner 邮件轰炸根因复盘 + 三层教训
- [[zmd-env-prepush-gate]] — 机械 pre-push 门禁 + 装机坑 + 残余敞口

相关:[[zmd-project-entry]]
