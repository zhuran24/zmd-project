import Endfield.«回放».«格子工具»

/-!
# 回放：贴着收货箱的分流器

据：实测-2026-11-27.md「三、一圈元件只靠一个贴着箱子的分流器出货」
和「四、整张蓝图转向以后桥接器的朝向」。坐标沿用游戏的格，3×3 的箱子给占地的左上角。
碳块用钢块代替，碳粉末用源石粉末代替。这两种货只用来认来源。

第三节各单放三件。点击放行到读到进箱，贴箱为 22.4–23.0 秒，垫带为 24.4–25.0 秒；
连着放都是每 4 秒一件。下面从每次放行后的第 1 步数，逐步读准入口、绕回带首格、收货箱。
具体步号是模型值。按相邻两次进箱读数之差，贴箱约 25、25 秒，垫带约 27、27 秒。

第四节头轮从下箱放货返回到放桥调用开始约 28.4 秒。后九轮清箱、收箱收桥、重置两口，
从下口重置返回到放桥调用开始约 8 秒。脚本放桥后等 4 秒放箱、再等 3 秒读箱，调用也占时间。
不限件数只有最后一轮蓝图桥测过。模型沿用十轮同一场地，按蓝图转完的朝向直接放桥。
-/

namespace Endfield.«回放».«贴箱的分流器»
open Endfield.«格子» Endfield.«回放».«格子»

/-- 回放：带格子位置的基地状态。 -/
private abbrev «基地» := Endfield.«格子».«状态»

/-- 回放：两箱、汇流器、分流器先放。准入口换在进料带首格，中间带和可选的垫带接好，最后拉右边绕回的三格。 -/
private def «一圈» («垫带» : Bool) : Option «基地» := do
  let ps ← ([«摆» 1 23 13 (.«协议储存箱» .«下»),
    «摆» 2 23 (if «垫带» then 22 else 21) (.«协议储存箱» .«下»),
    «摆» 3 24 18 (.«汇流器» .«下»), «摆» 4 24 20 (.«分流器» .«上»),
    «摆» 5 24 16 (.«传送带» .«上» .«下»), «摆» 6 24 17 (.«传送带» .«上» .«下»),
    «摆» 12 24 16 (.«物品准入口» .«下»), «摆» 7 24 19 (.«传送带» .«上» .«下»)] ++
    (if «垫带» then [«摆» 8 24 21 (.«传送带» .«上» .«下»)] else []) ++
    [«摆» 9 25 20 (.«传送带» .«左» .«上»), «摆» 10 25 19 (.«传送带» .«下» .«上»),
     «摆» 11 25 18 (.«传送带» .«下» .«左»)]).mapM id
  let s ← «布置» ps
  «依次» s [.«原样» (.«设准入口» 12 (some .«钢块») (some 1) (some 0)), .«原样» (.«放货» 1 .«钢块» 300),
    .«原样» (.«设准入口» 12 (some .«钢块») (some 1) none)]

/-- 回放：每多一件就记一个步号；同一步多两件会出现两次。 -/
private def «增加的步» (counts : List Nat) : List Nat :=
  (counts.zip (counts.drop 1)).zipIdx.flatMap fun ((a, b), i) => List.replicate (b - a) (i + 1)

/-- 回放：按三次点击放行，记下每件在模型中进准入口、绕回、进箱的步号，返回连放的起点。 -/
private def «三次单放» («垫带» : Bool) : Option («基地» × List (List Nat × List Nat × List Nat)) := do
  let mut s ← «一圈» «垫带»
  let mut single := #[]
  let waits : List Nat := if «垫带» then [108, 108, 112] else [100, 100, 104]
  let mut now := 0
  let mut arrivals : List Nat := []
  for (n, i) in waits.zipIdx do
    if i > 0 then s ← «做» s (.«原样» (.«重置计数» 12))
    let (t, rows) : «基地» × List (Nat × Nat × Nat) := «逐步读» s n fun m =>
      ((m.«准入口» 12).«累计已收», m.«件数» ⟨9, .«格» 0⟩ .«钢块», «箱里几件» m 2 .«钢块»)
    arrivals := arrivals ++ («增加的步» (rows.map (·.2.2))).map (now + ·)
    now := now + n
    single := single.push («增加的步» (rows.map (·.1)), «增加的步» (rows.map (·.2.1)),
      «增加的步» (rows.map (·.2.2)))
    s := t
  -- 调用 129、131、133 和 186、188、190 的三次进箱，沿同一条时间轴相减。
  let gaps := (arrivals.zip (arrivals.drop 1)).map fun (a,b) => b - a
  guard (gaps == (if «垫带» then [108,108] else [100,100]))
  s ← «做» s (.«原样» (.«设准入口» 12 (some .«钢块») none none))
  return (s, single.toList)

