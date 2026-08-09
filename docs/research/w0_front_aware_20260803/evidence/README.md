# G1 两个 master run root 的仓内副本（字节原样）

`RESULT.md` 的每个数字都来自这两个运行根。它们原本只存在于单机根盘的
`.artifacts/`（未跟踪、权限 700），所以这里放一份**字节原样**的副本进 git。

- **性质**：research-only 证据副本。authority 布尔恒 false，不携带任何界，`L` 不受影响。
- **副本不是新证据**：这些文件由 2026-08-03 的 `run_g1.py gate` 运行写出，本副本
  一个字节没改，也没有重跑。
- **原件不动**：`.artifacts/w0_front_aware_20260803/g1_run/stage_b/` 的两个 run root
  保持原样（它们的 root closure 是「这个目录恰好是这些文件」，多一个字节都会破）。

## 来源与 sha256

原路径前缀 = `/home/zhuran24/zmd-pj/.artifacts/w0_front_aware_20260803/g1_run/stage_b/`

| 本目录 | 原路径后缀 | 字节 | sha256 |
|---|---|---:|---|
| `L0/config.json` | `L0/config.json` | 1,325 | `45084d61f35d583ded355f74cceecbf5faeed58139dd02a9083e7df2a1777444` |
| `L0/gate.json` | `L0/gate.json` | 1,573 | `50bbcbe7a6fc7e27e903453c12a825045fee84a6227c8957e5d28a8fb414d584` |
| `L0/receipt.json` | `L0/receipt.json` | 1,909 | `9488483707b2ea7af04cd40ab91bd1a0ac3ff975feaffdc318c9d9658017e601` |
| `L0/master/pre_gate.json` | `L0/master/pre_gate.json` | 2,920 | `14436a93865f0672531290404946464304dfca1abdd2ceddd14fbd0a1288c1c7` |
| `L0/master/master_result.json` | `L0/master/master_result.json` | 2,560 | `d27cba2d2e48d8d6f35d1f91ede20d8a5a98f8ab7af2cd14af7d37aea6324bc6` |
| `L0/master/cpsat.log` | `L0/master/cpsat.log` | 11,574 | `423bbf16c9f7b1cc95c88bab2cbf4956666862eca8a6ee58ba05e542e89a39eb` |
| `L1_union/config.json` | `L1_union/config.json` | 2,939 | `26607b371aace98c787b4428db127fa81a8f3612c69bfe5ef84f65bcec7c0682` |
| `L1_union/gate.json` | `L1_union/gate.json` | 1,632 | `2ac5cff3095a2af784f99d245dbbfc7f37bede8985b79c17f472a6936d8d9bbe` |
| `L1_union/receipt.json` | `L1_union/receipt.json` | 1,998 | `b51863060d18d55a09d32041df14eca67bd785fc94e5cf8c8036d4fb01ec28bd` |
| `L1_union/master/pre_gate.json` | `L1_union/master/pre_gate.json` | 2,846 | `b5afa336f4893bdcc836387bbf650e49d43205c1d138886796b891ea610b4c70` |
| `L1_union/master/master_result.json` | `L1_union/master/master_result.json` | 4,051 | `3c6cc798ab801ae42a8ac7b9fda20348b57733f54a33b01e406e70f65200d94a` |
| `L1_union/master/cpsat.log` | `L1_union/master/cpsat.log` | 11,721 | `e9083525ba1a6a1a1fcb8f92ccad93a10e688d1d3dd1afb611bd2d23993503b1` |

复核一份副本：

```bash
sha256sum docs/research/w0_front_aware_20260803/evidence/L0/gate.json
cmp docs/research/w0_front_aware_20260803/evidence/L0/gate.json \
    /home/zhuran24/zmd-pj/.artifacts/w0_front_aware_20260803/g1_run/stage_b/L0/gate.json
```

## 读这些文件时要知道的两件事

1. **`receipt.json` 里的路径是原件的绝对路径。** receipt 的 identity graph 记的是
   run root 里每个工件的绝对路径 + sha256 + 字节数；副本换了位置，所以「按 receipt
   重放 identity graph」这件事只能在原机原路径上做。副本能独立证明的是它自己的
   sha256 与原件相等（上表），以及 receipt 内记录的 sha256 与同目录文件相符。
2. **`config.json` 里的 catalog 路径同样指向 `.artifacts/`。** catalog（1,354 签名，
   约 9 MB）不在本目录，也不进 git；它的 per-file sha256 记在 `config.json` 的
   `catalog_digests` 里，manifest sha256 见 `CATALOG_REPORT.md` §2。

## 这两个 run root 说了什么

一句话：两轮都是 `INFEASIBLE`，`registers_lower_bound: false`，authority 全 false。
完整判读在 `../RESULT.md`，措辞限定在 `../00_charter.md` §9。
