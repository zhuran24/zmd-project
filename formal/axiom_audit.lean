import ZmdFormal
#print axioms ZmdFormal.Tns.all_bad_of_cover
#print axioms ZmdFormal.Tns.exists_minimal_below
#print axioms ZmdFormal.Tns.all_bad_of_minimal_bad
#print axioms ZmdFormal.Tns.std_domain_collapse
#print axioms ZmdFormal.Tns.std_domain_minimal_66
#print axioms ZmdFormal.Tns.std_domain_minimal_iff
#print axioms ZmdFormal.F5.labeled_orbit_lift
#print axioms ZmdFormal.F5.labeled_orbit_lift_group_preserving
#print axioms ZmdFormal.F5.realizes_comp
#print axioms ZmdFormal.F5.nogood_mod_relabel
#print axioms ZmdFormal.F5.dedup_collapse_strengthens
#print axioms ZmdFormal.F5.dedup_collapse_can_false_reject
#print axioms ZmdFormal.F5.presence_key_alias_collapse_strengthens
#print axioms ZmdFormal.F5.presence_key_alias_can_false_reject
-- DesignStatements（盲形式化陈述 + 本方施工，2026-07-05）
-- A. TNS Finset 版
#print axioms ZmdDesignStatements.dimwise_antitone_cover_soundness
#print axioms ZmdDesignStatements.dimwise_antitone_cover_certificate_soundness
#print axioms ZmdDesignStatements.minimalDims_cover
#print axioms ZmdDesignStatements.minimalDims_antichain
#print axioms ZmdDesignStatements.dimwise_antitone_minimal_antichain_soundness
#print axioms ZmdDesignStatements.domain_with_bottom_minimalDims_singleton
#print axioms ZmdDesignStatements.standard_domain_minimalDims_singleton
#print axioms ZmdDesignStatements.standard_domain_single_point_collapse_soundness
-- B. F5 anon_lift_sound 主链
#print axioms ZmdDesignStatements.Orbit.named_orbit_lift_soundness
#print axioms ZmdDesignStatements.Orbit.anonMultisetExtends_gives_matching
#print axioms ZmdDesignStatements.Orbit.partialSlotPermExtends_of_fintype
#print axioms ZmdDesignStatements.Orbit.matching_extends_to_group_permutation
#print axioms ZmdDesignStatements.Orbit.anon_multiset_lift_soundness_from_named_representative
#print axioms ZmdDesignStatements.Orbit.boolean_presence_refines_multiset
#print axioms ZmdDesignStatements.Orbit.boolean_presence_lift_soundness_from_named_representative
-- C. no-repeat 反例（decide 版，无 native_decide）
#print axioms ZmdDesignStatements.NoRepeatCounterexample.presence_dedup_strengthens_cut_counterexample
-- CutFamilies（第一梯队 6 family 核心，2026-07-05）
#print axioms ZmdFormal.CutFamilies.f9_area_bound
#print axioms ZmdFormal.CutFamilies.f9_overflow_infeasible
#print axioms ZmdFormal.CutFamilies.f1_occupancy_bound
#print axioms ZmdFormal.CutFamilies.f1_demand_overflow_infeasible
#print axioms ZmdFormal.CutFamilies.f7_cover_filter_monotone
#print axioms ZmdFormal.CutFamilies.f7_empty_cover_monotone
#print axioms ZmdFormal.CutFamilies.f4_closed_set_absorbs_reach
#print axioms ZmdFormal.CutFamilies.f4_unreachable_outside_closed
#print axioms ZmdFormal.CutFamilies.f4_subgraph_reach_mono
#print axioms ZmdFormal.CutFamilies.f6_strip_capacity
#print axioms ZmdFormal.CutFamilies.f6_packing_bound
#print axioms ZmdFormal.CutFamilies.f6_packing_overflow_infeasible
#print axioms ZmdFormal.CutFamilies.f6_cross_side_lower_bound
#print axioms ZmdFormal.CutFamilies.f2_cutset_bound
#print axioms ZmdFormal.CutFamilies.f2_demand_overflow_infeasible
-- CutFamilies 第二梯队 F3（2026-07-05）
#print axioms ZmdFormal.CutFamilies.f3_blocked_port_infeasible
#print axioms ZmdFormal.CutFamilies.f3_pair_literal_cut_sound
-- FrameworkLemmas（F5 复合安全 / frontier lex 剪枝 / TP7-S 键边界，2026-07-05）
#print axioms ZmdFormal.Framework.f5_compound_safety
#print axioms ZmdFormal.Framework.f5_compound_needs_phom
#print axioms ZmdFormal.Framework.frontier_prune_dominates
#print axioms ZmdFormal.Framework.frontier_prune_preserves_max
#print axioms ZmdFormal.Framework.frontier_prune_preserves_max_lex
#print axioms ZmdFormal.Framework.eq_key_violated_iff
#print axioms ZmdFormal.Framework.tp7s_eq_key_sound
#print axioms ZmdFormal.Framework.tp7s_eq_key_no_overcut
#print axioms ZmdFormal.Framework.tp7s_selected_set_nogood_overcuts
