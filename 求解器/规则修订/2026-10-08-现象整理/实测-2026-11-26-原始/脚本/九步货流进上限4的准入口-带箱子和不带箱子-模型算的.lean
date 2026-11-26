import Endfield.«回放».«格子工具»
namespace T
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 挡住的一支先放；通畅的一支：一格带、桥接器、两格带，然后中间一段，再是限速准入口 45（紧贴收货箱 7）。
`箱` 为真：中间是仓储模式的箱子 5（中心 (27,23)），后面两格带；为假：中间是带子。 -/
def «件» («箱» : Bool) : Option (List «摆件») :=
  let base := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 6 31 16 (.«协议储存箱» .«右»),
    «摆» 2 27 17 (.«分流器» .«上»), «摆» 1 27 16 (.«传送带» .«上» .«下»)]
  let blocked := [«摆» 30 28 17 (.«传送带» .«左» .«右»), «摆» 33 29 17 (.«传送带» .«左» .«右»),
    «摆» 32 30 17 (.«传送带» .«左» .«右»), «摆» 31 28 17 (.«物品准入口» .«右»)]
  let clear := [«摆» 20 27 19 (.«桥接器» .«上»), «摆» 10 27 18 (.«传送带» .«上» .«下»),
    «摆» 41 27 20 (.«传送带» .«上» .«下»), «摆» 42 27 21 (.«传送带» .«上» .«下»)]
  let mid := if «箱» then [«摆» 5 26 22 (.«协议储存箱» .«下»)]
    else [«摆» 61 27 22 (.«传送带» .«上» .«下»), «摆» 62 27 23 (.«传送带» .«上» .«下»), «摆» 63 27 24 (.«传送带» .«上» .«下»)]
  let tail := [«摆» 7 30 24 (.«协议储存箱» .«右»), «摆» 50 27 25 (.«传送带» .«上» .«右»), «摆» 51 28 25 (.«传送带» .«左» .«右»),
    «摆» 45 29 25 (.«物品准入口» .«右»)]
  (base ++ blocked ++ clear ++ mid ++ tail).mapM id

def «各件» («箱» : Bool) (k : Option Nat) (n : Nat) : Option (List Nat) := do
  let s ← («件» «箱»).bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«源矿») none none))
  let s ← «做» s (.«原样» (.«设准入口» 45 (some .«蓝铁矿») none k))
  let s ← «做» s (.«原样» (.«放货» 0 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let r := ((List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 7 .«蓝铁矿»])) (s.«模型», [])).2
  let ts := (((r.zip (0 :: r)).zipIdx.filter fun ((a, b), _) => a > b).map fun (_, i) => i + 1)
  let secs := ts.map fun x => (x + 3) / 4
  return (secs.map fun x => x - secs.headD 0) ++ [0, 0, 0] ++ (ts.take 6)

#eval «各件» true (some 4) 300
#eval «各件» false (some 4) 300
#eval «各件» true none 200
#eval «各件» false none 200
end T
