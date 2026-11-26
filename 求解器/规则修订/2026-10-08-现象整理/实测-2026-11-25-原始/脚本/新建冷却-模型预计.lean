import Endfield.«回放».«格子工具»
namespace Endfield.«回放».«试E9»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

def «取» (c : Nat) : «未定» := { «取一种» with «新建储存箱的冷却» := c }

def «做于» (un : «未定») (s : Endfield.«格子».«状态») (a : Endfield.«格子».«操作») : Option Endfield.«格子».«状态» :=
  Endfield.«格子».«作用» un «端口先后» «无效口» s a

/-- 走 n 步，逐步记下传输箱里几件。 -/
def «走着记» (un : «未定») (s : Endfield.«格子».«状态») (n : Nat) :
    Endfield.«格子».«状态» × List Nat :=
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let r := (List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
    let t := «走» un todo T 1 acc.1
    (t, acc.2 ++ [«箱里几件» t 60 .«蓝铁矿»])) (s.«模型», [])
  ({ s with «模型» := r.1 }, r.2)

/-- 先放传输箱（没电）、货源放满，走 w 步（货进箱攒着），再放供电桩，接着走 n 步。给出放供电桩以后每步末箱里的件数。 -/
def «先进货后通电» (c w n : Nat) : Option (List Nat × List Nat) := do
  let un := «取» c
  let s ← (([«摆» 1 32 13 (.«协议储存箱» .«下»)]
     ++ ([16, 17, 18, 19, 20, 21, 22].map fun j => «摆» (100 + j) 32 j (.«传送带» .«上» .«下»))).mapM id).bind «布置»
  let s ← «做于» un s (.«建» (← «摆» 60 32 23 (.«协议储存箱» .«下»)))
  let s ← «做于» un s (.«原样» (.«放货» 1 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let (s, a) := «走着记» un s w
  let s ← «做于» un s (.«建» (← «摆» 99 36 24 .«供电桩»))
  let (_, b) := «走着记» un s n
  return (a, b)

#eval («先进货后通电» 0 120 100).map fun p => (p.1.getLast?, p.2)
#eval («先进货后通电» 40 120 100).map fun p => (p.1.getLast?, p.2)
end Endfield.«回放».«试E9»
