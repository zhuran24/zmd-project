import Endfield.«回放».«格子工具»

open Endfield Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

namespace LianZhe

/-- 一：货源箱出满带 → 一格带 → 精炼炉 → 一格带 → 收货箱。返回蓝铁块各件进箱的步号（放货后算起）。 -/
def furnace : Option (List Nat) := do
  let ps ← ([«摆» 1 23 13 (.«协议储存箱» .«下»), «摆» 11 24 16 (.«传送带» .«上» .«下»),
    «摆» 5 23 17 (.«制造» .«精炼炉» .«下»), «摆» 12 24 20 (.«传送带» .«上» .«下»),
    «摆» 7 23 21 (.«协议储存箱» .«下»), «摆» 99 27 18 .«供电桩»]).mapM id
  let s ← «布置» ps
  let s ← «做» s (.«原样» (.«放货» 1 .«蓝铁矿» 50))
  let t := s.«模型».«历史».«立表»
  let walk := «走» «取一种» (s.«场地».«待写» «端口先后» «无效口») t
  let r := (List.range 200).foldl (fun (acc : Endfield.«状态» × List Nat) i =>
    let m' := walk 1 acc.1
    (m', if «箱里几件» m' 7 .«蓝铁块» > «箱里几件» acc.1 7 .«蓝铁块» then (i+1) :: acc.2 else acc.2)) (s.«模型», [])
  return r.2.reverse

/-- 二：一粒种子在采种机 C 和种植机 P 之间转圈。C 的出口接一格带、分流器；分流器往下一格带进收货箱，往右 8 格带进 P；
P 的出口 10 格带回 C。返回种子各次进收货箱的步号。 -/
def loop (seed flower : «物品») : Option (List Nat) := do
  let hb := fun (x y : Nat) => «摆» (1000 + 70 * x + y) x y (.«传送带» .«右» .«左»)
  let ps ← ([«摆» 1 23 15 (.«制造» .«采种机» .«下»), «摆» 2 30 15 (.«制造» .«种植机» .«上»),
    «摆» 3 24 23 (.«协议储存箱» .«下»), «摆» 99 28 17 .«供电桩»,
    «摆» 20 25 20 (.«传送带» .«上» .«下»), «摆» 21 25 21 (.«分流器» .«上»), «摆» 22 25 22 (.«传送带» .«上» .«下»)]
    ++ ([26,27,28,29,30,31].map fun x => «摆» (2000 + x) x 21 (.«传送带» .«左» .«右»))
    ++ [«摆» 2032 32 21 (.«传送带» .«左» .«上»), «摆» 2033 32 20 (.«传送带» .«下» .«上»),
        «摆» 3001 32 14 (.«传送带» .«下» .«上»), «摆» 3002 32 13 (.«传送带» .«下» .«左»)]
    ++ ([31,30,29,28,27,26].map fun x => hb x 13)
    ++ [«摆» 3003 25 13 (.«传送带» .«右» .«下»), «摆» 3004 25 14 (.«传送带» .«上» .«下»)]).mapM id
  let s ← «布置» ps
  let s ← «做» s (.«原样» (.«放货» 2 seed 1))
  let _ := flower
  let t := s.«模型».«历史».«立表»
  let walk := «走» «取一种» (s.«场地».«待写» «端口先后» «无效口») t
  let r := (List.range 1500).foldl (fun (acc : Endfield.«状态» × List Nat) i =>
    let m' := walk 1 acc.1
    (m', if «箱里几件» m' 3 seed > «箱里几件» acc.1 3 seed then (i+1) :: acc.2 else acc.2)) (s.«模型», [])
  return r.2.reverse

#eval furnace
#eval loop .«砂叶种子» .«砂叶»
#eval (loop .«砂叶种子» .«砂叶»).map fun l => (l.zip (l.drop 1)).map fun (a, b) => b - a
end LianZhe
