---
name: gpt-delivery-dont-track-model-downgrade
description: "别手动复盘「是不是真 Pro/降没降级」也别挂嘴边(2026-06-14 owner 嫌烦,原话「你不要一直关注是不是真pro,一直关注很烦」)——dispatch 两端自动校验:发送侧 verify_model 校验选择器是 Pro 扩展、接收侧 collect() 复核回复 model-slug 含 pro + 生成时长 ≥ min-gen-seconds(默认 300s),任一不符并入 suspected_downgrade → exit 5;拿到回包默认信脚本:exit 0 = 模型没问题直接验收内容,只在真报 exit 5 时才提、才走 Claude-in-Chrome 插件托底重发"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

**模型对不对/降没降级是脚本的活, 别手动复盘也别挂嘴边 (2026-06-14 owner 嫌烦, 原话"你不要一直关注是不是真pro,一直关注很烦")**: dispatch 两端都校验——**发送侧** `verify_model` 校验模型选择器是 "Pro 扩展"(非则真点「智能水平」菜单切过去); **接收侧** `collect()` 复核回复 model-slug 含 "pro"(不符返回 model_mismatch)+ 生成时长 ≥ `min-gen-seconds`(默认 300s), 任一不符并入 `suspected_downgrade` → **exit 5**(交付不可信)。

所以拿到回包**默认信脚本**: exit 0 = 模型没问题, 直接验收内容。**别每次报告都念叨"真 Pro / 没降级"**——只在脚本真报 exit 5(疑似降级)时才提、才走 Claude-in-Chrome 插件通道托底重发。一直手动盯模型 = owner 嫌烦的"迷信式关注"。

母节点 [[gpt-delivery-no-blind-trust]]。
