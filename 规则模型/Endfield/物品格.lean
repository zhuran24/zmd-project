import Endfield.«框架»

/-!
# 端口与物品格、移动（不带端口的位置）

规则文件「端口与物品格」「通道与移动」两块里和货有关的部分：

- 一条通道的起点里这时能送的是哪件（`可移动物品`）；
- 一件物品进一个单位时放进哪一格、收不收得下（`放进哪`）；
- 一件物品经一条通道移过去以后，状态的每一样怎样变（`移一件`）。

哪条通道在哪一刻轮到、轮到了能不能移，是移动判定的事，不在这里。
端口的位置等格子写出来再说；一条通道接在协议核心的第几个取货端口上，先放在 `待写.口` 里。
-/

namespace Endfield

/-- 据：物品格、仓库

一件货所在的地方：某个单位的某个物品格，或者仓库。 -/
inductive «货位» where
  | «格» (g : «格位»)
  | «仓库»
deriving DecidableEq, Repr

/-- 工具：一格的货里添 n 件 x。 -/
def «添几件» (l : List «一堆») (x : «物品») (n : Nat) : List «一堆» :=
  if n == 0 then l
  else if l.any (·.«物» == x) then
    l.map fun p => if p.«物» == x then { p with «件数» := p.«件数» + n } else p
  else l ++ [⟨x, n⟩]

/-- 工具：一格的货里拿走 n 件 x；拿空了的那一堆不留。 -/
def «拿几件» (l : List «一堆») (x : «物品») (n : Nat) : List «一堆» :=
  (l.map fun p => if p.«物» == x then { p with «件数» := p.«件数» - n } else p).filter (·.«件数» > 0)

namespace «状态»

/-- 据：物品格

格 g 里有几件 x。 -/
def «件数» (s : «状态») (g : «格位») (x : «物品») : Nat :=
  ((s.«货» g).filter (·.«物» == x)).foldl (fun acc p => acc + p.«件数») 0

/-- 据：起点、可移动物品、协议储存箱、仓库

通道 c 的起点里这时能送的那件物品和它所在的地方；没有是 `none`。
- 运输单位：物品格里那件，须已停满 1 tick；
- 协议储存箱：编号最小的非空物品格里的物品；
- 制造单位：取货物品格里的物品；
- 协议核心、仓库取货口：这条通道接的取货端口指向的那种物品，仓库里有才算。
`L` 是 s 的布局，由用它的地方算好传进来（下同）；`port` 给出一条通道接在第几个取货端口上（现在取自 `待写.口`）。 -/
def «可移动物品» (L : Endfield.«布局») (port : «通道» → Nat) (s : «状态») (c : «通道») : Option («物品» × «货位») :=
  let u := c.«起»
  match L.«种类» u with
  | some .«传送带» | some .«分流器» | some .«汇流器» | some .«物品准入口» | some .«桥接器格» =>
    match s.«货» ⟨u, .«格» 0⟩ with
    | p :: _ =>
      if s.«已停» ⟨u, .«格» 0⟩ ≥ «tick» then some (p.«物», .«格» ⟨u, .«格» 0⟩) else none
    | [] => none
  | some .«协议储存箱» =>
    (List.range 6).findSome? fun i =>
      match s.«货» ⟨u, .«格» i⟩ with
      | p :: _ => some (p.«物», .«格» ⟨u, .«格» i⟩)
      | [] => none
  | some (.«制造» _) =>
    match s.«货» ⟨u, .«取货»⟩ with
    | p :: _ => some (p.«物», .«格» ⟨u, .«取货»⟩)
    | [] => none
  | some .«协议核心» | some .«仓库取货口» =>
    (s.«取货指向» u (port c)).bind fun x =>
      if s.«仓库» x > 0 then some (x, .«仓库») else none
  | none => none

/-- 据：物品格、存货/取货物品格、协议储存箱、物品准入口、协议核心

物品 x 经通道 c 进 c.止 时放进哪里；收不下是 `none`。
- 传送带、分流器、汇流器、桥接器格：物品格空着才收（上限 1）。汇流器这一步只通过哪条通道收货是输入判定的事，不在这里；
- 物品准入口：物品格空着，而且没有阻断（没设放行的物品时什么都放行；物品不符或任一上限用尽时阻断）；
- 协议储存箱：编号最小的能放它的物品格（空格，或放着同种物品且不到 50 件的格）；
- 制造单位：已经放着这种物品的那个存货物品格（不到 50 件才收；同种物品只能占一格，所以满了不会另占一格）；
  都没放着这种物品时，放进编号最小的空存货物品格（没测：规则没说哪个空格，两个格没有分别）；
