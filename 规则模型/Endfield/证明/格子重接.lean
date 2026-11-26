import Endfield.«证明».«基础»

namespace Endfield.«证明»
open «格子»

/-- 工具：每条重接的通道都来自保留场地中某一格带子的实际接通端口。 -/
theorem «重接通道有来处» (F : «场地») (o : «接通先后») (p : «摆件») (c : «通道»)
    (hc : c ∈ F.«重接通道» o p) :
    (∃ q ∈ F, ∃ es, F.«接通事件» o q = some es ∧ «事件».«接通» c ∈ es) ∧
      c.«起» ∉ p.«单位».map Prod.fst ∧ c.«止» ∉ p.«单位».map Prod.fst := by
  obtain ⟨dir, _, hh⟩ := List.mem_filterMap.mp hc
  simp only [Option.bind_eq_bind, Option.bind_eq_some_iff] at hh
  obtain ⟨_, _, last, _, es, hes, d, hd, hh⟩ := hh
  split at hh
  · contradiction
  next hids =>
    cases hh
    refine ⟨?_, by simpa using hids⟩
    obtain ⟨e, he, h⟩ := List.mem_filterMap.mp (List.mem_of_head? hd)
    refine ⟨last.val, last.property, es, hes, ?_⟩
    cases e <;> simp_all <;> split at h <;> simp_all

/-- 工具：已有通道移到末尾，通道表的成员不变。 -/
theorem «重接保留成员» (cs : List «通道») (c : «通道») (hc : c ∈ cs) (d : «通道») :
    d ∈ cs.filter (· != c) ++ [c] ↔ d ∈ cs := by
  by_cases h : d = c <;> simp [h, hc]

/-- 工具：已有通道移到末尾后，满足任一条件的通道条数都不增加，即使原表里有重复项。 -/
theorem «重接不增条数» (cs : List «通道») (c : «通道») (hc : c ∈ cs) (f : «通道» → Bool) :
    ((cs.filter (· != c) ++ [c]).filter f).length ≤ (cs.filter f).length := by
  let keep := fun d => d != c
  have hs : [c].Sublist (cs.filter fun d => !keep d) := by simp [keep, hc]
  have sub := (List.Sublist.refl (cs.filter keep)).append hs
  rw [← ((List.filter_append_perm keep cs).filter f).length_eq]
  exact (sub.filter f).length_le

namespace «格子快照»

/-- 工具：只记录单位表和通道先后，省去接通时刻。 -/
abbrev Snapshot := List («单位号» × «单位种类») × List «通道»

/-- 工具：一个布局事件在快照上的作用。 -/
def addSnapshot (s : Snapshot) : «事件» → Snapshot
  | .«建成» u k => (s.1 ++ [(u,k)], s.2)
  | .«接通» c => (s.1, s.2 ++ [c])
  | .«重接» c => (s.1, s.2.filter (· != c) ++ [c])
  | .«拆除» u => (s.1.filter (fun p => p.1 != u), s.2.filter (fun c => c.«起» != u && c.«止» != u))

/-- 工具：照事件先后更新快照。 -/
def replay (s : Snapshot) (es : «历史») : Snapshot := es.foldl addSnapshot s

/-- 工具：两个摆件各有一个端口，正好形成所给通道。 -/
def Between (o : «接通先后») (p q : «摆件») (c : «通道») : Prop :=
  ∃ ps qs, p.«端口» o = some ps ∧ q.«端口» o = some qs ∧
    ∃ a ∈ ps, ∃ b ∈ qs, «格子».«形成通道» p q a b = some c

/-- 工具：通道来自场地里的一对端口。 -/
def Geometry (F : «场地») (o : «接通先后») (c : «通道») : Prop :=
  ∃ p ∈ F, ∃ q ∈ F, Between o p q c

/-- 工具：场地中每个摆件的端口都能列出。 -/
def PortsExist (F : «场地») (o : «接通先后») : Prop :=
  ∀ p ∈ F, ∃ ps, p.«端口» o = some ps

/-- 工具：快照里的单位和通道与场地的摆件和端口一致。 -/
def Synchronized (F : «场地») (o : «接通先后») (s : Snapshot) : Prop :=
  s.1 = F.flatMap «摆件».«单位» ∧ PortsExist F o ∧ ∀ c, c ∈ s.2 ↔ Geometry F o c

/-- 工具：重接已有的几何通道保持同步。 -/
theorem sync_reconnect (F : «场地») (o : «接通先后») (s : Snapshot)
    (hs : Synchronized F o s) (c : «通道») (hc : Geometry F o c) :
    Synchronized F o (addSnapshot s (.«重接» c)) :=
  ⟨hs.1, hs.2.1, fun d => («重接保留成员» s.2 c ((hs.2.2 c).mpr hc) d).trans (hs.2.2 d)⟩

/-- 工具：逐条重接已有的几何通道保持同步。 -/
theorem sync_reconnects (F : «场地») (o : «接通先后») (cs : List «通道») (s : Snapshot)
    (hs : Synchronized F o s) (hc : ∀ c ∈ cs, Geometry F o c) :
    Synchronized F o (replay s (cs.map .«重接»)) := by
  induction cs generalizing s with
  | nil => exact hs
  | cons c cs ih =>
    exact ih _ (sync_reconnect F o s hs c (hc c (by simp))) (fun d hd => hc d (by simp [hd]))

end «格子快照»

end Endfield.«证明»
