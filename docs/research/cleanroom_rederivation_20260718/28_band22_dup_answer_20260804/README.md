# w0_band22_holes 咨询答复包

本包按原咨询包 `00_ASK.md` 的交付要求整理，并吸收委托方 2026-08-04 给出的三处数字勘误。

主要文件：

- `w0_band22_holes_consultation_response.md`：完整咨询报告。
- `w0_band22_local_patch_01_03.json`：洞①与洞③共用的机器可读坐标补丁。
- `validate_w0_local_patch.py`：局部补丁的独立算术与骨架校验器。
- `validate_w0_local_patch_output.txt`：上述校验器的运行输出。
- `verify_w0_direct4_power_obstruction.py`：洞②供电不可行证明的有限状态复核器，覆盖模型 A/B。
- `verify_w0_direct4_power_obstruction_output.txt`：上述证明脚本的运行输出。
- `authority_06_problem_instance.json`：原包权威实例 JSON 的副本。
- `recompute_rerun.txt`：原包 `05_recompute_check.py` 的复跑输出。
- `SHA256SUMS`：本目录文件校验和。

注意：局部补丁校验器不检查供电覆盖、operation-to-port 绑定或完整 strict connectivity。完整报告明确说明，洞①和洞③虽有坐标级局部修复，但该相邻 4+4 直连宏族在报告所述带内杆口径下被洞②的供电定理判死，因此本包不是完整可行 witness。
