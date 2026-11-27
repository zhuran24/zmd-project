import Endfield.«回放».«格子工具»

/-!
# 回放：两个分流器争公共箱的第 1 格

实测-2026-11-27.md 第十三节补四，建造和读箱时刻见同日调用记录 08:27–08:40。
1、2 是货源箱甲、乙，3 是混合分流器，4、5 是它左边的两格带，6 是公共箱，7 是远箱，
8 是另一个分流器，9 是排货箱。钢块代碳块，源石粉末代碳粉末，乙用实测的砂叶种子。
每遍把两个箱子装满才给两路供货，等两路都堵住，再从公共箱向排货箱拉带。
-/

namespace Endfield.«回放».«贴箱分流器争第一格»
open Endfield.«格子» Endfield.«回放».«格子»

/-- 回放：三遍共同的摆件，照各遍实际的先后逐件建成。排货箱只在第一遍建一次。 -/
private def «搭一遍» (s : Endfield.«格子».«状态») (round : Fin 3) := do
  let mixed ← «摆» 3 27 16 (.«分流器» .«上»)
  let b ← «摆» 4 26 16 (.«传送带» .«右» .«左»)
  let c ← «摆» 5 25 16 (.«传送带» .«右» .«左»)
  let common ← «摆» 6 27 17 (.«协议储存箱» .«下»)
  let far ← «摆» 7 22 15 (.«协议储存箱» .«左»)
  let single ← «摆» 8 29 16 (.«分流器» .«右»)
  let ps ← match round with
    | 0 => pure [mixed, b, c, common, far, single, ← «摆» 9 27 22 (.«协议储存箱» .«下»)]
    | 1 => pure [mixed, b, c, far, common, single]
    | 2 => pure [common, single, mixed, b, c, far]
  ps.foldlM «建好» s

/-- 回放：按乙、丙的预计只改混合分流器在本布局里的次序，再用两组实际的时刻比谁先送。 -/
private def «乙丙预计» (h : «历史») := do
  let n := h.length
  let t ← h.«组的时刻» n (.«分流器的» 3)
  let single ← h.«级别» n (.«分流器的» 8)
  let item (order : Nat) : «物品» :=
    if «历史».«级别高于» (order, t) single then .«源石粉末» else .«砂叶种子»
  -- 乙可走到混合分流器（1）或经左边带子到远箱（2），取先成终点的一支。丙只认远箱。
  let direct ← h.«终点的时刻» n 3
  let far ← h.«终点的时刻» n 7
  return (item (if direct ≤ far then 1 else 2), item 2)

/-- 回放：两次放货调用内分别采样，乙调用结束后才按四个面板的钟面时刻读数。
点击和放货面板各自的时刻未记。用调用长度给出从放货到采样的窗口；在窗口内核读数，
到调用返回继续走步。把放货放在窗口起点是一个相容取法。 -/
private def «放货读箱» (s : Endfield.«格子».«状态») (round : Fin 3) := do
  let s ← «依次» s [.«原样» (.«放货» 7 .«钢块» 300), .«原样» (.«放货» 6 .«钢块» 300),
    .«原样» (.«放货» 1 .«源石粉末» 50)]
  -- 调用 875–876、895–896、915–916，历时分别约 11.2/5.0、11.3/4.9、13.2/5.1 秒。
  let (aSpan, bSpan) : Nat × Nat := [(45,20),(45,20),(53,21)][round.val]!
  let (s, aPanel) := «逐步读» s aSpan (fun m => «箱里几件» m 1 .«源石粉末»)
  let s ← «做» s (.«原样» (.«放货» 2 .«砂叶种子» 50))
  let (s, bPanel) := «逐步读» s bSpan (fun m => «箱里几件» m 2 .«砂叶种子»)
  let (aRead, bRead) : Nat × Nat := if round == 2 then (48,49) else (50,50)
  guard (aPanel.contains aRead && bPanel.contains bRead)
  -- 调用 877、897、917：以乙返回为零，四箱约在第 13、15、17、19 秒采样。
  let a := «等» 52 s
  let b := «等» 8 a
  let c := «等» 8 b
  let d := «等» 8 c
  return («等» 4 d, [«箱货» a 1 .«源石粉末», «箱货» b 2 .«砂叶种子», «箱货» c 7 .«钢块», «箱货» d 6 .«钢块»])

