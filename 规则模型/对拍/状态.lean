import «对拍».«编码»
import Endfield.«物品格的规矩»

open Lean Endfield Endfield.«回放»
namespace Oracle

abbrev Table (α β : Type) := List (α × β)

structure Snapshot where
  «货» : Table «格位» (List «一堆») := []
  «已停» : Table «格位» Nat := []
  «来处» : Table «格位» (Option «格位») := []
  «分流器上次» : Table Nat (Option «通道») := []
  «进货上次» : Table Nat Nat := []
  «出货已移动» : Table Nat (List «通道») := []
  «制造中» : Table Nat (Option («配方» × Nat)) := []
  «准入口» : Table Nat «准入口状态» := []
  «储存箱» : Table Nat «储存箱状态» := []
  «开关» : Table Nat Bool := []
  «取货指向» : Table (Nat × Nat) (Option «物品») := []
  «仓库» : Table «物品» Nat := []
deriving ToJson, FromJson, DecidableEq

def portCount : «单位种类» → Nat
  | .«协议核心» => 6 | .«仓库取货口» => 1 | _ => 0

structure Domain where
  layout : «布局»
  units : List Nat
  cells : List «格位»
  gates : List Nat
  boxes : List Nat
  splitters : List Nat
  machines : List Nat
  poweredKinds : List Nat
  nonTransport : List Nat
  ports : List (Nat × Nat)
  outlets : List «通道»

def domain (L : «布局») : Domain :=
  let us := L.«单位表».mergeSort (fun a b => a.1 ≤ b.1)
  let select (f : «单位种类» → Bool) := (us.filter (fun p => f p.2)).map Prod.fst
  let tagged (k : «单位种类») := select (· == k)
  let machine : «单位种类» → Bool := fun | .«制造» _ => true | _ => false
  let ports := us.flatMap fun (u,k) => (List.range (portCount k)).map (u, ·)
  let outlets := (L.«通道表».map Prod.fst).filter fun c =>
    ((L.«种类» c.«起»).map portCount).getD 0 > 0
  ⟨L, us.map Prod.fst, us.flatMap (fun (u,k) => k.«物品格».map (⟨u, ·⟩)),
   tagged .«物品准入口», tagged .«协议储存箱», tagged .«分流器», select machine,
   select (fun k => machine k || k == .«协议储存箱»), select (!·.«是运输单位»), ports,
   outlets.mergeSort (fun a b => a.«起» < b.«起» || (a.«起» == b.«起» && a.«止» ≤ b.«止»))⟩

def sparse [BEq β] (keys : List α) (val : α → β) (d : β) : Table α β :=
  keys.filterMap fun k => let v := val k; if v == d then none else some (k,v)

private def inputIndex (d : Domain) (u n : Nat) : Nat :=
  if n == 0 then 0 else n % max 1 (d.layout.«进货表» u).length

private def loadedTransportCells (d : Domain) (cargo : Table «格位» (List «一堆»)) : List «格位» :=
  cargo.filterMap fun (g, stacks) =>
    if !stacks.isEmpty && d.layout.«是运输单位» g.«单位» then some g else none

-- cap=false 读取同一有限域上的原数，供核对原始计数与规范值之用。
def snapshot (d : Domain) (s : «状态») (cap := true) : Snapshot :=
  let cargo := sparse d.cells s.«货» []
  let loaded := loadedTransportCells d cargo
  { «货» := cargo
    «已停» := sparse loaded (fun g => if cap then min 8 (s.«已停» g) else s.«已停» g) 0
    «来处» := sparse loaded s.«来处» none
    «分流器上次» := sparse d.splitters s.«分流器上次» none
    «进货上次» := sparse d.units (fun u => if cap then inputIndex d u (s.«进货上次» u) else s.«进货上次» u) 0
    «出货已移动» := sparse d.nonTransport s.«出货已移动» []
    «制造中» := sparse d.machines s.«制造中» none
    «准入口» := sparse d.gates (fun u => let g := s.«准入口» u; if cap then {g with «拍» := g.«拍» % 4} else g) {}
    «储存箱» := sparse d.boxes s.«储存箱» {}
    «开关» := sparse d.poweredKinds s.«开关» true
    «取货指向» := sparse d.ports (fun (u,i) => s.«取货指向» u i) none
    «仓库» := sparse «各种物品» s.«仓库» 0 }