/-- 回放：从关累计上限走到收货箱的最后一次采样。 -/
private def «圈的读数» («垫带» : Bool) := do
  let (s, single) ← «三次单放» «垫带»
  let (_, counts) := «逐步读» s 184 fun m => «箱里几件» m 2 .«钢块»
  -- 贴箱 05:49:24.08 和垫带 05:58:52.94 都已过第 46 个结算秒。另读货源箱约在第 48 秒。
  return (single, «增加的步» counts, counts.getLast?, «箱货» («等» 192 s) 1 .«钢块»)

-- 三次单放均第 1 步进准入口、第 41 步绕回；到箱与进准入口两步相减，贴箱 88 步、垫带 96 步。
-- 接着关累计上限，两种摆法相邻两件都隔 16 步。
#guard «圈的读数» false == some (List.replicate 3 ([1], [41], [89]),
  [49, 65, 81, 97, 113, 129, 145, 161, 177], some 12, 281)
#guard «圈的读数» true == some (List.replicate 3 ([1], [41], [97]),
  [57, 73, 89, 105, 121, 137, 153, 169], some 11, 281)

/-- 回放：在限速 0 的调用窗口内停料。按两个面板各自的时刻读箱，再按先源箱后收货箱的次序清货。 -/
private def «停料清箱» («垫带» : Bool) (stop : Nat) := do
  let (s, _) ← «三次单放» «垫带»
  let s ← «做» («等» stop s) (.«原样» (.«设准入口» 12 (some .«钢块») none (some 0)))
  -- 步号都从关累计上限算。贴箱在 05:50:56.73、59.03 分开读两箱，清源箱始于
  -- 05:51:00.10，清收货箱始于 08.62。垫带对应 05:59:48.40、50.71、51.79、06:00:00.27。
  let (readA, readB, clearA, clearB) : Nat × Nat × Nat × Nat :=
    if «垫带» then (408, 416, 420, 456) else (556, 564, 568, 604)
  let a := «等» (readA - stop) s
  let b := «等» (readB - readA) a
  let mut c := «等» (clearA - readB) b
  let source := «箱货» c 1 .«钢块»
  for i in [:6] do
    let g : «格位» := ⟨1, .«格» i⟩
    unless (c.«模型».«货» g).isEmpty do c ← «做» c (.«原样» (.«收货» g))
  let d := «等» (clearB - clearA) c
  let sink := «箱货» d 2 .«钢块»
  -- 这一轮收货装在第 1 格。检查清完以后场上每个单位的每个物品格。
  let t ← «做» d (.«原样» (.«收货» ⟨2, .«格» 0⟩))
  let empty := t.«模型».«布局».«单位表».all fun (u, k) =>
    k.«物品格».all fun g => (t.«模型».«货» ⟨u, g⟩).isEmpty
  return («箱货» a 1 .«钢块», «箱货» b 2 .«钢块», source, sink, source + sink, empty)

-- set_gate 没记限速点击，只记调用起止。以箱数变化的整秒（贴箱约 .24、垫带约 .25）计，
-- 05:50:21.97–25.71 内未停料的完整步数有以下五种，垫带 05:59:11.73–15.50 同理。
-- 逐个核对可与实测相合的时刻。贴箱先读 267、32，稍后清出 267、33；垫带相应为 277、22 和 277、23。
#guard [416, 420, 424, 428, 432].map (fun n =>
  «停料清箱» false n == some (267, 32, 267, 33, 300, true)) == [true, true, true, false, false]
