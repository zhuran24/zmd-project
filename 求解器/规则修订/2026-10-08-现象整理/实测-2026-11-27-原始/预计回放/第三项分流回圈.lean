import Endfield.«回放».«格子工具»

namespace Endfield.«第三项»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

-- 箱号 1、2，汇流器 3，分流器 4。所有格从上游往下游摆。
def setup (padded returnFirst : Bool) : Option Endfield.«格子».«状态» := do
  let base := [«摆» 1 23 13 (.«协议储存箱» .«下»), «摆» 2 23 (if padded then 22 else 21) (.«协议储存箱» .«下»),
    «摆» 3 24 18 (.«汇流器» .«下»), «摆» 4 24 20 (.«分流器» .«上»),
    «摆» 5 24 16 (.«传送带» .«上» .«下»), «摆» 6 24 17 (.«传送带» .«上» .«下»), «摆» 7 24 19 (.«传送带» .«上» .«下»)]
  let out := if padded then [«摆» 8 24 21 (.«传送带» .«上» .«下»)] else []
  let back := [«摆» 9 25 20 (.«传送带» .«左» .«上»), «摆» 10 25 19 (.«传送带» .«下» .«上»), «摆» 11 25 18 (.«传送带» .«下» .«左»)]
  let ps ← (base ++ (if returnFirst then back ++ out else out ++ back)).mapM id
  let s ← «布置» ps
  «做» s (.«原样» (.«放货» 1 .«钢块» 300))

-- 逐步读两个箱子和分流器最近送往哪格。8 为进箱带，9 为回带首格。
def replay (padded returnFirst : Bool) : Option String := do
  let s ← setup padded returnFirst
  let h := s.«模型».«历史»
  let l := s.«模型».«布局»
  let levels := l.«各组».map (h.«级别» h.length)
  let step := «走» «取一种» (s.«场地».«待写» «端口先后» «无效口») h.«立表» 1
  let mut m := s.«模型»
  let initial := (List.range 6).map fun i => m.«件数» ⟨1, .«格» i⟩ .«钢块»
  guard (initial == List.replicate 6 50)
  let mut sent := #[]
  let mut received := #[]
  let mut routes : Array (Nat × Nat) := #[]
  for i in [:400] do
    let next := step m
    let a := «箱里几件» m 1 .«钢块»
    let b := «箱里几件» m 2 .«钢块»
    if a != «箱里几件» next 1 .«钢块» then
      guard (a == «箱里几件» next 1 .«钢块» + 1)
      sent := sent.push (i+1)
    if b != «箱里几件» next 2 .«钢块» then
      guard (b+1 == «箱里几件» next 2 .«钢块»)
      received := received.push (i+1)
    if next.«分流器上次» 4 != m.«分流器上次» 4 then
      if let some c := next.«分流器上次» 4 then routes := routes.push (i+1, c.«止»)
    m := next
  return s!"初始六格 {initial}，各组级别 {repr levels}，分流器出口接通顺序 {(l.«通道表».filter (fun p => p.1.«起» == 4)).map (fun p => p.1.«止»)}\n出箱步号 {sent}\n进箱步号 {received}\n分流器出口变化（步号、去向）{repr (routes.extract 0 12)}\n400 步后两箱 {«箱里几件» m 1 .«钢块»}, {«箱里几件» m 2 .«钢块»}"

#eval IO.println ((replay false false).getD "贴脸布置或读数失败")
#eval IO.println ((replay true false).getD "先接进箱布置或读数失败")
#eval IO.println ((replay true true).getD "先接回带布置或读数失败")
end Endfield.«第三项»
