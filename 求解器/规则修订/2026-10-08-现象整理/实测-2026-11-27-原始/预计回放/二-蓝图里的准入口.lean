import Std.Data.HashMap
import Endfield.«回放».«格子工具»

namespace Endfield.«蓝图准入口回放»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

-- 1 是货源箱，2 是进料准入口，3 是分流器，4 是待测准入口，5、6 是 G、B。
def pieces (second : Bool) : Option (List «摆件» × List «摆件») := do
  let fixed ← [«摆» 1 23 13 (.«协议储存箱» .«下»),
    «摆» 2 24 16 (.«物品准入口» .«下»), «摆» 3 24 18 (.«分流器» .«上»)].mapM id
  let exits ← (if second then
    [«摆» 4 25 18 (.«物品准入口» .«右»), «摆» 5 26 17 (.«协议储存箱» .«右»),
     «摆» 6 22 20 (.«协议储存箱» .«下»)]
    else [«摆» 4 24 19 (.«物品准入口» .«下»), «摆» 5 23 20 (.«协议储存箱» .«下»),
          «摆» 6 26 20 (.«协议储存箱» .«下»)]).mapM id
  let inlet ← «摆» 7 24 17 (.«传送带» .«上» .«下»)
  let belt ← (if second then
    [«摆» 8 23 18 (.«传送带» .«右» .«下»), «摆» 9 23 19 (.«传送带» .«上» .«下»)]
    else [«摆» 8 25 18 (.«传送带» .«左» .«右»), «摆» 9 26 18 (.«传送带» .«左» .«右»),
          «摆» 10 27 18 (.«传送带» .«左» .«下»), «摆» 11 27 19 (.«传送带» .«上» .«下»)]).mapM id
  return (fixed ++ exits, inlet :: belt)

abbrev FieldState := Endfield.«格子».«状态»
def buildOrder (units belts : List «摆件») (late : Option «摆件») : Option FieldState := do
  let s ← «做» Endfield.«格子».«状态».«空» (.«蓝图» (units ++ belts))
  match late with
  | none => return s
  | some gate => «做» s (.«建» gate)

-- 同一种货，不制造。所有准入口都要指定可放行的物品。
def observe (s : FieldState) : Option (List (Nat × Nat)) := do
  let s ← «依次» s [.«原样» (.«设准入口» 2 (some .«钢块») (some 1) none),
    .«原样» (.«设准入口» 4 (some .«钢块») none none), .«原样» (.«放货» 1 .«钢块» 3)]
  let table := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let mut s := s
  let mut counts := []
  for i in [:3] do
    if i > 0 then s ← «做» s (.«原样» (.«重置计数» 2))
    s := { s with «模型» := «走» «取一种» todo table 80 s.«模型» }
    counts := counts ++ [(«箱货» s 5 .«钢块», «箱货» s 6 .«钢块»)]
  return counts

def runSample (second late : Bool) : Option (List (Nat × Nat)) := do
  let (us, bs) ← pieces second
  let gate ← us.find? (·.«号» == 4)
  let s ← buildOrder (if late then us.filter (·.«号» != 4) else us) bs
    (if late then some gate else none)
  observe s

#eval [false,true].flatMap fun second => [false,true].map fun late => (second, late, runSample second late)
def inserts (x : α) : List α → List (List α)
  | [] => [[x]]
  | h :: t => (x :: h :: t) :: (inserts x t).map (h :: ·)
def orders : List α → List (List α)
  | [] => [[]]
  | x :: xs => (orders xs).flatMap (inserts x)

-- 读当前通道表，包含改带格导致的重接。
def outlets (s : FieldState) : List Nat :=
  s.«模型».«布局».«通道表».filterMap fun (c,_) => if c.«起» == 3 then some c.«止» else none

-- 固定摆法里几何、编号和种类相同。各件建完仍是空场，没有任何通道走过货。
-- 存下完整的步内调度（含带内和各组内部先后）；历史的时刻已由立表算进优先级。
-- 单位表用于按号查种类、取长度和压平，枚举格位时每个格位唯一。
-- 空场上的供电、端口和放货判定也只依赖这些摆件的几何和编号。
def schedule (s : FieldState) : String :=
  let t := s.«模型».«历史».«立表»
  reprStr (t.«带内», t.«元件的组», t.«汇流器», t.«非运输单位»)

abbrev Reading := List (Nat × Nat)
structure Stats where
  total : Nat := 0
  cache : Std.HashMap String Reading := {}
  counts : List (Reading × Nat) := []
  deriving Inhabited

def survey (second late : Bool) (start size : Nat) : Option Stats := do
  let (us, bs) ← pieces second
  let gate ← us.find? (·.«号» == 4)
  let nonbelts := if late then us.filter (·.«号» != 4) else us
  let beltOrders := orders bs
  let mut stats : Stats := {}
  for u in ((orders nonbelts).drop start).take size do
    for b in beltOrders do
      let s ← buildOrder u b (if late then some gate else none)
      let key := schedule s
      let reading ← match stats.cache[key]? with
        | some r => pure r
        | none => observe s
      if !stats.cache.contains key then
        stats := { stats with cache := stats.cache.insert key reading }
      let old := (stats.counts.lookup reading).getD 0
      stats := { stats with
        total := stats.total + 1
        counts := (reading, old + 1) :: stats.counts.filter (·.1 != reading)}
  return stats

-- 每一组排列都实际调用蓝图操作并从其完整历史立表。分块只为并行计算。
def surveyAll (second late : Bool) : IO Unit := do
  let n := if late then 120 else 720
  let chunk := n / 12
  let tasks := (List.range 12).map fun i =>
    Task.spawn (fun _ => survey second late (i * chunk) chunk)
  let mut counts : List (Reading × Nat) := []
  let mut total := 0
  for task in tasks do
    let some s := task.get | throw (IO.userError "蓝图建造、放货或重置失败")
    total := total + s.total
    for (reading, count) in s.counts do
      counts := (reading, (counts.lookup reading).getD 0 + count) ::
        counts.filter (·.1 != reading)
  let expected := n * (if second then 6 else 120)
  unless total == expected do throw (IO.userError "排列计数不符")
  IO.println s!"摆法{if second then 2 else 1} {if late then "后建对照" else "整张蓝图"}  共 {total} 种，逐件累计 (G,B) 及排列数 {repr counts}"

#eval surveyAll true false
#eval surveyAll true true
#eval surveyAll false true
#eval surveyAll false false
end Endfield.«蓝图准入口回放»
