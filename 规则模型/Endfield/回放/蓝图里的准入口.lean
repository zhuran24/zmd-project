import Endfield.«回放».«格子工具»

/-!
据：《实测-2026-11-27》第二节与第十三节补一。坐标为摆件左上角，i 向右、j 向下。
1 是货源箱，2 是进料准入口，3 是分流器，4 是待测准入口，5、6 分别是 G、B 箱。
碳块用钢块代，一组 50 件，无供电桩。每份在各自位置单独走货。

放货返回为第 0 步，放入 50 件和读货源箱都在该调用内，各自时刻未知。每秒 4 步，取最接近的整步。
各行步号来自《调用记录.jsonl》的两箱采样时刻和 reset_time.t0。摆法一手搭三件分别等 6、14、14 秒，其余各件等 16 秒，再逐箱采样。
下面分别在 G、B 的采样步读数。放货和重置之间保留全部走步。
-/

namespace Endfield.«蓝图里的准入口»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 回放：依手搭记录先建箱、分流器、两格进料带，再把第一格直带换成准入口。 -/
private def «手搭» («摆法二» «后放» : Bool) : Option Endfield.«格子».«状态» := do
  let source ← «摆» 1 23 13 (.«协议储存箱» .«下»)
  let split ← «摆» 3 24 18 (.«分流器» .«上»)
  let (boxes, gate, belts) ← if «摆法二» then do
    let b ← «摆» 6 22 20 (.«协议储存箱» .«下»)
    let g ← «摆» 5 26 17 (.«协议储存箱» .«右»)
    let gate ← «摆» 4 25 18 (.«物品准入口» .«右»)
    let belts ← [«摆» 8 23 18 (.«传送带» .«右» .«下»), «摆» 9 23 19 (.«传送带» .«上» .«下»)].mapM id
    pure ([source,b,g], gate, belts)
  else do
    let g ← «摆» 5 23 20 (.«协议储存箱» .«下»)
    let b ← «摆» 6 26 20 (.«协议储存箱» .«下»)
    let gate ← «摆» 4 24 19 (.«物品准入口» .«下»)
    let belts ← [«摆» 8 25 18 (.«传送带» .«左» .«右»), «摆» 9 26 18 (.«传送带» .«左» .«右»),
      «摆» 10 27 18 (.«传送带» .«左» .«下»), «摆» 11 27 19 (.«传送带» .«上» .«下»)].mapM id
    pure ([source,g,b], gate, belts)
  let s ← if «摆法二» then «布置» boxes else «依次» .«空» (boxes.map .«建»)
  let inlet ← [«摆» 12 24 16 (.«传送带» .«上» .«下»), «摆» 7 24 17 (.«传送带» .«上» .«下»),
    «摆» 2 24 16 (.«物品准入口» .«下»)].mapM id
  let s ← «依次» s (((split :: inlet) ++ (if «后放» then belts ++ [gate] else gate :: belts)).map .«建»)

  let s ← «做» s (.«原样» (.«设准入口» 4 (some .«钢块») none none))
  -- 补一存图时只设了待测准入口（调用 771–774），第二节两处都已设。
  if «后放» then return s
  «做» s (.«原样» (.«设准入口» 2 (some .«钢块») (some 1) none))

/-- 回放：取手搭场地的成品摆件，按实测平移。从准许的同类建成先后中取一种；
补一的带子虽先手搭，放蓝图仍须排在非带单位之后。模型没有存蓝图或点选操作。 -/
private def «放一份» (s : Endfield.«格子».«状态») («右移» : Nat) («空格有分流器» : Bool) := do
  let ps : List «摆件» ← s.«场地».mapM fun (p : «摆件») => «摆» p.«号» (p.«位置».i.val + «右移») p.«位置».j.val p.«种类»
  let start ← if «空格有分流器» then do
    «做» .«空» (.«建» (← «摆» 13 33 14 (.«分流器» .«上»)))
    else pure Endfield.«格子».«状态».«空»
  let (belts, units) := ps.partition «摆件».«是传送带»
  -- 模型自检：让待测准入口排在出口带之后，蓝图操作应拒绝这个建成顺序。
  let (gate, other) := units.partition (fun (p : «摆件») => p.«号» == 4)
  guard ((«做» start (.«蓝图» (other ++ belts ++ gate))).isNone)
  «做» start (.«蓝图» (units ++ belts))