- 协议核心：仓库里这种物品不到 80000 件才收；仓库取货口没有存货端口。 -/
def «放进哪» (L : Endfield.«布局») (s : «状态») (c : «通道») (x : «物品») : Option «货位» :=
  let v := c.«止»
  match L.«种类» v with
  | some .«传送带» | some .«分流器» | some .«汇流器» | some .«桥接器格» =>
    if (s.«货» ⟨v, .«格» 0⟩).isEmpty then some (.«格» ⟨v, .«格» 0⟩) else none
  | some .«物品准入口» =>
    let g := s.«准入口» v
    let ok1 :=
      match g.«放行» with
      | some y => y == x
      | none => true
    let ok2 :=
      match g.«累计上限» with
      | some n => g.«累计已收» < n
      | none => true
    let ok3 :=
      match g.«每5tick上限» with
      | some n => g.«本段已收» < n
      | none => true
    if (s.«货» ⟨v, .«格» 0⟩).isEmpty && ok1 && ok2 && ok3 then some (.«格» ⟨v, .«格» 0⟩) else none
  | some .«协议储存箱» =>
    ((List.range 6).find? fun i =>
      match s.«货» ⟨v, .«格» i⟩ with
      | [] => true
      | p :: _ => p.«物» == x && p.«件数» < 50).map fun i => .«格» ⟨v, .«格» i⟩
  | some (.«制造» k) =>
    let slots := List.range k.«存货物品格数»
    match slots.find? fun i => (s.«货» ⟨v, .«存货» i⟩).any (·.«物» == x) with
    | some i => if s.«件数» ⟨v, .«存货» i⟩ x < 50 then some (.«格» ⟨v, .«存货» i⟩) else none
    | none => (slots.find? fun i => (s.«货» ⟨v, .«存货» i⟩).isEmpty).map fun i => .«格» ⟨v, .«存货» i⟩
  | some .«协议核心» => if s.«仓库» x < 80000 then some .«仓库» else none
  | some .«仓库取货口» => none
  | none => none

/-- 据：移动、可移动物品

通道 c 这时能不能移一件：起点里有可移动物品，那一头收得下，而且不是移回它刚离开的上一物品格。
能移时给出那件物品、它现在在哪、要放进哪。汇流器的输入判定不在这里管。 -/
def «能移» (L : Endfield.«布局») (port : «通道» → Nat) (s : «状态») (c : «通道») :
    Option («物品» × «货位» × «货位») :=
  match s.«可移动物品» L port c with
  | some (x, src) =>
    match s.«放进哪» L c x with
    | some dst =>
      let back :=
        match src, dst with
        | .«格» a, .«格» b => s.«来处» a == some b
        | _, _ => false
      if back then none else some (x, src, dst)
    | none => none
  | none => none

/-- 框架：一件物品 x 从 src 经通道 c 移到 dst 以后的状态（一次移动）。

每个字段行尾是这一格的着落，写法同 `作用.lean`。前提（`能移` 给出的就是这三样）由用它的地方保证。 -/
def «移一件» (L : Endfield.«布局») (s : «状态») (c : «通道») (x : «物品») (src dst : «货位») : «状态» where
  «历史» := s.«历史»    -- 无关
  «货» := fun g =>    -- 据：移动
    let l := if src = .«格» g then «拿几件» (s.«货» g) x 1 else s.«货» g
    if dst = .«格» g then «添几件» l x 1 else l
  «已停» := fun g =>    -- 据：滞留（进来的那一步从零算起）
    if src = .«格» g || dst = .«格» g then 0 else s.«已停» g
  «来处» := fun g =>    -- 据：移动（不会移回刚离开的上一物品格）
    if dst = .«格» g then
      match src with
      | .«格» h => if L.«是运输单位» g.«单位» then some h else none
      | .«仓库» => none
    else if src = .«格» g then none
    else s.«来处» g
  «分流器上次» :=    -- 据：元件轮询（上一次移动物品的通道）
    if L.«种类» c.«起» == some .«分流器» then «换» s.«分流器上次» c.«起» (some c)
    else s.«分流器上次»
  «进货上次» :=    -- 据：元件轮询、输入判定（上一次移动物品的通道）
    if L.«算进货» c then «换» s.«进货上次» c.«止» (some c) else s.«进货上次»
  «出货已移动» :=    -- 据：非运输单位轮询（已移动过物品的通道按最近一次移动的先后）
    if L.«算出货» c then
      «换» s.«出货已移动» c.«起» ((s.«出货已移动» c.«起»).filter (· != c) ++ [c])
    else s.«出货已移动»
  «制造中» := s.«制造中»    -- 无关
  «准入口» :=    -- 实测：没设累计上限时不计数（操控工具说明，2026-10-08）；每 5 tick 那项照样处理、那 5 tick 是 40 步，是没测
    if L.«种类» c.«止» == some .«物品准入口» then
      let g := s.«准入口» c.«止»
      «换» s.«准入口» c.«止»
        { g with
          «累计已收» := if g.«累计上限».isSome then g.«累计已收» + 1 else g.«累计已收»
          «本段已收» := if g.«每5tick上限».isSome then g.«本段已收» + 1 else g.«本段已收»
          «本段还剩» :=
            if g.«每5tick上限».isSome then
              match g.«本段还剩» with
              | some n => some n
              | none => some (5 * «tick»)
            else g.«本段还剩» }
    else s.«准入口»
  «储存箱» := s.«储存箱»    -- 无关
  «开关» := s.«开关»    -- 无关
  «取货指向» := s.«取货指向»    -- 无关
  «仓库» := fun y =>    -- 据：仓库（进协议核心的进仓库，从取货端口出去的出仓库）
    if y = x then
      s.«仓库» y + (if dst = .«仓库» then 1 else 0) - (if src = .«仓库» then 1 else 0)
    else s.«仓库» y

end «状态»

end Endfield
