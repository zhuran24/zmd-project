import Endfield.«格子».«几何与端口»

/-!
场地只存摆件，按建成先后排列。建造、拆除、蓝图、重建都返回事件，
不改已有状态机。失败返回 none；蓝图是调用者指定的完整建造先后。
-/

namespace Endfield.«格子»

/-- 据：基地、接通
场地中的摆件，按建成先后。 -/
abbrev «场地» := List «摆件»

/-- 据：协议核心
摆件是否为协议核心。 -/
def «摆件».«是核心» (p : «摆件») : Bool :=
  match p.«种类» with | .«协议核心» _ => true | _ => false

/-- 据：传送带、蓝图
蓝图分组只把普通传送带归为传送带。 -/
def «摆件».«是传送带» (p : «摆件») : Bool :=
  match p.«种类» with | .«传送带» _ _ => true | _ => false

/-- 框架：摆件标识占用的编号。
供电桩也保留自己的摆件号以便收回；它不生成状态机单位。桥接器另占连续三个号。
这是命名约束，不表示供电桩在现有模型里有物品格。 -/
def «摆件».«占号» (p : «摆件») : List Nat :=
  if p.«种类» == .«桥接器» then (List.range 4).map (p.«号» + ·) else [p.«号»]

/-- 据：仓库取货口、基地
仓库取货口背向取货端口的长边必须贴基地边界；其他摆件没有这一额外条件。 -/
def «摆件».«贴边» (p : «摆件») : Bool :=
  match p.«种类» with
  | .«仓库取货口» .«上» => p.«位置».j.val + p.«大小».2 == 70
  | .«仓库取货口» .«右» => p.«位置».i.val == 0
  | .«仓库取货口» .«下» => p.«位置».j.val == 0
  | .«仓库取货口» .«左» => p.«位置».i.val + p.«大小».1 == 70
  | _ => true

/-- 据：基地、格、协议核心、仓库取货口
完整矩形在场地里摆得下：不越界、不重叠、不重号，核心至多一个，取货口贴边。
传送带两端不同边也在这里检查；物品准入口的替换前提另查。 -/
def «场地».«摆得下» (s : «场地») (p : «摆件») : Bool :=
  match p.«占格», s.mapM «摆件».«占格» with
  | some cs, some old =>
    p.«贴边» && !(old.flatten.any cs.contains) &&
    !(s.any fun q => q.«占号».any p.«占号».contains) &&
    (!p.«是核心» || !s.any «摆件».«是核心») &&
    (match p.«种类» with | .«传送带» a b => a != b | _ => true)
  | _, _ => false

/-- 据：接通、通道
遍历新摆件端口，求与已有摆件的接通事件。
合法场地上一个端口至多有一个相配端口；发现多个时失败，不拿旧摆件表顺序破同。 -/
def «场地».«接通事件» (s : «场地») (o : «接通先后») (p : «摆件») : Option «历史» := do
  let ps ← p.«端口» o
  let qs ← s.mapM fun q => do return (q, ← q.«端口» o)
  let es ← ps.mapM fun a =>
    let cs := qs.flatMap fun (q, bs) => bs.filterMap («形成通道» p q a)
    match cs with
    | [] => some []
    | [c] => some [«事件».«接通» c]
    | _ => none
  return es.flatten

/-- 据：接通、桥接器
建成的单位先发出事件，再按新摆件的端口先后接通；期间没有走步。 -/
def «场地».«建成» (s : «场地») (o : «接通先后») (p : «摆件») :
    Option («场地» × «历史») := do
  if !s.«摆得下» p then none else do
    let es ← s.«接通事件» o p
    return (s ++ [p], (p.«单位».map fun (u,k) => .«建成» u k) ++ es)

/-- 据：接通、桥接器、供电桩
按摆件的号收回整件；桥接器四个单位依上右下左拆除，供电桩只移出场地。 -/
def «场地».«收» (s : «场地») (u : Nat) : Option («场地» × «历史») :=
  match s.filter (·.«号» == u) with
  | [p] => some (s.filter (·.«号» != u), p.«单位».map fun (v,_) => .«拆除» v)
  | _ => none

/-- 据：物品准入口、传送带
普通建造准入口必须替换同位置、同取货方向的一格直带。
先拆带，后建准入口；替换允许沿用原号或换成未占用的新号。 -/
def «场地».«建» (s : «场地») (o : «接通先后») (p : «摆件») :
    Option («场地» × «历史») := do
  match p.«种类» with
  | .«物品准入口» d =>
    let qs := s.filter fun q => q.«位置» == p.«位置» &&
      (match q.«种类» with | .«传送带» a b => a == b.«对边» && b == d | _ => false)
    match qs with
    | [q] =>
      let (s', es) ← s.«收» q.«号»
      let (s'', fs) ← s'.«建成» o p
      return (s'', es ++ fs)
    | _ => none
  | _ => «场地».«建成» s o p

/-- 蓝图：一次建造一组单位并逐个建成；传送带均在非传送带单位之后建成，两类各自内部的建成先后无法确定
输入表本身就是调用者指定的先后；第一个传送带后面只能是传送带。 -/
def «蓝图先后» (ps : List «摆件») : Bool :=
  (ps.dropWhile fun p => !p.«是传送带»).all «摆件».«是传送带»

/-- 据：蓝图、接通
逐件建蓝图；任一件不合法时整次操作没有结果。顺序不由编号或坐标补定。 -/
def «场地».«放蓝图» (s : «场地») (o : «接通先后») (ps : List «摆件») :
    Option («场地» × «历史») :=
  if !«蓝图先后» ps then none else
    ps.foldlM (fun (s, es) p => do
      let (s', fs) ← s.«建» o p
      return (s', es ++ fs)) (s, [])

/-- 框架：离线按给定先后从空场地重建，准入口可以直接建于空格。
先后必须恰好包含原场地全部摆件；重建本身也检查重号、重叠及几何条件。
离线顺序没有蓝图的两类先后限制。 -/
def «场地».«重建» (s : «场地») (o : «接通先后») (ps : List «摆件») : Option «历史» := do
  if ps.length != s.length || !ps.all s.contains then none else do
    let (_, es) ← ps.foldlM (fun (s, es) p => do
      let (s', fs) ← «场地».«建成» s o p
      return (s', es ++ fs)) (([] : «场地»), ([] : «历史»))
    return es

end Endfield.«格子»