/-- 回放：按记录准备两个准入口并往货源箱放一组货。 -/
private def «放一组» (s : Endfield.«格子».«状态») :=
  «依次» s [.«原样» (.«设准入口» 4 (some .«钢块») none none),
    .«原样» (.«设准入口» 2 (some .«钢块») (some 1) none), .«原样» (.«放货» 1 .«钢块» 50)]

/-- 回放：枚举放货早于返回几步。源箱采样可以是放入 50 件到返回之间的任一步；
只有这段里读得到面板件数的偏移才保留。采样到返回可以继续走步。 -/
private def «放货偏移» (s : Endfield.«格子».«状态») (window panel : Nat) : List Nat :=
  let (_, counts) := «逐步读» s window fun m => «箱里几件» m 1 .«钢块»
  (List.range (window + 1)).filter fun early => (counts.take (early + 1)).contains panel

/-- 回放：从调用返回处的状态继续走，G、B 读数和重置都按各自的钟面时刻。 -/
private def «三件» (s : Endfield.«格子».«状态») («时刻» : List (Nat × Nat × Nat)) := do
  let mut s := s
  let mut now := 0
  let mut counts := []
  let mut outlets := []
  for (g,b,next) in «时刻» do
    s := «等» (g - now) s
    let inG := «箱货» s 5 .«钢块»
    s := «等» (b - g) s
    counts := counts ++ [(inG, «箱货» s 6 .«钢块»)]
    let outlet ← s.«模型».«分流器上次» 3
    outlets := outlets ++ [outlet.«止»]
    if next > 0 then
      s ← «做» («等» (next - b) s) (.«原样» (.«重置计数» 2))
      now := next
  return (counts, outlets, s)

/-- 回放：固定 G、B 的采样和重置时刻，逐个复算与放货面板相容的偏移。摆法一手搭
实读的首行为空，模型的界点另在「短窗口」核对；其余双箱读数要在整个候选范围内都相符。
在通过实读的历史中取一份作存图的原场。 -/
private def «核三件» (s : Endfield.«格子».«状态») (window panel : Nat)
    (times : List (Nat × Nat × Nat)) (expected : List (Nat × Nat)) (outlets : List Nat) := do
  let s ← «放一组» s
  let mut saved := none
  for early in «放货偏移» s window panel do
    let (r, exits, after) ← «三件» («等» early s) times
    if expected.head? == some (0,0) && early ≥ 22 then
      guard (r == (0,1) :: expected.drop 1)
    else
      guard (r == expected)
      if saved.isNone then saved := some after
    guard (exits == outlets)
  saved

