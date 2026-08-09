from __future__ import annotations

from itertools import product
import importlib
import unittest


active_match = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.active_signature_match"
)

ActiveSignatureMatchError = active_match.ActiveSignatureMatchError
DEFAULT_QUOTAS = active_match.DEFAULT_QUOTAS
PoseFronts = active_match.PoseFronts
Signature = active_match.Signature
match_active_signatures = active_match.match_active_signatures


class ActiveSignatureMatchTests(unittest.TestCase):
    def test_default_quota_sentinel_is_nine_signatures_and_219_bodies(self) -> None:
        self.assertEqual(len(DEFAULT_QUOTAS), 9)
        self.assertEqual(sum(DEFAULT_QUOTAS.values()), 219)
        by_template: dict[str, int] = {}
        for signature, count in DEFAULT_QUOTAS.items():
            by_template[signature.template] = by_template.get(signature.template, 0) + count
        self.assertEqual(
            by_template,
            {
                "manufacturing_3x3": 132,
                "manufacturing_5x5": 49,
                "manufacturing_6x4": 38,
            },
        )

    def test_exact_match_and_operation_expansion(self) -> None:
        small = Signature("t", 1, 1)
        large = Signature("t", 2, 1)
        poses = (
            PoseFronts("p1", "t", ((1, 0), (2, 0)), ((1, 2),)),
            PoseFronts("p2", "t", ((4, 0),), ((4, 2),)),
        )
        result = match_active_signatures(
            poses,
            facility_body_cells=(),
            pole_body_cells=(),
            quotas={small: 1, large: 1},
            operation_expansion={small: ("op_small",), large: ("op_large",)},
        )
        self.assertTrue(result.ok)
        self.assertIsNone(result.hall_failure)
        by_id = {match.pose_id: match for match in result.matches}
        self.assertEqual(by_id["p1"].signature, large)
        self.assertEqual(by_id["p1"].operation, "op_large")
        self.assertEqual(by_id["p2"].signature, small)
        self.assertEqual(by_id["p2"].operation, "op_small")

    def test_body_and_pole_cells_remove_physical_fronts(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", ((1, 0), (2, 0)), ((1, 2), (2, 2)))
        result = match_active_signatures(
            (pose,),
            facility_body_cells={(1, 0)},
            pole_body_cells={(1, 2)},
            quotas={signature: 1},
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.matches[0].free_input_fronts, ((2, 0),))
        self.assertEqual(result.matches[0].free_output_fronts, ((2, 2),))
        self.assertEqual(result.matches[0].active_input_fronts, ((2, 0),))
        self.assertEqual(result.matches[0].active_output_fronts, ((2, 2),))

    def test_opposite_ports_may_share_one_front_cell(self) -> None:
        signature = Signature("t", 1, 1)
        shared = (3, 3)
        poses = (
            PoseFronts("left", "t", (shared,), ((1, 1),)),
            PoseFronts("right", "t", ((5, 5),), (shared,)),
        )
        result = match_active_signatures(
            poses,
            facility_body_cells=(),
            pole_body_cells=(),
            quotas={signature: 2},
        )
        self.assertTrue(result.ok)
        by_id = {match.pose_id: match for match in result.matches}
        self.assertEqual(by_id["left"].active_input_fronts, (shared,))
        self.assertEqual(by_id["right"].active_output_fronts, (shared,))

    def test_minimal_hall_failure(self) -> None:
        small = Signature("t", 1, 1)
        large = Signature("t", 2, 1)
        poses = (
            PoseFronts("p1", "t", ((1, 0),), ((1, 2),)),
            PoseFronts("p2", "t", ((4, 0),), ((4, 2),)),
        )
        result = match_active_signatures(
            poses,
            facility_body_cells=(),
            pole_body_cells=(),
            quotas={small: 1, large: 1},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.matches, ())
        self.assertIsNotNone(result.hall_failure)
        failure = result.hall_failure
        assert failure is not None
        self.assertEqual(failure.signature_subset, (small,))
        self.assertEqual(failure.slot_capacity, 1)
        self.assertEqual(failure.forced_pose_count, 2)
        self.assertEqual(failure.deficiency, 1)
        self.assertEqual(failure.minimal_witness_pose_ids, ("p1", "p2"))

    def test_empty_domain_hall_failure(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", ((1, 0),), ((1, 2),))
        result = match_active_signatures(
            (pose,),
            facility_body_cells={(1, 0)},
            pole_body_cells=(),
            quotas={signature: 1},
        )
        self.assertFalse(result.ok)
        failure = result.hall_failure
        assert failure is not None
        self.assertEqual(failure.signature_subset, ())
        self.assertEqual(failure.slot_capacity, 0)
        self.assertEqual(failure.forced_pose_count, 1)
        self.assertEqual(failure.deficiency, 1)
        self.assertEqual(failure.minimal_witness_pose_ids, ("p",))

    def test_out_of_grid_front_is_unusable_but_diagnostic_is_returned(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", ((-1, 0),), ((1, 2),))
        result = match_active_signatures(
            (pose,),
            facility_body_cells=(),
            pole_body_cells=(),
            quotas={signature: 1},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.pose_audits[0].free_input_fronts, ())
        self.assertEqual(result.pose_audits[0].compatible_signatures, ())

    def test_exhaustive_small_instances_agree_with_bruteforce(self) -> None:
        small = Signature("t", 1, 1)
        large = Signature("t", 2, 1)
        for pose_count in range(1, 5):
            for capabilities in product(range(3), repeat=pose_count):
                poses = tuple(
                    PoseFronts(
                        f"p{index}",
                        "t",
                        tuple((10 * index + offset, 2) for offset in range(capability)),
                        ((10 * index, 3),),
                    )
                    for index, capability in enumerate(capabilities)
                )
                compatibility = tuple(
                    (() if capability == 0 else (small,) if capability == 1 else (small, large))
                    for capability in capabilities
                )
                for large_quota in range(pose_count + 1):
                    quotas = {small: pose_count - large_quota, large: large_quota}
                    expected = any(
                        all(choice in compatibility[index] for index, choice in enumerate(candidate))
                        and candidate.count(small) == quotas[small]
                        and candidate.count(large) == quotas[large]
                        for candidate in product((small, large), repeat=pose_count)
                    )
                    result = match_active_signatures(
                        poses,
                        facility_body_cells=(),
                        pole_body_cells=(),
                        quotas=quotas,
                    )
                    self.assertEqual(
                        result.ok,
                        expected,
                        (pose_count, capabilities, large_quota),
                    )
                    if not expected:
                        failure = result.hall_failure
                        assert failure is not None
                        self.assertGreater(failure.deficiency, 0)
                        self.assertEqual(
                            len(failure.minimal_witness_pose_ids),
                            failure.slot_capacity + 1,
                        )

    def test_operation_expansion_is_validated_before_hall_result(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", (), ((1, 2),))
        with self.assertRaises(ActiveSignatureMatchError) as raised:
            match_active_signatures(
                (pose,),
                facility_body_cells=(),
                pole_body_cells=(),
                quotas={signature: 1},
                operation_expansion={signature: ()},
            )
        self.assertEqual(raised.exception.code, "OPERATION_EXPANSION_COUNT")

    def test_operation_expansion_rejects_extra_signature(self) -> None:
        signature = Signature("t", 1, 1)
        extra = Signature("t", 2, 1)
        pose = PoseFronts("p", "t", ((1, 0),), ((1, 2),))
        with self.assertRaises(ActiveSignatureMatchError) as raised:
            match_active_signatures(
                (pose,),
                facility_body_cells=(),
                pole_body_cells=(),
                quotas={signature: 1},
                operation_expansion={signature: ("op",), extra: ()},
            )
        self.assertEqual(raised.exception.code, "OPERATION_EXPANSION_KEYS")

    def test_template_quota_total_mismatch_fails_closed(self) -> None:
        signature = Signature("t", 1, 1)
        poses = (
            PoseFronts("p1", "t", ((1, 0),), ((1, 2),)),
            PoseFronts("p2", "t", ((4, 0),), ((4, 2),)),
        )
        with self.assertRaises(ActiveSignatureMatchError) as raised:
            match_active_signatures(
                poses,
                facility_body_cells=(),
                pole_body_cells=(),
                quotas={signature: 1},
            )
        self.assertEqual(raised.exception.code, "TEMPLATE_QUOTA_MISMATCH")

    def test_facility_pole_overlap_fails_closed(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", ((1, 0),), ((1, 2),))
        with self.assertRaises(ActiveSignatureMatchError) as raised:
            match_active_signatures(
                (pose,),
                facility_body_cells={(4, 4)},
                pole_body_cells={(4, 4)},
                quotas={signature: 1},
            )
        self.assertEqual(raised.exception.code, "OCCUPANCY_OVERLAP")

    def test_out_of_grid_occupancy_fails_closed(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", ((1, 0),), ((1, 2),))
        with self.assertRaises(ActiveSignatureMatchError) as raised:
            match_active_signatures(
                (pose,),
                facility_body_cells={(-1, 0)},
                pole_body_cells=(),
                quotas={signature: 1},
            )
        self.assertEqual(raised.exception.code, "OCCUPANCY_OUT_OF_GRID")

    def test_malformed_signature_and_duplicate_fronts_fail_at_construction(self) -> None:
        with self.assertRaises(ActiveSignatureMatchError) as signature_error:
            Signature("t", True, 1)
        self.assertEqual(signature_error.exception.code, "INTEGER_INVALID")

        with self.assertRaises(ActiveSignatureMatchError) as fronts_error:
            PoseFronts("p", "t", ((1, 1), (1, 1)), ((2, 2),))
        self.assertEqual(fronts_error.exception.code, "FRONTS_DUPLICATE")

    def test_duplicate_pose_ids_and_boolean_grid_dimension_fail_closed(self) -> None:
        signature = Signature("t", 1, 1)
        pose = PoseFronts("p", "t", ((1, 0),), ((1, 2),))
        with self.assertRaises(ActiveSignatureMatchError) as duplicate_error:
            match_active_signatures(
                (pose, pose),
                facility_body_cells=(),
                pole_body_cells=(),
                quotas={signature: 2},
            )
        self.assertEqual(duplicate_error.exception.code, "POSE_ID_DUPLICATE")

        with self.assertRaises(ActiveSignatureMatchError) as grid_error:
            match_active_signatures(
                (pose,),
                facility_body_cells=(),
                pole_body_cells=(),
                quotas={signature: 1},
                grid_width=True,
            )
        self.assertEqual(grid_error.exception.code, "GRID_INVALID")


if __name__ == "__main__":
    unittest.main()
