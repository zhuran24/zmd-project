import «对拍».«场地»
import Endfield.«回放».«格子»

open Lean Endfield Endfield.«格子» Oracle Oracle.Grid

-- ref 来自原回放的格子状态里的「模型.历史」，或原回放建造失败的标记。
private def check (name : String) (input ref : Json) : IO Unit := do
  let built ← ioResult name (readExample input >>= build)
  let some c := built | do
    unless ref == "拒绝" do throw (IO.userError s!"{name} 场地拒绝了回放布局")
    return
  unless toJson c.«历史» == ref do throw (IO.userError s!"{name} 历史与原回放不同")
  let boxes := (domain (c.«历史».«布局于» c.«历史».length)).boxes
  let keep := (Counter.«保留», Counter.«保留»)
  let un : Policies := ⟨keep, keep, boxes.map (·, 0), .«每步判两次»⟩
  let fields ← ioResult name (toJson c).getObj?
  let seg := Json.mkObj (fields.toList ++ [("未定", toJson un), ("状态", Json.mkObj []),
    ("操作", arr [arr ["走", toJson 3]])])
  let count ← IO.mkRef 0
  runSegment seg 1 (fun _ => count.modify (· + 1))
  unless (← count.get) == 3 do throw (IO.userError s!"{name} 未走完三步")

private def live (name : String) (state : Option Endfield.«格子».«状态») : IO Unit := do
  let some s := state | throw (IO.userError s!"{name} 回放未建成")
  let ps := s.«场地».map Piece.fromModel
  let ranks := (coreKeys ps).map fun (d,n) => ((d,n), «回放».«格子».«端口先后».«协议核心» d n)
  check name (toJson (Example.mk ps ranks)) (toJson s.«模型».«历史»)

open Endfield.«回放».«格子» in
def main (paths : List String) : IO Unit := do
  if paths.isEmpty then
    live "分流布局" («分流布局».bind «布置»)
    for n in [0,1,3] do
      for order in [if n == 1 then [8,9,7] else [9,8,7], [7,9,8]] do
        live "汇流布局" ((«汇流布局» n order).bind «布置»)
    for k in [«摆件种类».«协议储存箱» .«下», .«制造» .«精炼炉» .«下»] do
      live "同边进口布局" ((«同边进口布局» k).bind «布置»)
      live "同边出口布局" ((«同边出口布局» k 0).bind «布置»)
    live "同边出口布局转两次" ((«同边出口布局» (.«协议储存箱» .«下») 2).bind «布置»)
    IO.println "12 个现场回放历史相同，步进模式各走 3 步。"
  else
    for path in paths do
      let file ← IO.FS.Handle.mk path .read
      let mut n := 0
      repeat
        let line ← file.getLine
        if line.isEmpty then break
        n := n + 1
        let label := s!"{path} 第 {n} 行"
        let (input, ref_) ← ioResult label (StrictJson.parse line >>= fromJson? (α := Json × Json))
        check label input ref_
      IO.println s!"{n} 个回放读数相同。"