/-- 回放：一份手搭和从这张图放下的各份共用摆件。摆法二用走过三件的场地作原件，
另两种用放货前的场地。每份先看放置产生的新状态，再按记录中的设定走货。 -/
private def «核一组» («摆法二» «后放» : Bool) («手搭时刻» : List (Nat × Nat × Nat))
    («蓝图各份» : List (Nat × Bool × Nat × Nat × List (Nat × Nat × Nat))) : Option Bool := do
  let s ← «手搭» «摆法二» «后放»
  if «后放» then
    -- 补一调用 772–774：存图后、手搭放货前，进料口仍未设。
    let inlet := s.«模型».«准入口» 2
    guard (inlet.«放行».isNone && inlet.«累计上限».isNone && inlet.«累计已收» == 0)
  let bgb := [(0,1), (1,1), (1,2)]
  let expected := if «后放» then [(1,0), (1,1), (2,1)] else
    if «摆法二» then bgb else [(0,0), (1,1), (1,2)]
  -- 调用 211、296、775 的放货面板都是 50。最后一列出口只作模型自检。
  let window := if «后放» then 51 else if «摆法二» then 48 else 54
  let after ← «核三件» s window 50 «手搭时刻» expected (if «后放» then [4,8,4] else [8,4,8])
  if «摆法二» && (after.«模型».«准入口» 2).«累计已收» != 1 then return false
  for ((dx, occupied, window, panel, times), index) in «蓝图各份».zipIdx do
    let copy ← «放一份» (if «摆法二» then after else s) dx occupied
    -- 第二节第 77–79 行。摆法二末份只读 G 箱模式，前两份读货源箱和进料准入口。
    if «摆法二» then
      let box := if index == 2 then 5 else 1
      if (copy.«模型».«储存箱» box).«仓储模式» then return false
      if box == 1 && «箱货» copy 1 .«钢块» != 0 then return false
    -- 模型值：蓝图刚落地时，两口的放行物品和累计上限都为空。模型的蓝图只带摆件，
    -- 放货前由「放一组」另设两口。游戏中设过的跟图带下来：第二节调用 226、254、269、
    -- 310、319 读进料口为碳块、上限 1、累计 0；223、253、308、317 读待测口放行碳块。
    for u in [2,4] do
      let gate := copy.«模型».«准入口» u
      guard (gate.«放行».isNone && gate.«累计上限».isNone)
    -- 补一存图时进料口本来就未设，落地读到未设和累计 0（782），随后才设成限放 1（783）。
    if !«摆法二» || index < 2 then guard ((copy.«模型».«准入口» 2).«累计已收» == 0)
    let _ ← «核三件» copy window panel times bgb [8,4,8]
  return true

-- 各蓝图依次列平移、是否预放分流器、放货调用长度（折为步数）、调用内的源箱读数和三件的时刻。
-- (G 读数步，B 读数步，下一次重置步；0 表示结束)。摆法一的第三份蓝图
-- 在 (33,14) 先放分流器。手搭首件在短窗口内两箱皆空，B、G、B 是记录的轮询推断。
-- 第二节第 61–64 行；调用记录从 211、228、256、271 行开始。
#guard «核一组» false false [(28,35,43),(113,121,129),(198,206,0)] [
  (0,false,54,49,[(68,75,84),(160,168,176),(252,259,0)]),
  (6,false,55,49,[(68,75,83),(161,168,176),(253,260,0)]),
  (6,true,54,50,[(68,75,83),(159,167,174),(251,258,0)])] == some true

-- 第二节第 70–73 行；调用记录从 296、311、320、332 行开始。
#guard «核一组» true false [(68,76,84),(161,168,176),(253,261,0)] [
  (0,false,54,49,[(68,75,83),(161,169,177),(253,261,0)]),
  (7,false,55,50,[(68,75,83),(160,167,175),(251,259,0)]),
  (7,false,54,49,[(68,75,83),(161,169,177),(253,260,0)])] == some true

-- 第十三节补一第 333–334 行；调用记录从 775、784 行开始。
#guard «核一组» false true [(68,76,84),(160,168,176),(252,260,0)] [
  (6,false,58,49,[(68,75,83),(161,169,177),(253,261,0)])] == some true

/-- 回放：调用 211 长 13.525 秒。逐一改变放货偏移，G、B 的采样仍固定在返回后
第 28、35 步。放货面板的 50 件也要能在这次调用内读到。 -/
private def «短窗口» := do
  let s ← «放一组» (← «手搭» false false)
  let (_, rows) := «逐步读» s (54 + 35) fun m => («箱里几件» m 5 .«钢块», «箱里几件» m 6 .«钢块»)
  return («放货偏移» s 54 50).filter fun early =>
    rows[early + 28]?.map Prod.fst == some 0 && rows[early + 35]?.map Prod.snd == some 0

-- 实读首行 (0,0)。按本回放的整步对时，提前 0–21 步相容；22 步是模型界点。
#guard «短窗口» == some (List.range 22)

end Endfield.«蓝图里的准入口»
