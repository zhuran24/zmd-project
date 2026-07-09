# 批 1F 前置侦察：生产 replay 基建现成度（2026-07-10 主会话核查）

> 任务书 §七.6：w6/cgroup 硬帽跑 b0_4r 等价 replay 或完整 certified smoke，记录
> wall/RSS/proof_summary/terminal verifier，worker 上限进 production profile/wrapper。
> 本稿 = 实施前的现状核查与形态拍板草案；1F 规格书在 1D/1E 收口后定稿。

## 现状核查（2026-07-10，HEAD ce6f703）

| 基建 | 现状 | 1F 要做 |
|---|---|---|
| `scripts/run_campaign_linux.sh` | 有 `--resume-campaign` 自动注入；**无 systemd-run/MemoryMax 硬帽、无 worker 上限** | 加 cgroup 硬帽包装 + 默认 w6 注入 |
| worker env 通道 | `EXACT_MASTER_CP_SAT_WORKERS`（stage 专属）/`EXACT_CP_SAT_WORKERS` 均在 operational allowlist | 现成，wrapper 注入 `EXACT_MASTER_CP_SAT_WORKERS=6`（显式 env 已设时不覆盖） |
| cgroup 配方 | 环境卡实证：`systemd-run --user --unit=<名> -p MemoryMax=<N>G -p MemorySwapMax=0`（b0_6 拦下 43.9GB 尖峰） | 直接复用；验尸走 `journalctl --user -u <名>`；监控兼 `systemctl --user is-active` 判死（OOM 杀进程组，done 标记写不出来） |
| readiness gate OOM 模型 | `WORKER_PEAK_RSS_GIB` 还是 witness 30GB 时代估值 | 1F 按 C1 实测更新（稳态 11-16.6GB + 解附近 3 秒 +26GB 事件尖峰；w6 安全/w12 两连死/w24 42G 帽 9min 击穿） |
| RSS 采样 | `~/m5_runs/` 有 b0_6 的 rss.log 采样先例脚本 | 复用采样间隔与格式（尖峰是 3 秒级，采样 ≤1s） |

## 形态拍板草案（倾向，1F 规格书定稿）

1. **完整 certified smoke 优于 b0_4r 复刻**：1D 后 C1 已是 certified 默认，直接
   `run_campaign_linux.sh` 跑 `main.py --mode certified_exact` 短 campaign（w6+硬帽），
   终点 CANDIDATE_PROPOSED——比复刻 monkeypatch 原型的 b0_4r 更贴 1F 验收本意
   （proof_summary 含 power_pole_dominance、terminal verifier、可重放全链一次走真）。
   b0_4r 的 6×6 OPTIMAL@541s 作为 wall-clock 参考锚（w6、同机、硬件状态注意 BIOS/硅脂档案）。
2. **硬帽参数**：MemoryMax=42G（b0_6 同值，系统 47.7GB 留 5.7G host 余量）+
   MemorySwapMax=0；w6。**一次只跑一个 master solve**（铁律，双发=OOM 双杀实测）。
3. **验收边界**：w6 不 OOM + 剪杆后 solution 过 terminal verifier + proof artifacts 可重放；
   w12/w24 只进 optional perf lane（cgroup 硬帽+OOM 预期记录），不作 release gate。
4. wrapper 手术属 sealed 面吗——`run_campaign_linux.sh` 不在 close-kernel pin 表
   （实施时复核），但 readiness gate（`production_readiness_gate.py`）改 RSS 模型
   要查 pin。1F 规格书列 reseal 面。

## 依赖顺序

1D（C1 默认化——smoke 跑的就是 C1）→ 1E（义务层——smoke 产出的 proof 材料按新义务校验）→ 1F。
1F 是批 1 收口批：跑完向 owner 交批 1 完成战报 + M5 A/B 解锁通知。
