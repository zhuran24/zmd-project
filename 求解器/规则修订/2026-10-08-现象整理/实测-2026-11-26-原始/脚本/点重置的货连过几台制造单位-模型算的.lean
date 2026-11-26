import Endfield.«回放».«格子工具»
namespace T
open Endfield Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 一条直线：货源箱 0、带、准入口 30（累计上限 2）、带、三个位置（前 k 个放制造单位：精炼炉、粉碎机、精炼炉；其余各换成三格带）、
每个位置后面一格带、限速的准入口 45（上限 1）、收货箱 7。 -/
def «件» (k : Nat) : Option (List «摆件») :=
  let head := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 1 27 16 (.«传送带» .«上» .«下»),
    «摆» 30 27 17 (.«物品准入口» .«下»), «摆» 2 27 18 (.«传送带» .«上» .«下»)]
  let slot (m : Nat) : List (Option «摆件») :=
    let j := 19 + 4 * m
    (if m < k then [«摆» (50 + m) 26 j (.«制造» (if m == 1 then .«粉碎机» else .«精炼炉») .«下»)]
     else [«摆» (60 + 3 * m) 27 j (.«传送带» .«上» .«下»), «摆» (61 + 3 * m) 27 (j + 1) (.«传送带» .«上» .«下»),
           «摆» (62 + 3 * m) 27 (j + 2) (.«传送带» .«上» .«下»)])
    ++ [«摆» (80 + m) 27 (j + 3) (.«传送带» .«上» .«下»)]
  let tail := [«摆» 45 27 31 (.«物品准入口» .«下»), «摆» 7 26 32 (.«协议储存箱» .«下»),
    «摆» 97 30 20 .«供电桩», «摆» 98 30 24 .«供电桩», «摆» 99 30 28 .«供电桩»]
  (head ++ slot 0 ++ slot 1 ++ slot 2 ++ tail).mapM id

def «产物» : Nat → «物品»
  | 0 => .«蓝铁矿» | 1 => .«蓝铁块» | 2 => .«蓝铁粉末» | _ => .«蓝铁块»

/-- 头两件走完、G 关上以后，在第 `w` 步（4 的整倍数）以后点一次重置，再走 260 步。
给出重置以后两件进收货箱各是第几步、整秒上隔几秒。 -/
def «看» (k w : Nat) : Option (List Nat × Nat) := do
  let s ← («件» k).bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 30 (some .«蓝铁矿») (some 2) none))
  let s ← «做» s (.«原样» (.«设准入口» 45 (some («产物» k)) none (some 1)))
  let s ← «做» s (.«原样» (.«放货» 0 .«蓝铁矿» 50))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let s := «等» w s
  let n0 := «箱里几件» s.«模型» 7 («产物» k)
  let s ← «做» s (.«原样» (.«重置计数» 30))
  let r := ((List.range 260).foldl (fun (acc : Endfield.«格子».«状态» × List Nat) _ =>
      let t := «等» 1 acc.1
      (t, acc.2 ++ [«箱里几件» t.«模型» 7 («产物» k)])) (s, [])).2
  let ts := ((r.zip (n0 :: r)).zipIdx.filter fun ((a, b), _) => a > b).map fun (_, i) => i + 1
  let secs := ts.map fun x => (x + 3) / 4
  return (ts ++ [n0], (secs.getD 1 0) - (secs.getD 0 0))

#eval (List.range 4).map fun k => (k, «看» k 400)
#eval (List.range 4).map fun k => (k, «看» k 404)
end T
