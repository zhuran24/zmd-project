# 本地可选证据根

`.artifacts/` 保存可能不随轻量 checkout 分发的实验、外审、收据和交付工件。它们属于 evidence，不会因文件存在、测试通过或目录名称而自动获得 owner、rules、research-authority 或 production authority。

一级目录由 [`data/knowledge/dossiers.json`](../data/knowledge/dossiers.json) 登记。某个 dossier 是否已经完成语义审阅，应查 [`docs/BACKFILL_LEDGER.md`](../docs/BACKFILL_LEDGER.md) 与 `backfill_reviews.jsonl`；尚未审阅的目录必须进入 `backfill_triage.json`，而 triage 只表示可发现和待处理，不表示没有可复用结论。

历史或关闭后的 artifact 正文原则上冻结。更正通过新的 claim、decision、erratum、validity event 或 superseding dossier 表达。

## 新 local-optional package

新增本机证据包时，先准备真实 package manifest 和稳定恢复说明，再运行：

```bash
.venv/bin/python devtools/docctl.py register-local-evidence .artifacts/<package> \
  --title "<title>" --manifest-path .artifacts/<package>/<manifest> \
  --recovery-instructions .artifacts/README.md --topic <topic>
```

登记会计算 manifest SHA-256，并以 active `local_optional` workflow 写入中央 dossier ledger。轻量 checkout 可以缺 payload，但不能用空占位、伪造摘要或不可执行的恢复说明换取绿色检查。完成语义审阅后，使用与 tracked research 相同的 typed closure 流程关闭。
