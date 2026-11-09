import Endfield.«通道与移动»

/-!
# 拓扑与级别

规则文件「拓扑与级别」一块里的元件、运输带、终点、终点的时刻、次序。组、组的时刻、级别还没写。

每个量都从布局或历史算出来，不另存一份。元件用它的出口格指代：特别运输单位就是它自己，
一段连续传送带是最后那一格（物品从这一格离开这段传送带）。
-/

namespace Endfield

namespace «布局»

/-- 据：元件

运输单位 u 在哪个元件里，返回那个元件的出口格。传送带格顺着通往下一格传送带的通道走到头；
`fuel` 是最多走几格，一圈首尾相接的传送带走不到头，结果是 `none`。 -/
def «所在元件» (L : «布局») : Nat → «单位号» → Option «单位号»
  | 0, _ => none
  | fuel + 1, u =>
    match L.«种类» u with
    | some .«传送带» =>
      match (L.«出» u).find? fun p => L.«种类» p.1.«止» == some .«传送带» with
      | some p => L.«所在元件» fuel p.1.«止»
      | none => some u
    | some k => if k.«是运输单位» then some u else none
    | none => none

/-- 元件：一个特别运输单位（桥接器的每个物品格连同与它相连的端口各算一个），或一段首尾相接、不能再延长的连续传送带

布局里的全部元件，各用出口格指代。 -/
def «元件» (L : «布局») : List «单位号» :=
  (List.range L.«单位表».length).filter fun u => L.«所在元件» 1 u == some u

/-- 据：运输带

末端元件：有取货通道，而且取货通道都通往非运输单位的元件。
取货端口什么都没接的元件（断头带的最后一段）不算末端元件，它不在任何运输带上。 -/
def «是末端元件» (L : «布局») (e : «单位号») : Bool :=
  L.«元件».contains e && !(L.«出» e).isEmpty && (L.«出» e).all fun p => L.«是非运输单位» p.1.«止»

/-- 据：运输带

元件 e 直接输出到的元件。 -/
def «下游元件» (L : «布局») (e : «单位号») : List «单位号» :=
  (L.«出» e).filterMap fun p => L.«所在元件» (L.«单位表».length + 1) p.1.«止»

/-- 运输带：一条线上依次输出、且末端元件的取货端口只与非运输单位相连的一串元件（可以只有一个元件）

从元件 e 起、到末端元件为止的每一串元件。e 所在的每条运输带，从 e 往后的那一段都在这里面；
e 在其中一条上的次序就是那一串的长度。`fuel` 是一串最多几个元件。 -/
def «运输带从» (L : «布局») : Nat → «单位号» → List (List «单位号»)
  | 0, _ => []
  | fuel + 1, e =>
    if L.«是末端元件» e then [[e]]
    else (L.«下游元件» e).flatMap fun f => (L.«运输带从» fuel f).map (e :: ·)

/-- 终点：一条运输带末尾连接的非运输单位；末端元件是分流器的运输带，以该分流器为终点

末端元件 e 的运输带的终点；e 不是末端元件时是 `none`。
不是分流器的末端元件只有一个取货端口，取货通道正好一条；不是一条的情况这里不给结果。 -/
def «终点» (L : «布局») (e : «单位号») : Option «单位号» :=
  if !L.«是末端元件» e then none
  else if L.«种类» e == some .«分流器» then some e
  else
    match L.«出» e with
    | [p] => some p.1.«止»
    | _ => none

/-- 据：终点

x 是不是某条运输带的终点。 -/
def «是终点» (L : «布局») (x : «单位号») : Bool :=
  L.«元件».any fun e => L.«终点» e == some x

end «布局»

/-- 工具：`p` 在时刻 `now` 成立时，它最近一次从不成立变成成立的那一刻；`now` 时不成立是 `none`。 -/
def «最近一次变成» (p : «时刻» → Bool) : «时刻» → Option «时刻»
  | 0 => if p 0 then some 0 else none
  | t + 1 =>
    if p (t + 1) then
      if p t then «最近一次变成» p t else some (t + 1)
    else none

namespace «历史»

/-- 终点的时刻：

    - 非运输单位：它最近一次从“不是终点”变成“是终点”、末端元件与它接通的那一刻；
    - 分流器：它最近一次从“没有通往非运输单位的通道”变成“有”的那一刻

x 在时刻 `now` 不是终点时是 `none`。 -/
def «终点的时刻» (H : «历史») (now : «时刻») (x : «单位号») : Option «时刻» :=
  let L := H.«布局于» now
  if !L.«是终点» x then none
  else if L.«种类» x == some .«分流器» then
    «最近一次变成» (fun t =>
      let Lt := H.«布局于» t
      (Lt.«出» x).any fun p => Lt.«是非运输单位» p.1.«止») now
  else «最近一次变成» (fun t => (H.«布局于» t).«是终点» x) now

/-- 据：次序

先比终点的时刻、再比次序，取靠前的那个。 -/
def «较先» (a b : «时刻» × Nat) : «时刻» × Nat :=
  if a.1 < b.1 || (a.1 == b.1 && a.2 ≤ b.2) then a else b

/-- 次序：运输带上的元件从末端元件起依次为 1、2、3……；一个元件在多条运输带上时，取通往“终点的时刻”最早的运输带中最小的次序

照定义算：列出从 e 起的每一串运输带，各配上它终点的时刻和 e 在上面的次序，取终点的时刻最早的里面次序最小的。
e 不在任何运输带上时是 `none`。 -/
def «次序» (H : «历史») (now : «时刻») (e : «单位号») : Option Nat :=
  let L := H.«布局于» now
  let cands := (L.«运输带从» (L.«单位表».length + 1) e).filterMap fun P =>
    ((P.getLast?.bind L.«终点»).bind (H.«终点的时刻» now)).map fun t => (t, P.length)
  match cands with
  | [] => none
  | c :: cs => some (cs.foldl «较先» c).2

end «历史»

end Endfield
