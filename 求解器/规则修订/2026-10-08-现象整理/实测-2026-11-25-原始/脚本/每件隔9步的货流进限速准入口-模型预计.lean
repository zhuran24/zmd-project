import Endfield.«回放».«格子工具»
namespace Endfield.«回放».«试E8»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 准入口贴着分流器、挡住的一支先放（另一支每件隔 9 步），另一支桥接器后面那格 (27,20) 换成限速的准入口 45。 -/
def «件» : Option (List «摆件») :=
  let base := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 5 26 22 (.«协议储存箱» .«下»),
    «摆» 6 31 16 (.«协议储存箱» .«右»), «摆» 2 27 17 (.«分流器» .«上»), «摆» 1 27 16 (.«传送带» .«上» .«下»)]
  let clear := [«摆» 20 27 19 (.«桥接器» .«上»), «摆» 10 27 18 (.«传送带» .«上» .«下»),
    «摆» 41 27 20 (.«传送带» .«上» .«下»), «摆» 42 27 21 (.«传送带» .«上» .«下»)]
  let blocked := [«摆» 30 28 17 (.«传送带» .«左» .«右»), «摆» 33 29 17 (.«传送带» .«左» .«右»),
    «摆» 32 30 17 (.«传送带» .«左» .«右»), «摆» 31 28 17 (.«物品准入口» .«右»)]
  (base ++ blocked ++ clear ++ [«摆» 45 27 20 (.«物品准入口» .«下»)]).mapM id

/-- 各件进收货箱的步；k = 9 表示不限速。 -/
def «到货» (k n : Nat) : Option (List Nat) := do
  let s ← «件».bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«源矿») none none))
  let s ← «做» s (.«原样» (.«设准入口» 45 (some .«蓝铁矿») none (if k == 9 then none else some k)))
  let s ← «做» s (.«原样» (.«放货» 0 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let r := ((List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 5 .«蓝铁矿»])) (s.«模型», [])).2
  return ((r.zip (0 :: r)).zipIdx.filter fun ((a, b), _) => a > b).map fun (_, i) => i + 1

def «秒» (xs : List Nat) : List Nat :=
  let ts := xs.map fun x => (x + 3) / 4
  match ts with
  | [] => []
  | a :: _ => ts.map (· - a)
def «隔» (xs : List Nat) : List Nat := (xs.zip (xs.drop 1)).map fun (a, b) => b - a

#eval ("不限 步", («到货» 9 330).map (·.take 30))
#eval ("不限 秒间隔", («到货» 9 400).map fun l => «隔» («秒» l))
#eval ("上限5 秒间隔", («到货» 5 400).map fun l => «隔» («秒» l))
#eval ("上限4 步", («到货» 4 400).map (·.take 30))
#eval ("上限4 秒", («到货» 4 600).map «秒»)
#eval ("上限4 秒间隔", («到货» 4 600).map fun l => «隔» («秒» l))
#eval ("上限3 秒间隔", («到货» 3 600).map fun l => «隔» («秒» l))
#eval ("上限2 秒间隔", («到货» 2 600).map fun l => «隔» («秒» l))
#eval ("上限1 秒间隔", («到货» 1 600).map fun l => «隔» («秒» l))
end Endfield.«回放».«试E8»
