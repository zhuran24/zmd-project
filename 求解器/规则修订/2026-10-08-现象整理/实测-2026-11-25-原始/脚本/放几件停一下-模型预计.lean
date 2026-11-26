import Endfield.«回放».«准入口周期»
namespace Endfield.«回放».«准入口周期»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 布局乙。下游准入口每 5 tick 上限 k；上游的先设累计上限 m（连着放 m 件就停），货源箱放满；
走 `隔` 步以后把累计上限关掉（接着连续来货），再走 n 步。各件到收货箱的秒数，相对头一件。 -/
def «放几件停一下» (k m «隔» n : Nat) : Option (List Nat) := do
  let s ← «乙».bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 30 (some .«蓝铁矿») none (some k)))
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«蓝铁矿») (some m) none))
  let s ← «做» s (.«原样» (.«放货» 2 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let «走着记» (m : Endfield.«状态») (n : Nat) : Endfield.«状态» × List Nat :=
    (List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 50 .«蓝铁矿»])) (m, [])
  let (m', a) := «走着记» s.«模型» «隔»
  let s ← «做» { s with «模型» := m' } (.«原样» (.«设准入口» 31 (some .«蓝铁矿») none none))
  let (_, b) := «走着记» s.«模型» n
  return («相对头一件» («到的步» (a ++ b))).map (· / 4)

-- 上限 2，先连着放 4 件，第 5 件在头一件之后 g 秒才到下游的准入口（g = 16…24）
#eval ([16, 17, 18, 19, 20, 21, 22, 23, 24].map fun g => (g, «放几件停一下» 2 4 (g * 4 + 8) 150))
-- 上限 3，先连着放 6 件
#eval ([18, 19, 20, 21, 22, 23, 24, 25, 26].map fun g => (g, «放几件停一下» 3 6 (g * 4 + 8) 150))
end Endfield.«回放».«准入口周期»
