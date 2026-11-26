import Endfield.«回放».«格子工具»
namespace Endfield.«回放».«现象2试2»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 照游戏里动手的先后摆：货源箱 0、收货箱 5、挡住那支的箱 6、分流器 2、进料带 1 先放；
通畅的一支：桥接器 20、带 10（分流器到桥接器之间那一格）、带 41、42；
挡住的一支：带 30、33、32 三格，再把 `口` 那一格（28 或 29）换成物品准入口 31。 -/
def «件» («挡住的先放» : Bool) («口» : Nat) : Option (List «摆件») :=
  let base := [«摆» 0 26 13 (.«协议储存箱» .«下»), «摆» 5 26 22 (.«协议储存箱» .«下»),
    «摆» 6 31 16 (.«协议储存箱» .«右»), «摆» 2 27 17 (.«分流器» .«上»), «摆» 1 27 16 (.«传送带» .«上» .«下»)]
  let clear := [«摆» 20 27 19 (.«桥接器» .«上»), «摆» 10 27 18 (.«传送带» .«上» .«下»),
    «摆» 41 27 20 (.«传送带» .«上» .«下»), «摆» 42 27 21 (.«传送带» .«上» .«下»)]
  let blocked := [«摆» 30 28 17 (.«传送带» .«左» .«右»), «摆» 33 29 17 (.«传送带» .«左» .«右»),
    «摆» 32 30 17 (.«传送带» .«左» .«右»), «摆» 31 «口» 17 (.«物品准入口» .«右»)]
  (base ++ (if «挡住的先放» then blocked ++ clear else clear ++ blocked)).mapM id

/-- 稳下来以后各件进收货箱 5 的间隔（步），取 12 个。 -/
def «间隔» («挡住的先放» : Bool) («口» : Nat) : Option (List Nat) := do
  let s ← («件» «挡住的先放» «口»).bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 31 (some .«源矿») none none))
  let s ← «做» s (.«原样» (.«放货» 0 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let r := ((List.range 420).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 5 .«蓝铁矿»])) (s.«模型», [])).2
  let ts := ((r.zip (0 :: r)).zipIdx.filter fun ((a, b), _) => a > b).map fun (_, i) => i + 1
  let ds := (ts.zip (ts.drop 1)).map fun (a, b) => b - a
  return (ds.drop 20).take 12

#eval [(true, 29), (false, 29), (true, 28), (false, 28)].map fun p => (p, «间隔» p.1 p.2)
end Endfield.«回放».«现象2试2»
