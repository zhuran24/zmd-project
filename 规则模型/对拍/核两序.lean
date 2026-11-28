import «对拍».«执行»

open Lean Endfield Oracle

private structure Totals where
  ticks : Nat := 0
  rawDiff : Nat := 0
  stopped : Nat := 0
  phase : Nat := 0
  index : Nat := 0

private def compareStep (stats : IO.Ref Totals) (d : Domain) (tab : «判定表»)
    (un : «未定») (todo : «待写») (s next : «状态») : IO Unit := do
  let n := (snapshot d s).restore s.«历史»
  let stepped := «一步于» tab un todo n
  let right := snapshot d next
  unless snapshot d stepped == right && toJson stepped.«历史» == toJson next.«历史» do
    throw (IO.userError "两边逐步规范化以后有差异")
  let raw := snapshot d stepped false
  let a := raw.«已停» != right.«已停»
  let b := raw.«准入口» != right.«准入口»
  let c := raw.«进货上次» != right.«进货上次»
  unless {raw with «已停» := right.«已停», «准入口» := right.«准入口», «进货上次» := right.«进货上次»} == right do throw (IO.userError "另有字段不同")
  stats.modify fun r => ⟨r.ticks+1, r.rawDiff+(a || b || c).toNat, r.stopped+a.toNat, r.phase+b.toNat, r.index+c.toNat⟩

def main (paths : List String) : IO Unit := do
  if paths.isEmpty then throw (IO.userError "需要黄金文件名")
  let totals ← IO.mkRef ({} : Totals)
  for path in paths do replay path (fun _ => pure ()) (some (compareStep totals))
  let r ← totals.get
  IO.println s!"{r.ticks} 步，双方规范化后 0 处不同。左侧保留原数时 {r.rawDiff} 步不同，其中已停 {r.stopped} 步，拍 {r.phase} 步，进货上次 {r.index} 步（可同时发生）。"
