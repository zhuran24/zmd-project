/-!
# 计量与基础

规则文件「计量与基础」一块里的时间单位。空间单位、蓝图、旋转、设定还没写。
-/

namespace Endfield

/-- 步：每 1/8 tick 为一步；玩家的操作只能在两步之间进行

模型里的时刻和时长都用步数。 -/
abbrev «步» := Nat

/-- 时间单位：tick

1 tick 是 8 步。 -/
def «tick» : «步» := 8

end Endfield
