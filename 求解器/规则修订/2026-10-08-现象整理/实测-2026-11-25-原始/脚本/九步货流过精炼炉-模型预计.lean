import Endfield.«回放».«格子工具»
namespace Endfield.«回放».«试E22»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 现象第 2 条那种摆法（另一支每件隔 9 步）送蓝铁矿进精炼炉 5（上进下出，有电），
精炼炉左下出口接一格带 51、限速的准入口 52，进箱子 7。 -/
def «件» : Option (List «摆件») :=
  let base := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 5 26 22 (.«制造» .«精炼炉» .«下»),
    «摆» 6 31 16 (.«协议储存箱» .«右»), «摆» 7 22 24 (.«协议储存箱» .«左»),
    «摆» 2 27 17 (.«分流器» .«上»), «摆» 1 27 16 (.«传送带» .«上» .«下»)]
  let clear := [«摆» 20 27 19 (.«桥接器» .«上»), «摆» 10 27 18 (.«传送带» .«上» .«下»),
    «摆» 41 27 20 (.«传送带» .«上» .«下»), «摆» 42 27 21 (.«传送带» .«上» .«下»)]
  let blocked := [«摆» 30 28 17 (.«传送带» .«左» .«右»), «摆» 33 29 17 (.«传送带» .«左» .«右»),
    «摆» 32 30 17 (.«传送带» .«左» .«右»), «摆» 31 28 17 (.«物品准入口» .«右»)]
  let outb := [«摆» 51 26 25 (.«传送带» .«上» .«左»), «摆» 52 25 25 (.«物品准入口» .«左»)]
  (base ++ blocked ++ clear ++ outb ++ [«摆» 99 30 22 .«供电桩»]).mapM id

/-- k 是出口那个准入口的每 5 tick 上限（none 不限）。给出箱子 7 各件到货的步和整秒间隔。 -/
def «看» (k : Option Nat) (n : Nat) : Option (List Nat × List Nat) := do
  let s ← «件».bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«源矿») none none))
  let s ← «做» s (.«原样» (.«设准入口» 52 (some .«蓝铁块») none k))
  let s ← «做» s (.«原样» (.«放货» 0 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let r := ((List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 7 .«蓝铁块»])) (s.«模型», [])).2
  let st := ((r.zip (0 :: r)).zipIdx.filter fun ((a, b), _) => a > b).map fun (_, i) => i + 1
  let ts := st.map fun x => (x + 3) / 4
  return (st.take 12, (ts.zip (ts.drop 1)).map fun (a, b) => b - a)

#eval ("不限", «看» none 400)
#eval ("上限4", «看» (some 4) 500)
#eval ("上限3", «看» (some 3) 500)
#eval ("上限2", «看» (some 2) 500)
end Endfield.«回放».«试E22»