#guard [260, 264, 268, 272, 276].map (fun n =>
  «停料清箱» true n == some (277, 22, 277, 23, 300, true)) == [true, true, false, false, false]

/-- 回放：上下两个货源箱、各两格带、两个分流器，最后在两条带的首格换准入口。每箱放一组。
头轮两次 box_put（调用 36、37）内，上箱读到 49 件，下箱读到 50 件。 -/
private def «两条进料线» : Option «基地» := do
  let ps ← [«摆» 1 26 14 (.«协议储存箱» .«下»), «摆» 2 26 24 (.«协议储存箱» .«上»),
    «摆» 3 27 17 (.«传送带» .«上» .«下»), «摆» 4 27 18 (.«传送带» .«上» .«下»),
    «摆» 5 27 23 (.«传送带» .«下» .«上»), «摆» 6 27 22 (.«传送带» .«下» .«上»),
    «摆» 7 27 19 (.«分流器» .«上»), «摆» 8 27 21 (.«分流器» .«下»),
    «摆» 9 27 17 (.«物品准入口» .«下»), «摆» 10 27 23 (.«物品准入口» .«上»)].mapM id
  let s ← «布置» ps
  let s ← «依次» s [.«原样» (.«设准入口» 9 (some .«钢块») (some 2) none),
    .«原样» (.«设准入口» 10 (some .«源石粉末») (some 2) none), .«原样» (.«放货» 1 .«钢块» 50)]
  -- 两次调用各约 15 秒。点击和读面板的时刻未单记，核同一窗口内能否读到该值。
  let (s, upper) := «逐步读» s 60 (fun m => «箱里几件» m 1 .«钢块»)
  let s ← «做» s (.«原样» (.«放货» 2 .«源石粉末» 50))
  let (s, lower) := «逐步读» s 62 (fun m => «箱里几件» m 2 .«源石粉末»)
  guard (upper.contains 49 && lower.contains 50)
  return s

/-- 回放：D 的六格，第一项是面板第 1 格。 -/
private def «六格» (s : «基地») :=
  (List.range 6).map fun i =>
    (s.«模型».«货» ⟨30, .«格» i⟩).map fun (p : «一堆») => (p.«物», p.«件数»)

/-- 回放：从本轮准备好的场地放桥、放无线模式的 D、读六格，留下读完的场地。
beforeBridge 从头轮下箱放货返回或以后各轮下口重置返回算起。 -/
private def «放桥读箱» (s : «基地») (d : «朝向») (upperFirst : Bool)
    (beforeBridge beforeBox afterBox : Nat) : Option «基地» := do
  let a := «等» beforeBridge s
  let b ← «做» a (.«建» (← «摆» 20 27 20 (.«桥接器» d)))
  let connections := «接通表» (b.«模型».«历史».drop a.«模型».«历史».length)
  guard (connections.map «通道».«起» == (if upperFirst then [7,8] else [8,7]))
  let b ← «做» («等» beforeBox b) (.«建» (← «摆» 30 24 19 (.«协议储存箱» .«左»)))
  let b := «等» afterBox b
  let upper := [(«物品».«钢块», 1)]
  let lower := [(«物品».«源石粉末», 1)]
  guard («六格» b == (if upperFirst then [upper,lower] else [lower,upper]) ++ [[],[],[],[]])
  return b

/-- 回放：清掉 D 面板里两格各一件，余下六格都空。 -/
private def «清箱» (s : «基地») := do
  let t ← «依次» s [.«原样» (.«收货» ⟨30, .«格» 0⟩), .«原样» (.«收货» ⟨30, .«格» 1⟩)]
  guard («六格» t == List.replicate 6 [])
  return t

