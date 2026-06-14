---
name: fact-forcing-function-required
description: "抽象事实: 反复复发的行为/状态漂移不能靠再写一条更强规则根治; 需要 hook、test、gate、stamp、生成器等 forcing function,规则只做 fallback。"
metadata:
  node_type: memory
  type: fact
---

## 抽象事实

对反复复发的动作漏做、状态漏更、投影漂移、数字散抄，"再记一条更强规则"通常治不住。被动文本只在被召回且被正确执行时才生效；压力一来，旧病会换措辞复发。

根治要把正确动作做成 forcing function：hook 拦截、pytest/gate 报红、stamp 自动生成、单一来源生成投影、pre-push 物理挡、schema/check 让漂移无法静默进入仓库。规则仍要写，但它是解释和 fallback，不是主刹车。

## 首批投影

- [[authoritative-numbers-single-source]] — 数字 core-node + projection + gate 的既有经验。
- [[memory-tree-structural-health]] — link/MEMORY/live mirror/INSTANCE 这些结构病要机器查。
- [[memory-currency-protocol]] — living 现状靠 subject/projection/stamp,不是散文自觉。
- [[zmd-env-ci-gate]] / [[zmd-env-prepush-gate]] — push 前后都让漏做自动变红。
