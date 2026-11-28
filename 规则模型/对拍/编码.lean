import Lean.Data.Json
import Endfield.«回放».«格子工具»

open Lean Endfield
namespace Oracle

abbrev Result := Except String

-- 无参数的构造子按原名写成字符串。
deriving instance ToJson, FromJson for «物品», «制造单位», «都没货时»
deriving instance ToJson, FromJson for «配方», «准入口状态», «储存箱状态»

def arr (xs : List Json) := Json.arr xs.toArray

def args (j : Json) : Result (List Json) := Array.toList <$> j.getArr?

instance : ToJson «通道» := ⟨fun c => toJson (c.«起», c.«止»)⟩
instance : FromJson «通道» := ⟨fun j => do
  let (a,b) ← fromJson? j
  return ⟨a,b⟩⟩

instance : ToJson «格名» where
  toJson
    | .«格» i => arr ["格", toJson i]
    | .«存货» i => arr ["存货", toJson i]
    | .«取货» => "取货"
    | .«缓存» => "缓存"

instance : FromJson «格名» where
  fromJson?
    | .str "取货" => return .«取货»
    | .str "缓存" => return .«缓存»
    | .arr #[.str "格", i] => return .«格» (← fromJson? i)
    | .arr #[.str "存货", i] => return .«存货» (← fromJson? i)
    | j => throw s!"未知格名 {j.compress}"

instance : ToJson «格位» := ⟨fun g => toJson (g.«单位», g.«名»)⟩
instance : FromJson «格位» := ⟨fun j => do
  let (u,n) ← fromJson? j
  return ⟨u,n⟩⟩
instance : ToJson «一堆» := ⟨fun p => toJson (p.«物», p.«件数»)⟩
instance : FromJson «一堆» := ⟨fun j => do
  let (x,n) ← fromJson? j
  return ⟨x,n⟩⟩

def kind : «单位种类» → Json
  | .«传送带» => "传送带" | .«分流器» => "分流器" | .«汇流器» => "汇流器"
  | .«物品准入口» => "物品准入口" | .«桥接器格» => "桥接器格"
  | .«协议储存箱» => "协议储存箱" | .«协议核心» => "协议核心" | .«仓库取货口» => "仓库取货口"
  | .«制造» k => toJson k

def readKind : Json → Result «单位种类»
  | .str "传送带" => return .«传送带» | .str "分流器" => return .«分流器»
  | .str "汇流器" => return .«汇流器» | .str "物品准入口" => return .«物品准入口»
  | .str "桥接器格" => return .«桥接器格» | .str "协议储存箱" => return .«协议储存箱»
  | .str "协议核心" => return .«协议核心» | .str "仓库取货口" => return .«仓库取货口»
  | j => .«制造» <$> fromJson? j

instance : ToJson «事件» where
  toJson
    | .«建成» u k => arr ["建成", toJson u, kind k]
    | .«接通» c => arr ["接通", toJson c]
    | .«重接» c => arr ["重接", toJson c]
    | .«拆除» u => arr ["拆除", toJson u]

instance : FromJson «事件» where
  fromJson?
    | .arr #[.str "建成", u, k] => return .«建成» (← fromJson? u) (← readKind k)
    | .arr #[.str "接通", c] => return .«接通» (← fromJson? c)
    | .arr #[.str "重接", c] => return .«重接» (← fromJson? c)
    | .arr #[.str "拆除", u] => return .«拆除» (← fromJson? u)
    | j => throw s!"未知事件或参数个数有误 {j.compress}"

inductive Action where
  | walk (n : Nat)
  | apply (o : «操作»)

def actionJson : Action → Json
  | .walk n => arr ["走", toJson n]
  | .apply .«走一步» => arr ["走", toJson 1]
  | .apply (.«设准入口» u x a b) => arr ["设准入口", toJson u, toJson x, toJson a, toJson b]
  | .apply (.«重置计数» u) => arr ["重置计数", toJson u]
  | .apply (.«设储存箱模式» u b) => arr ["设储存箱模式", toJson u, toJson b]
  | .apply (.«设取货指向» u i x) => arr ["设取货指向", toJson u, toJson i, toJson x]
  | .apply (.«拨开关» us b) => arr ["拨开关", toJson us, toJson b]
  | .apply (.«放货» u x n) => arr ["放货", toJson u, toJson x, toJson n]
  | .apply (.«收货» g) => arr ["收货", toJson g]
  | .apply (.«入库» x n) => arr ["入库", toJson x, toJson n]
  | .apply (.«出库» x n) => arr ["出库", toJson x, toJson n]
  | .apply (.«离线» h) => arr ["离线", toJson h]
  | .apply (.«改布局» e) => arr ["改布局", toJson e]

def readAction (j : Json) : Result Action := do
  match ← args j with
  | [.str "走", n] => return .walk (← fromJson? n)
  | [.str "设准入口", u, x, a, b] => return .apply (.«设准入口» (← fromJson? u) (← fromJson? x) (← fromJson? a) (← fromJson? b))
  | [.str "重置计数", u] => return .apply (.«重置计数» (← fromJson? u))
  | [.str "设储存箱模式", u, b] => return .apply (.«设储存箱模式» (← fromJson? u) (← fromJson? b))
  | [.str "设取货指向", u, i, x] => return .apply (.«设取货指向» (← fromJson? u) (← fromJson? i) (← fromJson? x))
  | [.str "拨开关", us, b] => return .apply (.«拨开关» (← fromJson? us) (← fromJson? b))
  | [.str "放货", u, x, n] => return .apply (.«放货» (← fromJson? u) (← fromJson? x) (← fromJson? n))
  | [.str "收货", g] => return .apply (.«收货» (← fromJson? g))
  | [.str "入库", x, n] => return .apply (.«入库» (← fromJson? x) (← fromJson? n))
  | [.str "出库", x, n] => return .apply (.«出库» (← fromJson? x) (← fromJson? n))
  | [.str "离线", h] => return .apply (.«离线» (← fromJson? h))
  | _ => throw s!"段内不支持的操作或参数个数有误 {j.compress}"

-- 标准库的对象解析会覆盖重名成员。这里共用它的标量解析，并在插入对象前检查唯一性。
namespace StrictJson
open Std.Internal.Parsec Std.Internal.Parsec.String

def value : Nat → Parser Json
  | 0 => fail "JSON 嵌套深度超过输入长度"
  | fuel + 1 => do
    match ← peek! with
    | '{' =>
      skip
      ws
      let mut members : Std.TreeMap.Raw String Json := {}
      unless (← peek!) == '}' do
        repeat
          let _ ← pchar '"'
          let k ← Json.Parser.str
          if members.contains k then fail s!"重复的 JSON 键 {k}"
          ws
          let _ ← pchar ':'
          ws
          members := members.insert k (← value fuel)
          if (← peek!) == '}' then break
          let _ ← pchar ','
          ws
      skip
      ws
      return .obj members
    | '[' =>
      skip
      ws
      let mut xs := #[]
      unless (← peek!) == ']' do
        repeat
          xs := xs.push (← value fuel)
          if (← peek!) == ']' then break
          let _ ← pchar ','
          ws
      skip
      ws
      return .arr xs
    | _ => Json.Parser.anyCore

def parse (s : String) : Result Json :=
  Parser.run (ws *> value (s.utf8ByteSize + 1) <* eof) s

end StrictJson
end Oracle
