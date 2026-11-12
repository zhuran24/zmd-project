import Endfield.«格子».«场地与建造»
import Endfield.«作用»

/-!
从场地实现供电、仓库取货口编号、玩家放货，并把整件建造等操作交给现有 `作用`。
所有布局变化先算完整事件表，再连续执行；不能夹入一步。
-/

namespace Endfield.«格子»

/-- 据：供电桩、供电状态
供电桩左上角 (i,j) 的范围为 i−5 到 i+6、j−5 到 j+6；用整数避免下溢。 -/
def «供电范围» (p : «摆件») (c : «格») : Bool :=
  let i : Int := p.«位置».i.val
  let j : Int := p.«位置».j.val
  let x : Int := c.i.val
  let y : Int := c.j.val
  i - 5 ≤ x && x ≤ i + 6 && j - 5 ≤ y && y ≤ j + 6

/-- 据：供电桩、供电状态、需电功能
仅制造单位和协议储存箱需电；占格中任一格在某根供电桩的范围内即有电。
没有该单位、非需电单位或越界摆件均没有供电状态。 -/
def «场地».«有电» (s : «场地») (u : «单位号») : Bool :=
  s.any fun p =>
    p.«号» == u &&
    (match p.«种类» with | .«制造» _ _ | .«协议储存箱» _ => true | _ => false) &&
    (match p.«占格» with
     | none => false
     | some cs => cs.any fun c => s.any fun q =>
       q.«种类» == .«供电桩» && q.«占格».isSome && «供电范围» q c)

/-- 据：协议核心、仓库取货口
仓库取货端口的固定编号表，与接通先后无关。
核心按上右下左筛取货边，每边按第 2、5、8 格排列：上下型为上 0～2、下 3～5，
左右型为右 0～2、左 3～5。仓库取货口唯一端口为 0。其他种类没有仓库取货端口。 -/
def «摆件».«仓库取货端口» (p : «摆件») : Option (List Endfield.«格子».«端口») := do
  let _ ← p.«占格»
  match p.«种类» with
  | .«协议核心» a => («核心边格» a true).mapM fun (d,n) => p.«造端口» true d n
  | .«仓库取货口» d => return [← p.«造端口» true d 1]
  | _ => return []

/-- 据：协议核心、仓库取货口、通道
找一条通道的仓库取货端口编号；没有唯一匹配时返回 none。
已有场地的端口表只用于匹配，至多一条，不拿表顺序破同。 -/
def «场地».«口?» (s : «场地») (o : «接通先后») (c : «通道») : Option Nat := do
  let rows ← s.mapM fun p => do return (p, ← p.«端口» o)
  let found ← s.mapM fun p => do
    let ps ← p.«仓库取货端口»
    return ps.zipIdx |>.filterMap fun (a, i) =>
      if a.«单位» == c.«起» && rows.any (fun (q,bs) =>
        bs.any fun b => «形成通道» p q a b == some c) then some i else none
  match found.flatten with
  | [i] => some i
  | _ => none

/-- 据：物品格、协议储存箱、存货/取货物品格
一件件尝试放入箱子或制造单位；满了的剩余件不放，不改其他状态。
复用现有 `放进哪` 的箱子、制造单位分支，包括制造单位同物品只占一个存货格。 -/
def «放进单位» (s : Endfield.«状态») (u : «单位号») (x : «物品») (n : Nat) :
    «格位» → List «一堆» :=
  let L := s.«布局»
  let names := match L.«种类» u with
    | some .«协议储存箱» => (List.range 6).map «格名».«格»
    | some (.«制造» k) => (List.range k.«存货物品格数»).map «格名».«存货»
    | _ => []
  -- 先读一次目标单位的存货格，避免连续放货形成的函数在每次试放时重新求值。
  let stock : List («格位» × List «一堆») := names.map fun name =>
    let g := «格位».mk u name
    (g, s.«货» g)
  let read := fun (tab : List («格位» × List «一堆»)) g =>
    match tab.find? (·.1 == g) with
    | some (_, ps) => ps
    | none => s.«货» g -- 本次放货不改的格，保留原值。
  let result := (List.range n).foldl (fun tab _ =>
    if names.isEmpty then tab else
      let t := { s with «货» := read tab }
      match t.«放进哪» L ⟨u, u⟩ x with
      | some (.«格» g) => tab.map fun (h,ps) => (h, if h == g then «添几件» ps x 1 else ps)
      | _ => tab) stock
  read result