/-- 回放：拉两格排货带后逐步看公共箱，记第一件补进去的货及其步号。
前两遍从实读首次换货的时刻起，按两个面板各自的采样时差查这段走步里的箱数。 -/
private def «排货» (s : Endfield.«格子».«状态») (round : Fin 3) (n : Nat) := do
  guard («格里» s.«模型» 6 == some «物品».«钢块»)
  let s ← «依次» s [.«建» (← «摆» 10 28 20 (.«传送带» .«上» .«下»)),
    .«建» (← «摆» 11 28 21 (.«传送带» .«上» .«下»))]
  let (t, rows) : Endfield.«格子».«状态» × List (Option «物品» × Nat × Nat × Nat × Nat) := «逐步读» s n fun m =>
    («格里» m 6, m.«件数» ⟨6, .«格» 0⟩ .«源石粉末», «箱里几件» m 6 .«钢块»,
      «箱里几件» m 9 .«钢块», «箱里几件» m 9 .«源石粉末»)
  let i ← rows.findIdx? fun (row : Option «物品» × Nat × Nat × Nat × Nat) => row.1.isSome && row.1 != some «物品».«钢块»
  let (slot, _) ← rows[i]?
  if round < 2 then
    -- 调用 879–880：08:31:05.93 → 40.18、42.36。899–900：08:35:30.95 → 08:36:09.69、11.93。
    let (common, drain, powder) : Nat × Nat × Nat := if round == 0 then (137,146,16) else (155,164,18)
    let (_, firstCount, coal, _, _) ← rows[i + common]?
    let (_, _, _, dischargedCoal, dischargedPowder) ← rows[i + drain]?
    guard (firstCount == 1 && coal == 250 && dischargedCoal == 50 && dischargedPowder == powder)
  return (t, i, ← slot)

/-- 回放：先拆排货带，再依次清空甲、乙、公共箱、远箱、排货箱，最后收掉该遍重搭的摆件。 -/
private def «清场» (s : Endfield.«格子».«状态») := do
  -- 08:31:43 和 08:36:13 起的两次拆带各约 3 秒。以下依次取各次清箱调用到下一次调用的整秒数。
  let mut s := «等» 12 (← «依次» s [.«收» 10, .«收» 11])
  for (u, seconds) in [(1, 4), (2, 4), (6, 11), (7, 10), (9, 5)] do
    for i in [:6] do
      let g := «格位».mk u (.«格» i)
      unless (s.«模型».«货» g).isEmpty do
        s ← «做» s (.«原样» (.«收货» g))
    s := «等» (4 * seconds) s
  «依次» s ([3, 4, 5, 8, 6, 7].map .«收»)

/-- 回放：三遍沿用两个货源箱和排货箱。前两遍从拉带走到拆带，最后一遍走到读箱结束。 -/
private def «三遍» := do
  let mut s ← «布置» [← «摆» 1 26 13 (.«协议储存箱» .«下»), ← «摆» 2 30 15 (.«协议储存箱» .«左»)]
  let mut rows := #[]
  -- 调用记录中这三段各约 138、143、107 秒。计步从排货带接好后的第一步起。
  for (r, steps) in ([(0, 552), (1, 572), (2, 428)] : List (Fin 3 × Nat)) do
    s ← «搭一遍» s r
    let (t, boxes) ← «放货读箱» s r
    let (t, first) ← «排货» t r steps
    rows := rows.push (boxes, first, ← «乙丙预计» t.«模型».«历史»)
    if r < 2 then s ← «清场» t
  return rows.toList

-- 每行依次是甲、乙、远箱、公共箱的实测件数，模型首次换货的步号与实测货种，乙、丙两种预计。
-- 第一、二遍读到碳粉末，第三遍读到砂叶种子。乙在第二遍失配，丙在第一、二遍失配。
#guard «三遍» == some [
  ([47, 49, 300, 300], (394, .«源石粉末»), .«源石粉末», .«砂叶种子»),
  ([47, 49, 300, 300], (394, .«源石粉末»), .«砂叶种子», .«砂叶种子»),
  ([47, 49, 300, 300], (394, .«砂叶种子»), .«砂叶种子», .«砂叶种子»)]

end Endfield.«回放».«贴箱分流器争第一格»
