import Endfield.«回放».«格子工具»

open Endfield.«格子» Endfield.«回放» Endfield.«回放».«格子»

/-- 一条直线往下：货源箱、带、限速的准入口 30、带、精炼炉、四格带、粉碎机、两格带、精炼炉、两格带、无线传输的箱子 60。
`k` 是前几台真放制造单位（其余换成三格带），3 就是三台都在。 -/
def «底» (k : Nat) : Option (List «摆件») :=
  let m (i j : Nat) («机» : Endfield.«制造单位») : List (Option «摆件») :=
    if i < k then [«摆» (50 + i) 29 j (.«制造» «机» .«下»)]
    else [0, 1, 2].map fun d => «摆» (200 + 10 * i + d) 30 (j + d) (.«传送带» .«上» .«下»)
  ([«摆» 1 29 13 (.«协议储存箱» .«下»)]
   ++ ([16, 17, 18].map fun j => «摆» (100 + j) 30 j (.«传送带» .«上» .«下»))
   ++ [«摆» 30 30 17 (.«物品准入口» .«下»)]
   ++ m 0 19 .«精炼炉»
   ++ ([22, 23, 24, 25].map fun j => «摆» (100 + j) 30 j (.«传送带» .«上» .«下»))
   ++ m 1 26 .«粉碎机»
   ++ ([29, 30].map fun j => «摆» (100 + j) 30 j (.«传送带» .«上» .«下»))
   ++ m 2 31 .«精炼炉»
   ++ ([34, 35].map fun j => «摆» (100 + j) 30 j (.«传送带» .«上» .«下»))
   ++ [«摆» 60 29 36 (.«协议储存箱» .«下»),
       «摆» 96 33 20 .«供电桩», «摆» 97 33 27 .«供电桩», «摆» 98 33 32 .«供电桩», «摆» 99 33 37 .«供电桩»]).mapM id

/-- 阀门先关着，传输箱第 0 步就在；走 w 步以后把阀门设成每 5 tick 1 件；再走 n 步。
给出整秒上看到的传输箱里的件数（从打开阀门以后算起，每秒一个）。 -/
def «看» (k w n : Nat) : Option (List Nat) := do
  let s ← («底» k).bind «布置»
  let s ← «做» s (.«原样» (.«设准入口» 30 (some .«蓝铁矿») none (some 0)))
  let s ← «做» s (.«原样» (.«设储存箱模式» 60 false))
  let s ← «做» s (.«原样» (.«放货» 1 .«蓝铁矿» 300))
  let s := { s with «模型» := «压平» s.«模型».«布局» s.«模型» }
  let T := s.«模型».«历史».«立表»
  let todo := s.«场地».«待写» «端口先后» «无效口»
  let m := «走» «取一种» todo T w s.«模型»
  let s ← «做» { s with «模型» := m } (.«原样» (.«设准入口» 30 (some .«蓝铁矿») none (some 1)))
  let r := ((List.range n).foldl (fun (acc : Endfield.«状态» × List Nat) _ =>
      let t := «走» «取一种» todo T 1 acc.1
      (t, acc.2 ++ [«箱里几件» t 60 .«蓝铁矿» + «箱里几件» t 60 .«蓝铁块» + «箱里几件» t 60 .«蓝铁粉末»])) (s.«模型», [])).2
  return (r.zipIdx.filter fun p => (p.2 + 1) % 4 == 0).map (·.1)

#eval do
  for k in [3, 2, 1] do
    IO.println s!"== 前 {k} 台是制造单位"
    for i in List.range 10 do
      let w := 40 + 4 * i
      match «看» k w 520 with
      | some l =>
        let tail := (l.drop 80).take 40
        let d := tail.foldl (· + ·) 0
        IO.println s!"  w={w}: 每轮看得到货 {d / 4} 秒  {String.join (tail.map toString)}"
      | none => IO.println s!"  w={w}: 搭不出来"