def Snapshot.restore (t : Snapshot) (h : «历史») : «状态» where
  «历史» := h
  «货» := «查表» t.«货» []
  «已停» := «查表» t.«已停» 0
  «来处» := «查表» t.«来处» none
  «分流器上次» := «查表» t.«分流器上次» none
  «进货上次» := «查表» t.«进货上次» 0
  «出货已移动» := «查表» t.«出货已移动» []
  «制造中» := «查表» t.«制造中» none
  «准入口» := «查表» t.«准入口» {}
  «储存箱» := «查表» t.«储存箱» {}
  «开关» := «查表» t.«开关» true
  «取货指向» := fun u i => «查表» t.«取货指向» none (u,i)
  «仓库» := «查表» t.«仓库» 0

def Snapshot.json (t : Snapshot) : Json :=
  match toJson t with
  | .obj fields => Json.mkObj (fields.toList.filter (·.2 != Json.arr #[]))
  | j => j

def checkKeys (j : Json) (allowed : List String) : Result Unit := do
  for (key, _) in (← j.getObj?).toList do
    unless allowed.contains key do throw s!"未知字段 {key}"

def checkRows [BEq α] (label : String) (keys : List α) (rows : Table α β) : Result Unit := do
  unless keys.filter (fun k => rows.any (·.1 == k)) == rows.map Prod.fst do
    throw s!"{label} 有不存在、重复或未按规定先后排列的键"

private def fill (defaults input : Json) : Result Json := do
  let fields ← input.getObj?
  let schema ← defaults.getObj?
  checkKeys input (schema.toList.map Prod.fst)
  return Json.mkObj (schema.toList.map fun (k,v) => (k, (fields.get? k).getD v))

private def fillRows (rows defaults : Json) : Result Json := do
  let xs ← rows.getArr?
  return .arr (← xs.mapM fun entry => do
    let (k, v) ← fromJson? (α := Json × Json) entry
    return arr [k, ← fill defaults v])

def readSnapshot (j : Json) (d : Domain) (h : «历史») : Result Snapshot := do
  let base ← fill (toJson ({} : Snapshot)) j
  let full := Json.mkObj (← (← base.getObj?).toList.mapM fun (k,v) => do
    match k with
    | "准入口" => return (k, ← fillRows v (toJson ({} : «准入口状态»)))
    | "储存箱" => return (k, ← fillRows v (toJson ({} : «储存箱状态»)))
    | _ => return (k,v))
  let t : Snapshot ← fromJson? full
  unless toJson t == full do throw "状态含多余的字段或取值类型有误"
  checkRows "货" d.cells t.«货»
  checkRows "已停" d.cells t.«已停»
  checkRows "来处" d.cells t.«来处»
  checkRows "分流器上次" d.splitters t.«分流器上次»
  checkRows "进货上次" d.units t.«进货上次»
  checkRows "出货已移动" d.nonTransport t.«出货已移动»
  checkRows "制造中" d.machines t.«制造中»
  checkRows "准入口" d.gates t.«准入口»
  checkRows "储存箱" d.boxes t.«储存箱»
  checkRows "开关" d.poweredKinds t.«开关»
  checkRows "取货指向" d.ports t.«取货指向»
  checkRows "仓库" «各种物品» t.«仓库»
  unless t.«进货上次».all (fun (u,n) => inputIndex d u n == n) do throw "进货上次超出现布局的下标范围"
  let loaded := loadedTransportCells d t.«货»
  unless t.«已停».all (fun (g,n) => n == 0 || (loaded.contains g && n ≤ 8)) do
    throw "非零已停须在有货的运输格上且不超过 8"
  unless t.«来处».all (fun (g,src) => src.isNone || loaded.contains g) do
    throw "非空来处须在有货的运输格上"
  unless t.«准入口».all (·.2.«拍» < 4) do throw "准入口拍超过 3"
  let s := t.restore h
  unless s.«各格合规矩» d.layout && t.«仓库».all (·.2 ≤ 80000) do throw "货物、制造中配方或仓库数量不合规矩"
  for (u, g) in t.«准入口» do
    unless («操作».«设准入口» u g.«放行» g.«累计上限» g.«每5tick上限»).«做得了» s do throw "段首的准入口设定不合规矩"
  return t

end Oracle
