# certified_exact 求解器 soundness 白板审查

这个项目是一个对外打 CERTIFIED 标签的精确求解器:在 70×70 网格上,放置一组强制设施后,求面积最大的空矩形,目标是 `max_lex(area, min_side)`。

看一下项目里有没有任何会让它的 CERTIFIED 结论变成假话的正确性(soundness)问题——它报 CERTIFIED 的解,要么其实不可行,要么其实存在一个被它漏掉的、面积更大的可行矩形。

包在本 Project 文件区:`zmd_v80_impl_full_20260616_single.zip` / sha256 `f85fe62eb36d17aafcf5dfafaaaa47637fbf7bbb8589c9815bf9da87ec91ddc6`。包根有一张代码导航图 `NAV_MAP.md`。
