import Endfield.«回放».«格子工具»

namespace Endfield.«回放».«种植机出口预计»
open Endfield.«格子» Endfield.«回放».«格子»

def belt (u i j : Nat) (a b : «朝向») := «摆» u i j (.«传送带» a b)
def planter := «摆» 10 27 15 (.«制造» .«种植机» .«下»)

-- 箱和桩按左上格摆。(27,14) 用普通带，货源箱留空。
def base := [
  «摆» 1 23 13 (.«协议储存箱» .«右»), «摆» 99 33 16 .«供电桩»,
  «摆» 51 23 24 (.«协议储存箱» .«下»), «摆» 52 26 24 (.«协议储存箱» .«下»),
  «摆» 53 29 24 (.«协议储存箱» .«下»), «摆» 54 32 24 (.«协议储存箱» .«下»),
  belt 2 26 14 .«左» .«右», belt 3 27 14 .«左» .«右»,
  belt 4 28 14 .«左» .«右», belt 5 29 14 .«左» .«下»]

def routeM := [«摆» 20 27 20 (.«汇流器» .«下»),
  belt 21 27 21 .«上» .«左», belt 22 26 21 .«右» .«左», belt 23 25 21 .«右» .«左»,
  belt 24 24 21 .«右» .«下», belt 25 24 22 .«上» .«下», belt 26 24 23 .«上» .«下»]
def routeC := [belt 30 31 20 .«上» .«下», belt 31 31 21 .«上» .«右»,
  belt 32 32 21 .«左» .«右», belt 33 33 21 .«左» .«下»,
  belt 34 33 22 .«上» .«下», belt 35 33 23 .«上» .«下»]
def routeA := [belt 40 29 20 .«上» .«下», belt 41 29 21 .«上» .«下»,
  belt 42 29 22 .«上» .«左», belt 43 28 22 .«右» .«左»,
  belt 44 27 22 .«右» .«下», belt 45 27 23 .«上» .«下»]
def routeB := [belt 60 30 20 .«上» .«下», belt 61 30 21 .«上» .«下»,
  belt 62 30 22 .«上» .«下», belt 63 30 23 .«上» .«下»]

def layout (last : Bool) (extra : Bool := false) := do
  let routes := routeM ++ routeC ++ routeA ++ routeB
  let probe := if extra then [belt 70 28 20 .«上» .«下»] else []
  let ps := if last then base ++ routes ++ probe ++ [planter] else base ++ [planter] ++ routes
  «布置» (← ps.mapM id)

def boxes := [("M",51), ("A",52), ("B",53), ("C",54)]
def counts (s : Endfield.«格子».«状态») :=
  boxes.map fun (_,u) => «箱货» s u .«砂叶»

-- 等到四箱中恰有一箱比投种前多一件才接受这次读数，并沿用此状态。
def trial (last : Bool) : Option (List String × List Nat) := do
  let s ← layout last
  let (t, dest) ← (List.range 6).foldlM (fun (acc : Endfield.«格子».«状态» × List String) _ => do
    let before := counts acc.1
    let fed ← «做» acc.1 (.«原样» (.«放货» 10 .«砂叶种子» 1))
    let t := «等» 80 fed
    let after := counts t
    let [i] := (List.range 4).filter (fun i => before.modify i (· + 1) == after) | none
    return (t, acc.2 ++ [(← boxes[i]?).1])) (s, [])
  return (dest, counts t)

-- 直接读接通事件，把下游单位号换回第 20 行的横坐标。
def connected (last extra : Bool) : Option (List Nat) := do
  let s ← layout last extra
  let cs := («接通表» s.«模型».«历史»).filter (fun c => c.«起» == 10)
  cs.mapM fun c => do
    let p ← s.«场地».find? (fun p => p.«号» == c.«止»)
    return p.«位置».i.val

#eval ("甲", trial false)
#eval ("乙", trial true)
#eval ("甲出口接通横坐标", connected false false)
#eval ("乙出口接通横坐标", connected true false)
#eval ("乙另接满五口，仅查接通事件", connected true true)

end Endfield.«回放».«种植机出口预计»
