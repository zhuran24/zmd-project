import «对拍».«场地»

open Lean Endfield Endfield.«格子» Oracle.Grid
namespace Oracle.GridTrace

private def record (ps : «场地») (o : «接通先后») (reference : Json) (result : α) : α :=
  let pieces := ps.map Piece.fromModel
  let ranks := (coreKeys pieces).map fun (d, n) => ((d,n), o.«协议核心» d n)
  let row := arr [toJson (Example.mk pieces ranks), reference]
  dbgTrace ("@field " ++ row.compress) fun _ => result

-- 在原回放的操作返回后读场地和里层历史。出现拆除时只导出当前摆件表。
def observe (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (s : Endfield.«格子».«状态») (op : Endfield.«格子».«操作») : Option Endfield.«格子».«状态» :=
  let result := Endfield.«格子».«作用» un o bad s op
  match op, result with
  | .«原样» _, _ => result
  | _, some t =>
    let h := t.«模型».«历史»
    let removed := h.any fun e => match e with | .«拆除» _ => true | _ => false
    record t.«场地» o (if removed then .null else toJson h) result
  | .«建» p, none => record (s.«场地» ++ [p]) o "拒绝" none
  | _, none => none

def power (ps : «场地») (u : Nat) : Bool :=
  record ps «回放».«格子».«端口先后» .null (ps.«有电» u)

end Oracle.GridTrace
