import «对拍».«执行»

/- 这些观察函数只在导出时调用。传回给回放的值来自原模型。
   编译器的 dbgTrace 把观察结果送给收集程序；核对失败使用独立的错误标记。 -/
open Lean Endfield Endfield.«回放»
namespace Oracle.Trace

private def record (j : Json) (value : α) : α :=
  dbgTrace ("@oracle " ++ j.compress) fun _ => value

private def header (d : Domain) (s : «状态») (un : «未定») (todo : «待写») : Json :=
  let keep := (Counter.«保留», Counter.«保留»)
  let policies : Policies := ⟨keep, keep, d.boxes.map (fun u => (u, un.«传输排在几组之后» u)), un.«输入判定都没货时»⟩
  toJson (Context.mk s.«历史» (d.units.filter (todo.«有电» s))
    (d.outlets.map fun c => (c, todo.«口» s c)) policies)

private def checkpoint (s : «状态») (un : «未定») (todo : «待写») : «状态» :=
  let d := domain s.«布局»
  record (arr [header d s un todo, (snapshot d s).json, "布局"]) s

private def observe (s t : «状态») (un : «未定») (todo : «待写») (op : «操作») : «状态» :=
  let d := domain s.«布局»
  let before := snapshot d s
  let after := snapshot d t
  match «作用» un todo (before.restore s.«历史») op with
  | some other =>
    if snapshot d other == after && toJson other.«历史» == toJson t.«历史» then
      record (arr [header d s un todo, before.json, actionJson (.apply op), after.json]) t
    else record (.str "规范化后操作结果不同") t
  | none => record (.str "规范化后操作失败") t

def step (tab : «判定表») (un : «未定») (todo : «待写») (s : «状态») : «状态» :=
  let t := «一步于» tab un todo s
  let d := domain tab.«现布局»
  let before := snapshot d s
  let after := snapshot d t
  let other := «一步于» tab un todo (before.restore s.«历史»)
  if snapshot d other == after && toJson other.«历史» == toJson t.«历史» then
    record (arr [header d s un todo, before.json, actionJson (.walk 1), after.json]) t
  else record (Json.str "规范化走一步不相等") t

def applyOp (un : «未定») (todo : «待写») (s : «状态») (op : «操作») : Option «状态» :=
  match op with
  | .«走一步» => some (step s.«历史».«立表» un todo s)
  | .«改布局» _ => («作用» un todo s op).map fun t => checkpoint t un todo
  | _ => («作用» un todo s op).map (fun t => observe s t un todo op)

def gridOp (un : «未定») (order : «格子».«接通先后») (bad : «通道» → Nat)
    (g : «格子».«状态») (op : «格子».«操作») : Option «格子».«状态» := do
  let todo := g.«场地».«待写» order bad
  match op with
  | .«原样» a => return {g with «模型» := ← applyOp un todo g.«模型» a.«模型操作»}
  | .«离线» _ =>
    let next ← «格子».«作用» un order bad g op
    return {next with «模型» := observe g.«模型» next.«模型» un todo (.«离线» next.«模型».«历史»)}
  | _ =>
    let t ← «格子».«作用» un order bad g op
    return {t with «模型» := checkpoint t.«模型» un (t.«场地».«待写» order bad)}

-- 纯供电读数在原场地摆好后取零步段。供电桩没有里层单位。
def power (ps : «格子».«场地») (u : Nat) : Bool :=
  let result := ps.«有电» u
  let order := «回放».«格子».«端口先后»
  match ps.foldlM (fun g p => «格子».«作用» «取一种» order «回放».«格子».«无效口» g (.«建» p)) «格子».«状态».«空» with
  | none => record (.str "供电场地重建失败") result
  | some g =>
    let s := g.«模型»
    let d := domain s.«布局»
    record (arr [header d s «取一种» (ps.«待写» order «回放».«格子».«无效口»), (snapshot d s).json]) result

end Oracle.Trace
