import Endfield.«证明».«基础»

/-!
证明「立表的带内整齐」。筛选条件保证通道两头都是传送带，合规保证不连自己。
传送带的进、出端口都只有一个，因此不同通道不能共用起点或止点。
最后将通道映到互不相同的起点，用单位表包含这些起点得到条数上界。
-/

namespace Endfield.«证明»

private theorem short_list_eq {α : Type} {xs : List α} (h : xs.length ≤ 1)
    {a b : α} (ha : a ∈ xs) (hb : b ∈ xs) : a = b := by
  cases xs with
  | nil => simp at ha
  | cons x xs =>
    cases xs with
    | nil =>
      have ha' : a = x := by simpa using ha
      have hb' : b = x := by simpa using hb
      exact ha'.trans hb'.symm
    | cons y ys => simp at h

/-- 据：元件、端口、通道

合规且端口数合的历史立出的带内通道两端整齐，且条数不超过单位数。
-/
theorem «立表的带内整齐» : «命题».«立表的带内整齐» := by
  intro H hH hp
  let L := H.«布局于» H.length
  let bs := H.«立表».«带内»
  have hr : L.«整齐» := H.«合规则整齐» hH H.length
  have mem_bs (c : «通道») (hc : c ∈ bs) :
      c ∈ L.«通道表».map (·.1) ∧ L.«种类» c.«起» = some .«传送带» ∧
        L.«种类» c.«止» = some .«传送带» := by
    simpa [bs, «历史».«立表», «历史».«立表照», L, List.mem_filter,
      Bool.and_eq_true] using hc
  have hn : bs.Nodup := hr.«通道不重».filter _
  have hw : bs.Pairwise (fun c d => c.«起» ≠ d.«起» ∧ c.«止» ≠ d.«止») := by
    apply List.Pairwise.imp_of_mem _ hn
    intro c d hc hd hne
    obtain ⟨pc, hpc, ec⟩ := List.mem_map.mp (mem_bs c hc).1
    obtain ⟨pd, hpd, ed⟩ := List.mem_map.mp (mem_bs d hd).1
    constructor
    · intro he
      have hl := L.«端口数合_出» c.«起» .«传送带» hp (mem_bs c hc).2.1
      have hpc' : pc ∈ L.«出» c.«起» := by simp [«布局».«出», hpc, ec]
      have hpd' : pd ∈ L.«出» c.«起» := by simp [«布局».«出», hpd, ed, he]
      have eq := short_list_eq hl hpc' hpd'
      exact hne (ec.symm.trans ((congrArg Prod.fst eq).trans ed))
    · intro he
      have hl := L.«端口数合_进» c.«止» .«传送带» hp (mem_bs c hc).2.2
      have hpc' : pc ∈ L.«进» c.«止» := by simp [«布局».«进», hpc, ec]
      have hpd' : pd ∈ L.«进» c.«止» := by simp [«布局».«进», hpd, ed, he]
      have eq := short_list_eq hl hpc' hpd'
      exact hne (ec.symm.trans ((congrArg Prod.fst eq).trans ed))
  constructor
  · refine ⟨?_, hw⟩
    intro c hc
    obtain ⟨p, hp', ep⟩ := List.mem_map.mp (mem_bs c hc).1
    exact ⟨(mem_bs c hc).2.1, (mem_bs c hc).2.2, ep ▸ hr.«不连自己» p hp'⟩
  · change bs.length ≤ L.«单位表».length
    have hnd : (bs.map (·.«起»)).Nodup :=
      List.pairwise_map.mpr (hw.imp (fun h => h.1))
    have hsub : bs.map (·.«起») ⊆ L.«单位表».map (·.1) := by
      intro u hu
      obtain ⟨c, hc, rfl⟩ := List.mem_map.mp hu
      have hk := (mem_bs c hc).2.1
      obtain ⟨p, hfind, _⟩ := Option.map_eq_some_iff.mp hk
      have hm := List.mem_of_find?_eq_some hfind
      have he : p.1 = c.«起» := by simpa using List.find?_some hfind
      exact List.mem_map.mpr ⟨p, hm, he⟩
    simpa only [List.length_map] using hnd.length_le_of_subset hsub

end Endfield.«证明»