/-- 回放：沿用上一轮的两条进料线。以读 D、清 D、拆除调用的开始，两个 reset_time.t0，
以及下口重置返回为界，相邻时刻之差折整步。重置后的面板在各自调用内读。 -/
private def «准备下一轮» (s : «基地») (toClear toRemove toUpper between toReturn : Nat) := do
  let s ← «清箱» («等» toClear s)
  let s ← «依次» («等» toRemove s) [.«收» 30, .«收» 20]
  let s ← «做» («等» toUpper s) (.«原样» (.«重置计数» 9))
  let s := «等» 8 s
  guard ((s.«模型».«准入口» 9).«累计已收» == 1)
  let s ← «做» («等» (between - 8) s) (.«原样» (.«重置计数» 10))
  let s := «等» 8 s
  guard ((s.«模型».«准入口» 10).«累计已收» == 1)
  return «等» (toReturn - 8) s

-- 头轮调用 37→39 相隔 28.414 秒，折 114 步。次轮调用 44、45 各在重置后约两秒读到 1，
-- 45 返回到 46 开始隔 8.029 秒，折 32 步。两种手放桥的六格也按脚本等待 16、12 步复核。
#guard (do
  let s ← «放桥读箱» (← «两条进料线») .«上» true 114 16 12
  «放桥读箱» (← «准备下一轮» s 9 28 20 15 9) .«下» false 32 16 12).isSome

/-- 回放：调用 39–104 的十轮。头两轮直接放 rot=0、2。后八轮游戏里用 brga（存 0）、
brgc（存 2）各转 0、1、2、3 次；模型的放蓝图没有整张转向，按转后的朝向直接放。
表中依次为朝向、实读是否上货在先、清拆重置的五段间隔、放桥到放 D、放 D 到读箱。 -/
private def «十轮» := do
  let mut s ← «放桥读箱» (← «两条进料线») .«上» true 114 28 24
  let rounds : List («朝向» × Bool × Nat × Nat × Nat × Nat × Nat × Nat × Nat) := [
    (.«下», false, 9,28,20,15,9, 29,24),
    (.«上», true,  9,27,18,14,10, 39,23), (.«右», true,  8,25,18,13,9, 42,24),
    (.«下», false, 9,29,21,16,10, 53,24), (.«左», false, 9,28,20,15,10, 60,25),
    (.«下», false, 9,28,20,15,11, 43,24), (.«左», false, 9,28,20,15,10, 49,24),
    (.«上», true,  9,28,20,15,11, 53,24), (.«右», true,  8,27,19,14,11, 47,23)]
  for (d, upper, clear, remove, reset, gap, finish, box, readAt) in rounds do
    s ← «准备下一轮» s clear remove reset gap finish
    s ← «放桥读箱» s d upper 32 box readAt
  return s

/-- 回放：调用 104–108。沿用 brgc 转三次（朝右）的桥和刚读过的 D。清空后先开上路，
再开下路。两次调用开始差 2.968 秒，取相隔 12 步；点击的间隔未单独量到。 -/
private def «不限件数» := do
  let s ← «清箱» («等» 100 (← «十轮»))  -- 104→105 约 25 秒
  let s ← «做» («等» 25 s) (.«原样» (.«设准入口» 9 (some .«钢块») none none))
  let s ← «做» («等» 12 s) (.«原样» (.«设准入口» 10 (some .«源石粉末») none none))
  let (last, rows) : «基地» × List (Nat × Nat) := «逐步读» s 94 fun m =>
    («箱里几件» m 30 .«钢块», «箱里几件» m 30 .«源石粉末»)
  -- 调用 108 首帧空，约 0.7 秒后见首件，约再过 20.3 秒末读。以模型首件为第 13 步对时。
  return (rows[10]?, «增加的步» (rows.map (@Prod.fst Nat Nat)), «增加的步» (rows.map (@Prod.snd Nat Nat)), «六格» last)

-- 实测先是两件上货，再进一件下货，以后两路各隔约两秒、相互错开一秒。步号是模型值。
#guard «不限件数» == some (some (0,0),
  [13,21,29,37,45,53,61,69,77,85,93], [25,33,41,49,57,65,73,81,89],
  [[(.«钢块»,11)],[(.«源石粉末»,9)],[],[],[],[]])

end Endfield.«回放».«贴箱的分流器»
