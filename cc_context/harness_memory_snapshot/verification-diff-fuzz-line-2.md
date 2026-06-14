---
name: verification-diff-fuzz-line-2
description: "certified 验证加固阶梯第②线「差分对拍 fuzz」(CC 自建本地零外发, 唯一不受 reviewer 能力上限约束的层): 随机小实例 + 独立朴素 oracle 对拍 CP-SAT routing/master certified 路径; 切片1 routing 连通 ~1200 实例 + 切片2 master 几何 ~1760 实例零不一致; 含 sink-front 极性反向重大教训 + pinned-pool 二次裁决滤假阳性 + 验证器独立性铁律。"
metadata: 
  node_type: memory
  type: project
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

第②线 = certified soundness 验证加固阶梯里的「差分对拍 fuzz」。

## ② 差分对拍 fuzz (CC 自建, 本地零外发)
随机小实例生成器 + 独立朴素验证器 (暴力可达 / 重叠 / 小实例最优性穷举) 自动对拍 CP-SAT certified 路径, 不一致 = 必有 bug。**不依赖任何 AI 能力, A-1 类全局连通 bug 机械必抓**——这是唯一不受 reviewer 能力上限约束的一层。
- **切片 1 已落地 (2026-06-12, commit c2e7394)**: `cc_context/verification/diff_fuzz/routing_connectivity_diff.py` — 独立验证器自重导 port-front 几何 + 裸 BFS (零共享 guard 代码), self-test 含 A-1 dead-end 必抓案例, 首批 100 随机实例对拍零不一致。坑: sink-front 状态约定是 `flow_out = port.dir` (几何上"背对"port), 真路径必须绕到 front 格的另一侧进入——独立实现时别按直觉几何想当然。
- **切片 2 已落地 (2026-06-12, auto-checkpoint 06eb068)**: `cc_context/verification/diff_fuzz/master_geometry_diff.py` — master no-overlap/bounds/电力覆盖独立验证 (只看选中 pose 真实 occupied_cells, 不碰 master interval 逻辑); 非方形模板横竖 pose 覆盖 B-01 命中点。self-test 4 格 (含 B-01 竖向 4x6 重叠必抓) 过; seed 0-5 共 ~440 实例 forward/reverse mismatch 全 0。**关键方法论坑 (reverse 方向)**: 抓 false-INFEASIBLE 要求验证器完整编码全部可行性约束, 但 exact master 的核心是「ghost 空矩形」约束 (占满全网格→无空矩形→正确 INFEASIBLE), 独立复现它≈重写半个 master → 验证器漏它会**诬陷 master over-cut**。解法 = **嫌疑 witness 缩成 pinned pool 重喂 master 做二次裁决**: 仅 pinned 仍 FEASIBLE 才算真 over-cut, pinned INFEASIBLE = 验证器不全的假阳性自动过滤 (实测 13 个假阳性全过滤干净)。诚实边界: 故 slice2 的 forward 方向 (false-CERTIFIED) 稳健, reverse 方向靠 master 自裁兜底。
- **累计战绩 (2026-06-12 上午)**: 切片 1 累计 **900 实例零不一致** (含 F04-R4 落地后复跑 150); 切片 2 累计 **~1760 实例零不一致** (pinned 裁决累计滤 28 假阳性)。**无线箱形态已加进 master 切片生成器** (方形无端口单朝向全 anchor, 镜像 post-F-01 协议箱几何, wireless_mode ~50% 掺入; seeds 100-105 共 360 实例其中 168 含箱形态, 全净; commit 7a229c1)。工具包 README = `cc_context/verification/diff_fuzz/README.md`。
- **⚠️ 重大方法论教训 (2026-06-12 夜, F-RT-R2-01)**: 切片 1 的 900 历史实例对 **sink front 极性反向**类 bug 全盲 — oracle 的 sink front 方向键**从实现抄了同一个反向语义** (上面那条 2026-06-12 早间记的「坑: sink-front 状态约定是 flow_out = port.dir」**本身就是被实现带歪的错误理解**, 正确语义 = front 朝 connector 送料 `Opp(dir)`)。**验证器任何字段语义只要是「从实现学来的」就在该字段上失去独立性**——独立性要求从规则文本独立推导。face 3 外审抓出实现+oracle 同源反向后两边一起修 (commit b48728b), 修后 200 新实例 (seeds 200/300) 零不一致。lock 已新增 F-RT-R2-01 条款写明极性与验证器独立性要求。
- **connector 时代续跑 (2026-06-13 凌晨)**: F-RT-R3-01 (connector cell 可当 belt 格穿过, live false-FEASIBLE) 修复时 oracle **独立**新增 connector 占用检查 (从规则推导非抄实现) + self-test 场景; 修后再跑 200 (seeds 400/500) + F-RT-R4 双修后 100 (seed 600) 全零不一致。切片 1 累计 ~1200 实例。
- 待做切片: 仅剩 binding oracle (难)。
