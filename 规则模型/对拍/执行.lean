import «对拍».«状态»

open Lean Endfield Endfield.«回放»
namespace Oracle

inductive Counter where
  | «保留» | «清空»
deriving ToJson, FromJson, DecidableEq

structure Policies where
  «改设定后的计数» : Counter × Counter
  «离线后的计数» : Counter × Counter
  «传输排在几组之后» : Table Nat Nat
  «输入判定都没货时» : «都没货时»
deriving ToJson, FromJson

def counts (p : Counter × Counter) (g : «准入口状态») : Nat × List Nat :=
  (if p.1 == .«保留» then g.«累计已收» else 0, if p.2 == .«保留» then g.«名额» else [])

def Policies.model (p : Policies) : «未定» where
  «改设定后的计数» := fun g _ _ _ => counts p.«改设定后的计数» g
  «离线后的计数» := counts p.«离线后的计数»
  «传输排在几组之后» := «查表» p.«传输排在几组之后» 0
  «输入判定都没货时» := p.«输入判定都没货时»

structure Context where
  «历史» : «历史»
  «供电» : List Nat
  «端口» : Table «通道» Nat
  «未定» : Policies
deriving ToJson, FromJson

def Context.hooks (c : Context) : «待写» where
  «有电» := fun _ u => c.«供电».contains u
  «口» := fun _ => «查表» c.«端口» 6
  «放进单位» := Endfield.«格子».«放进单位»

def Context.check (c : Context) (d : Domain) : Result Unit := do
  unless c.«历史».«合规» do throw "段首历史不合规"
  unless d.units.filter c.«供电».contains == c.«供电» do throw "供电表含缺失、重复或乱序的单位号"
  unless c.«未定».«传输排在几组之后».map Prod.fst == d.boxes do throw "每个箱须按单位号给出传输位置"
  unless c.«端口».map Prod.fst == d.outlets do throw "端口表须按起止号列全仓库取货通道"
  for (ch,i) in c.«端口» do
    unless d.ports.contains (ch.«起», i) do throw "端口编号越界"

def key (j : Json) (k : String) : Result Json := j.getObjVal? k

def readContext (j : Json) : Result Context := do
  let c : Context ← fromJson? j
  for (k,v) in (← (toJson c).getObj?).toList do
    unless (← key j k) == v do throw s!"段首字段 {k} 不合格式"
  return c

def ioResult (where_ : String) (r : Result α) : IO α := do
  match r with
  | .ok x => return x
  | .error e => throw (IO.userError (where_ ++ " " ++ e))

abbrev StepCheck := Domain → «判定表» → «未定» → «待写» → «状态» → «状态» → IO Unit

def runSegment (j : Json) (index : Nat) (writeRow : Json → IO Unit)
    (check : Option StepCheck := none) : IO Unit := do
  let label := s!"第 {index} 段"
  let (c,d,t,ops,expected) ← ioResult label do
    checkKeys j ["历史", "供电", "端口", "未定", "状态", "操作", "期望", "备注"]
    if let .ok v := j.getObjVal? "备注" then let _ ← v.getStr?
    let c ← readContext j
    let d := domain (c.«历史».«布局于» c.«历史».length)
    c.check d
    let t ← readSnapshot (← key j "状态") d c.«历史»
    let ops ← (← key j "操作").getArr?
    let expected ← (j.getObjVal? "期望").toOption.mapM Json.getArr?
    return (c,d,t,ops,expected)
  let un := c.«未定».model
  let hooks := c.hooks
  let mut s := t.restore c.«历史»
  let mut tab := c.«历史».«立表»
  let mut line := 0
  let emit := fun (i : Nat) (s : «状态») => do
    let row := (snapshot d s).json
    if let some rows := expected then
      unless rows[i]? == some row do throw (IO.userError s!"{label} 第 {i+1} 个输出与期望不同")
    writeRow row
  for (jop, i) in ops.toList.zipIdx do
    let pos := s!"{label} 第 {i+1} 项操作"
    match ← ioResult pos (readAction jop) with
    | .walk n =>
      for _ in [:n] do
        let next := «压平» tab.«现布局» («一步于» tab un hooks s)
        if let some audit := check then audit d tab un hooks s next
        s := next
        emit line s
        line := line + 1
    | .apply o =>
      let some next := «作用» un hooks s o | throw (IO.userError s!"{pos} 做不了 {jop.compress}")
      if check.isSome then
        let restored := (snapshot d s).restore s.«历史»
        let some other := «作用» un hooks restored o | throw (IO.userError s!"{pos} 规范化后操作失败")
        unless snapshot d other == snapshot d next && toJson other.«历史» == toJson next.«历史» do
          throw (IO.userError s!"{pos} 规范化后操作结果不同")
      s := «压平» d.layout next
      if let .«离线» _ := o then tab := s.«历史».«立表»
      emit line s
      line := line + 1
  if let some rows := expected then
    unless rows.size == line do throw (IO.userError s!"{label} 期望行数应为 {line}")

def replay (path : System.FilePath) (writeRow : Json → IO Unit)
    (check : Option StepCheck := none) : IO Unit := do
  let j ← ioResult path.toString (StrictJson.parse (← IO.FS.readFile path))
  let segs ← ioResult path.toString do
    checkKeys j ["版本", "段"]
    unless (← (← key j "版本").getNat?) == 1 do throw "只支持版本 1"
    (← key j "段").getArr?
  for (seg,i) in segs.toList.zipIdx do runSegment seg (i+1) writeRow check

def run (path : System.FilePath) : IO Unit := do
  let out ← IO.getStdout
  replay path (fun row => out.putStrLn row.compress)

end Oracle
