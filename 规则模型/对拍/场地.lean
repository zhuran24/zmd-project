import «对拍».«执行»

open Lean Endfield Endfield.«格子»
namespace Oracle.Grid

deriving instance ToJson, FromJson for «朝向», «平行边»

private def shape : «摆件种类» → List Json
  | .«传送带» a b => ["传送带", toJson a, toJson b]
  | .«分流器» d => ["分流器", toJson d]
  | .«汇流器» d => ["汇流器", toJson d]
  | .«桥接器» d => ["桥接器", toJson d]
  | .«物品准入口» d => ["物品准入口", toJson d]
  | .«协议储存箱» d => ["协议储存箱", toJson d]
  | .«制造» k d => ["制造", toJson k, toJson d]
  | .«协议核心» a => ["协议核心", toJson a]
  | .«仓库取货口» d => ["仓库取货口", toJson d]
  | .«供电桩» => ["供电桩"]

instance : ToJson «摆件种类» := ⟨fun k => arr (shape k)⟩
instance : FromJson «摆件种类» where
  fromJson? j := do
    match ← args j with
    | [.str "传送带", a, b] => return .«传送带» (← fromJson? a) (← fromJson? b)
    | [.str "分流器", d] => return .«分流器» (← fromJson? d)
    | [.str "汇流器", d] => return .«汇流器» (← fromJson? d)
    | [.str "桥接器", d] => return .«桥接器» (← fromJson? d)
    | [.str "物品准入口", d] => return .«物品准入口» (← fromJson? d)
    | [.str "协议储存箱", d] => return .«协议储存箱» (← fromJson? d)
    | [.str "制造", k, d] => return .«制造» (← fromJson? k) (← fromJson? d)
    | [.str "协议核心", a] => return .«协议核心» (← fromJson? a)
    | [.str "仓库取货口", d] => return .«仓库取货口» (← fromJson? d)
    | [.str "供电桩"] => return .«供电桩»
    | _ => throw s!"未知摆件种类或参数个数有误 {j.compress}"

-- 先读全例的自然数坐标。能否成为场上的格属于建造结果。
structure Piece where
  «号» : Nat
  «种类» : «摆件种类»
  «位置» : Nat × Nat
deriving FromJson, ToJson

def Piece.fromModel (p : «摆件») : Piece :=
  ⟨p.«号», p.«种类», p.«位置».i.val, p.«位置».j.val⟩

abbrev Ranks := Table («朝向» × Nat) Nat

structure Example where
  «摆件» : List Piece
  «核心先后» : Ranks
deriving FromJson, ToJson

def coreKeys (ps : List Piece) : List («朝向» × Nat) :=
  match ps.findSome? (fun p => match p.«种类» with | .«协议核心» a => some a | _ => none) with
  | some a => «核心边格» a false ++ «核心边格» a true
  | none => []

def readExample (j : Json) : Result Example := do
  let x : Example ← fromJson? j
  unless toJson x == j do throw "多余的字段或字段写法有误"
  return x

private def readOrder (x : Example) : Result «接通先后» := do
  let keys := x.«核心先后».map Prod.fst
  let required := coreKeys x.«摆件»
  unless keys.length == required.length && required.all keys.contains do
    throw "核心先后须恰好覆盖全部端口位置，每个位置只出现一次"
  -- 模型需要全函数。核齐全部有效端口后，域外的值不会参与排序。
  return ⟨fun d n => «回放».«查表» x.«核心先后» n (d,n)⟩

structure Columns where
  «历史» : «历史»
  «供电» : List Nat
  «端口» : Table «通道» Nat
deriving ToJson

def columns (ps : «场地») (order : «接通先后») (h : «历史») : Result Columns := do
  let d := domain (h.«布局于» h.length)
  let ports ← d.outlets.mapM fun c => do
    let some n := ps.«口?» order c | throw s!"场地里找不到通道 {toJson c} 的唯一口号"
    return (c,n)
  return ⟨h, d.units.filter (ps.«有电» ·), ports⟩

def build (x : Example) : Result (Option Columns) := do
  let order ← readOrder x
  let mut field : «场地» := []
  let mut history : «历史» := []
  for p in x.«摆件» do
    let some c := «格».«坐标» p.«位置».1 p.«位置».2 | return none
    let some (next, events) := field.«建成» order ⟨p.«种类», c, p.«号»⟩ | return none
    field := next
    history := history ++ events
  return some (← columns field order history)

-- 在标准 JSON 解析器折合 -0、1e0 等写法前检查词形。键与字符串由同一 str 解析器跳过。
open Std.Internal.Parsec Std.Internal.Parsec.String in
def plainNumbers (s : String) : Result Unit := Parser.run (do
  repeat
    if ← isEof then break
    let c ← any
    if c == '"' then
      let _ ← Json.Parser.str
    else if c == '-' || c == '+' || c == '.' then
      fail "场地中的数字必须是普通十进制非负整数"
    else if c.isDigit then
      while !(← isEof) && (← peek!).isDigit do skip
      if !(← isEof) && ['e', 'E'].contains (← peek!) then
        fail "场地中的数字必须是普通十进制非负整数") s

def runExample (j : Json) (i : Nat) (writeRow : Json → IO Unit) : IO Unit := do
  let r ← ioResult s!"第 {i} 个场地" (readExample j >>= build)
  writeRow ((r.map toJson).getD (Json.str "拒绝"))

end Oracle.Grid