/-- 框架：场地对应的待写实现；无效通道的口编号由调用者显式给出。
现有 `待写.口` 对所有通道必须返回 Nat，无法表达不存在或多个匹配；
这里不把查找失败默认为 0，也不宣称该输入不会发生。`bad` 只在 `口?` 失败时调用。
合法几何所生成的核心、仓库取货通道有唯一匹配，编号由位置确定，不受 bad 影响。 -/
def «场地».«待写» (s : «场地») (o : «接通先后») (bad : «通道» → Nat) : Endfield.«待写» where
  «有电» := fun _ u => s.«有电» u
  «口» := fun _ c => match s.«口?» o c with | some i => i | none => bad c
  «放进单位» := «放进单位»

/-- 框架：场地和现有状态；场地按建成先后。通过本层操作保持两者同步。 -/
structure «状态» where
  «场地» : «场地»
  «模型» : Endfield.«状态»

/-- 框架：空场地及空状态。 -/
def «状态».«空» : «状态» := ⟨[], Endfield.«状态».«空»⟩

/-- 框架：原样交给现有作用的操作；类型里不包含改布局和离线。 -/
inductive «原样操作» where
  | «走一步»
  | «设准入口» (u : «单位号») (x : Option «物品») (a b : Option Nat)
  | «重置计数» (u : «单位号»)
  | «设储存箱模式» (u : «单位号») (b : Bool)
  | «设取货指向» (u : «单位号») (i : Nat) (x : Option «物品»)
  | «拨开关» (us : List «单位号») (b : Bool)
  | «放货» (u : «单位号») (x : «物品») (n : Nat)
  | «收货» (g : «格位»)
  | «入库» (x : «物品») (n : Nat)
  | «出库» (x : «物品») (n : Nat)

/-- 框架：原样操作对应现有操作。 -/
def «原样操作».«模型操作» : «原样操作» → Endfield.«操作»
  | .«走一步» => .«走一步»
  | .«设准入口» u x a b => .«设准入口» u x a b
  | .«重置计数» u => .«重置计数» u
  | .«设储存箱模式» u b => .«设储存箱模式» u b
  | .«设取货指向» u i x => .«设取货指向» u i x
  | .«拨开关» us b => .«拨开关» us b
  | .«放货» u x n => .«放货» u x n
  | .«收货» g => .«收货» g
  | .«入库» x n => .«入库» x n
  | .«出库» x n => .«出库» x n

/-- 框架：格子层操作；离线传入全部摆件的重建先后。 -/
inductive «操作» where
  | «建» (p : «摆件»)
  | «收» (u : «单位号»)
  | «蓝图» (ps : List «摆件»)
  | «离线» (ps : List «摆件»)
  | «原样» (o : «原样操作»)

/-- 框架：把全部布局事件依次交给现有作用；中间没有走步或外部操作。 -/
def «执行事件» (un : «未定») (todo : Endfield.«待写») (s : Endfield.«状态») (es : «历史») :
    Option Endfield.«状态» :=
  es.foldlM (fun s e => Endfield.«作用» un todo s (.«改布局» e)) s

/-- 框架：带格子的作用；建造、蓝图、拆除、离线失败均返回 none。
几何先后和无效口输入的行为都显式传入。变化期间不走步，所以待写按最终场地生成。 -/
def «作用» (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (s : «状态») (a : «操作») : Option «状态» := do
  let apply := fun (r : Option («场地» × «历史»)) => do
    let (ps, es) ← r
    let t ← «执行事件» un («场地».«待写» ps o bad) s.«模型» es
    return ⟨ps, t⟩
  match a with
  | .«建» p => apply (s.«场地».«建» o p)
  | .«收» u => apply (s.«场地».«收» u)
  | .«蓝图» ps => apply (s.«场地».«放蓝图» o ps)
  | .«离线» ps =>
    let H ← s.«场地».«重建» o ps
    let t ← Endfield.«作用» un («场地».«待写» ps o bad) s.«模型» (.«离线» H)
    return ⟨ps, t⟩
  | .«原样» b =>
    let t ← Endfield.«作用» un (s.«场地».«待写» o bad) s.«模型» b.«模型操作»
    return ⟨s.«场地», t⟩

end Endfield.«格子»
