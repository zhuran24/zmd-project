import Endfield.«回放».«格子工具»
namespace T
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 一条直线往下：分流器 (27,17)、带 (27,18)、桥接器 (27,19)、n 格带、限速的准入口（上限 4）、紧贴的收货箱。
挡住的一支先放。给出各件进收货箱的整秒（头一件算 0）。 -/
def «各件» (n : Nat) (steps : Nat) : Option (List Nat) := do
  let base := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 6 31 16 (.«协议储存箱» .«右»),
    «摆» 2 27 17 (.«分流器» .«上»), «摆» 1 27 16 (.«传送带» .«上» .«下»)]
  let blocked := [«摆» 30 28 17 (.«传送带» .«左» .«右»), «摆» 33 29 17 (.«传送带» .«左» .«右»),
    «摆» 32 30 17 (.«传送带» .«左» .«右»), «摆» 31 28 17 (.«物品准入口» .«右»)]
  let clear := [«摆» 20 27 19 (.«桥接器» .«上»), «摆» 10 27 18 (.«传送带» .«上» .«下»)]
  let belts := (List.range n).map fun i => «摆» (41 + i) 27 (20 + i) (.«传送带» .«上» .«下»)
  let tail := [«摆» 45 27 (20 + n) (.«物品准入口» .«下»), «摆» 7 26 (21 + n) (.«协议储存箱» .«下»)]
  let s ← ((base ++ blocked ++ clear ++ belts ++ tail).mapM id).bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«源矿») none none))
  let s ← «做» s (.«原样» (.«设准入口» 45 (some .«蓝铁矿») none (some 4)))
  let s ← «做» s (.«原样» (.«放货» 0 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let r := ((List.range steps).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 7 .«蓝铁矿»])) (s.«模型», [])).2
  let ts := (((r.zip (0 :: r)).zipIdx.filter fun ((a, b), _) => a > b).map fun (_, i) => i + 1).map fun x => (x + 3) / 4
  return (ts.map fun x => x - ts.headD 0).take 18

#eval (0, «各件» 0 260)
#eval (1, «各件» 1 260)
#eval (2, «各件» 2 260)
#eval (3, «各件» 3 260)
#eval (4, «各件» 4 260)
end T
