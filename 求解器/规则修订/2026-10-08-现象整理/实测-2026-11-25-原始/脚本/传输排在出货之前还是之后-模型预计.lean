import Endfield.«回放».«格子工具»
namespace Endfield.«回放».«试E21»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 现象第 2 条那种摆法（另一支每件隔 9 步）进无线传输的箱子 5；箱子 5 左下出口接两格带进箱子 7。 -/
def «件» : Option (List «摆件») :=
  let base := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 5 26 22 (.«协议储存箱» .«下»),
    «摆» 6 31 16 (.«协议储存箱» .«右»), «摆» 7 22 24 (.«协议储存箱» .«左»),
    «摆» 2 27 17 (.«分流器» .«上»), «摆» 1 27 16 (.«传送带» .«上» .«下»)]
  let clear := [«摆» 20 27 19 (.«桥接器» .«上»), «摆» 10 27 18 (.«传送带» .«上» .«下»),
    «摆» 41 27 20 (.«传送带» .«上» .«下»), «摆» 42 27 21 (.«传送带» .«上» .«下»)]
  let blocked := [«摆» 30 28 17 (.«传送带» .«左» .«右»), «摆» 33 29 17 (.«传送带» .«左» .«右»),
    «摆» 32 30 17 (.«传送带» .«左» .«右»), «摆» 31 28 17 (.«物品准入口» .«右»)]
  let outb := [«摆» 51 26 25 (.«传送带» .«上» .«左»), «摆» 52 25 25 (.«传送带» .«右» .«左»)]
  (base ++ blocked ++ clear ++ outb ++ [«摆» 99 30 22 .«供电桩»]).mapM id

/-- 传输排在各组之前（k=0）还是之后（k=3）；货源在第 w 步放货。给出箱子 7 各件到货的整秒间隔，和仓库里蓝铁矿几件。 -/
def «看» (k w n : Nat) : Option (List Nat × Nat) := do
  let un : «未定» := { «取一种» with «传输排在几组之后» := fun _ => k }
  let s ← «件».bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«源矿») none none))
  let s ← «做» s (.«原样» (.«设储存箱模式» 5 false))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let «走着记» (m : Endfield.«状态») (n : Nat) : Endfield.«状态» × List Nat :=
    (List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» un todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 7 .«蓝铁矿»])) (m, [])
  let (m1, _) := «走着记» s.«模型» w
  let s ← «做» { s with «模型» := m1 } (.«原样» (.«放货» 0 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let (m2, b) := «走着记» s.«模型» n
  let ts := (((b.zip (0 :: b)).zipIdx.filter fun ((a, c), _) => a > c).map fun (_, i) => i + 1).map fun x => (x + 3) / 4
  return ((ts.zip (ts.drop 1)).map fun (a, c) => c - a, m2.«仓库» .«蓝铁矿»)

#eval [0, 3].map fun k => (k, (List.range 10).map fun j => («看» k (4 * j) 800).map fun p => ((p.1.filter (· > 3)), p.1.length, p.2))
#eval («看» 0 0 800).map (·.1)
#eval («看» 3 0 800).map (·.1)
end Endfield.«回放».«试E21»
