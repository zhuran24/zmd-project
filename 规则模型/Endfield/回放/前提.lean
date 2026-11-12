import Endfield.«回放».«绕回卡两件»
import Endfield.«回放».«两个中转箱»
import Endfield.«回放».«存货箱和中转箱»
import Endfield.«回放».«配件机和带子»
import Endfield.«回放».«换配方»
import Endfield.«回放».«桥接器»
import Endfield.«回放».«下游放置翻转»
import Endfield.«回放».«一步的尺子»
import Endfield.«回放».«原料格堆满»
import Endfield.«回放».«分流器最后放»
import Endfield.«回放».«终点的时刻»
import Endfield.«命题»

/-!
# 回放里的布局满足定理的前提

`命题.lean` 里的定理拿合规、端口数合、走得通当前提（定义在 `通道与移动.lean`、`合法基地.lean`）。
这里拿别的回放摆过的 22 个布局验一遍：都合规、每一刻端口数都合；走得通的 20 个，
走不通的两个是带着断头线路的桥接器布局（`回放/桥接器.lean`），它们上面有的组没有级别。

最后两段把「走一步的结果不看规则没定的先后」（`命题.一步不看没定的先后`，已证）在两个布局上算出来看：
把列出各组的先后、带内通道的先后、汇流器那张表的先后、制造判定的先后都倒过来，连走 40 步，每一步都和原来的一样。
-/

namespace Endfield.«回放».«前提»

open Endfield.«命题»

/-- 回放：一个布局合不合规、端口数合不合、走不走得通、是不是每个组都有级别；剧本做不下去是 `none`。 -/
def «验» (o : Option «状态») : Option (Bool × Bool × Bool × Bool) :=
  o.map fun s =>
    let H := s.«历史»
    let L := s.«布局»
    (H.«合规», H.«端口数合», L.«走得通», L.«各组».all fun g => (H.«级别» H.length g).isSome)

/-- 回放：照剧本演出来的布局。 -/
def «演出» (script : List «一幕») : Option «状态» := «演» «状态».«空» script

-- 走得通的 20 个：四样都成立。
#guard [«演出» («绕回卡两件».«布置» true true), «演出» («绕回卡两件».«布置» true false),
        «演出» («绕回卡两件».«布置» false true),
        «演出» («两个中转箱».«布置» true false), «演出» («两个中转箱».«实测的布置» false),
        «演出» («存货箱和中转箱».«布置» true false),
        «演出» («配件机和带子».«布置» true), «演出» («换配方».«三路» true),
        «演出» («下游放置翻转».«布置» true),
        «演出» («一步的尺子».«布置» ++ «一步的尺子».«摆法一»),
        «演出» («一步的尺子».«布置» ++ «一步的尺子».«摆法二»),
        «原料格堆满».«双原料», «分流器最后放».«起点» true,
        «演出» «终点的时刻».«组一», «演出» «终点的时刻».«组三», «演出» «终点的时刻».«组五»,
        «演出» «终点的时刻».«组七», «演出» «终点的时刻».«组甲», «演出» «终点的时刻».«组丙»,
        «演出» «终点的时刻».«组丁»].all fun o => «验» o == some (true, true, true, true)

-- 带着断头线路的两个：合规、端口数合，走不通，有的组没有级别。
#guard [«演出» «桥接器».«蛇形布置», «演出» «桥接器».«七格双线»].all fun o =>
  «验» o == some (true, true, false, false)

/-- 回放：状态在现有单位上的全部内容，拿来比两个状态一不一样。 -/
def «摘要» (L : «布局») (s : «状态») :=
  let us := L.«单位表».map (·.1)
  let cells : List «格位» := L.«单位表».flatMap fun p => p.2.«物品格».map fun n => ⟨p.1, n⟩
  (cells.map fun g => (s.«货» g, s.«已停» g, s.«来处» g),
   us.map fun u => (s.«分流器上次» u, s.«进货上次» u, s.«出货已移动» u, s.«制造中» u, s.«准入口» u,
     s.«储存箱» u, s.«开关» u),
   «各种物品».map fun x => s.«仓库» x)

/-- 回放：从 s 起走 n 步，每一步都把各处的先后倒过来再走一遍，和原来的比；返回对不上的是第几步。 -/
def «换排法对不上的步» (n : Nat) (s : «状态») : List Nat :=
  let H := s.«历史»
  let T := H.«立表»
  let L := T.«现布局»
  let us := T.«非运输单位».map (·.1)
  let T' := H.«立表照» L.«各组».reverse
  ((List.range n).foldl (fun (acc : «状态» × List Nat) i =>
    let a := «一步于» T «取一种» «都有电» acc.1
    let b := «一步照» T' T.«带内».reverse T.«汇流器».reverse us.reverse us.reverse «取一种» «都有电» acc.1
    («压平» L a, if «摘要» L a == «摘要» L b then acc.2 else acc.2 ++ [i])) (s, [])).2

/-- 回放：给没有进口、有出口的协议储存箱装满源矿，好让线上有东西走。 -/
def «装上货» (s : «状态») : «状态» :=
  let L := s.«布局»
  L.«单位表».foldl (fun s p =>
    if p.2 == .«协议储存箱» && (L.«进» p.1).isEmpty && !(L.«出» p.1).isEmpty then
      (List.range 6).foldl (fun s i => «装货» s p.1 (.«格» i) .«源矿» 50) s
    else s) s

-- 绕回的那个布局（分流器、汇流器、桥接器、带子都有）和两个中转箱：40 步里每一步都一样。
#guard ((«演出» («绕回卡两件».«布置» true true)).map fun s => «换排法对不上的步» 40 («装上货» s)) == some []
#guard ((«演出» («两个中转箱».«布置» true false)).map fun s => «换排法对不上的步» 40 («装上货» s)) == some []

end Endfield.«回放».«前提»
