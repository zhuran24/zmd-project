import Endfield.«回放».«格子工具»
open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

def «底» : Option (List «摆件») :=
  ([«摆» 1 29 13 (.«协议储存箱» .«下»)]
   ++ ([16, 17, 18].map fun j => «摆» (100 + j) 30 j (.«传送带» .«上» .«下»))
   ++ [«摆» 30 30 17 (.«物品准入口» .«下»), «摆» 50 29 19 (.«制造» .«粉碎机» .«下»)]
   ++ [«摆» 122 30 22 (.«传送带» .«上» .«下»), «摆» 99 33 21 .«供电桩»,
       «摆» 60 29 23 (.«协议储存箱» .«下»)]).mapM id

def «看» (w n : Nat) : Option (List Nat) := do
  let s ← «底».bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 30 (some .«荞花») none (some 0)))
  let s ← «做» s (.«原样» (.«设储存箱模式» 60 false))
  let s ← «做» s (.«原样» (.«放货» 1 .«荞花» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let m := «走» «取一种» todo T w s.«模型»
  let s ← «做» { s with «模型» := m } (.«原样» (.«设准入口» 30 (some .«荞花») none (some 1)))
  let r := ((List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 60 .«荞花粉末»])) (s.«模型», [])).2
  return (r.zipIdx.filter fun p => (p.2 + 1) % 4 == 0).map (·.1)

#eval do
  for k in List.range 10 do
    let w := 40 + 4 * k
    match «看» w 400 with
    | some l => IO.println s!"w={w}: {String.join (((l.drop 40).take 30).map toString)}"
    | none => IO.println s!"w={w}: 搭不出来"
