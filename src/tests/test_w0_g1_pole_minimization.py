"""W0 G1: T-POLE-MINIMAL, the sufficient restriction that buys irredundancy.

research-only.  The claim under test: an inclusion-minimal covering pole set
satisfies the repository's power-irredundancy predicate
(``src/search/pr2_l0_artifact_core.py`` :1030-1041: poles <= powered instances,
every pole covers something, every pole is some instance's sole coverer).  That
is what lets stage B place poles greedily and then shrink, instead of encoding
irredundancy into the master.
"""

from __future__ import annotations

from pathlib import Path
import random
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import g1_pattern_evaluator as ev  # noqa: E402

pytestmark = pytest.mark.evidence

GRID = 70


def _random_instance(rng: random.Random):
    """A few 3x3 machines plus a pole at every legal anchor that covers them."""
    machines = []
    for index in range(rng.randint(1, 6)):
        ax = rng.randrange(0, GRID - 3)
        ay = rng.randrange(0, GRID - 3)
        machines.append((f"m{index}", ev.body_cells("manufacturing_3x3", 0, (ax, ay))))
    poles = []
    for _ in range(rng.randint(3, 12)):
        poles.append((rng.randrange(0, GRID - 1), rng.randrange(0, GRID - 1)))
    # Guarantee coverage: give every machine a pole sitting on its own anchor.
    for _name, cells in machines:
        poles.append(cells[0])
    return machines, sorted(set(poles))


@pytest.mark.parametrize("seed", range(200))
def test_minimal_cover_satisfies_the_repo_irredundancy_predicate(seed: int) -> None:
    """[28] 200 fixed-seed instances: minimality implies the repo predicate."""
    rng = random.Random(seed)
    machines, poles = _random_instance(rng)
    clip = (0, 0, GRID, GRID)
    minimal = ev.minimize_poles(machines, poles, clip=clip)

    stencils = {anchor: ev.coverage_cells(anchor, clip=clip) for anchor in minimal}
    coverers = {
        name: [anchor for anchor in minimal if set(cells) & stencils[anchor]]
        for name, cells in machines
    }
    # 1. still a cover
    assert all(coverers[name] for name, _cells in machines)
    # 2. no more poles than powered instances
    assert len(minimal) <= len(machines)
    # 3. every pole is the sole coverer of some instance, and those instances
    #    are pairwise distinct -- which is where bound 2 comes from.
    private: dict[tuple[int, int], str] = {}
    for anchor in minimal:
        owned = [name for name, hits in coverers.items() if hits == [anchor]]
        assert owned, f"pole {anchor} is never a sole coverer"
        private[anchor] = owned[0]
    assert len(set(private.values())) == len(minimal)


@pytest.mark.parametrize("seed", range(50))
def test_minimisation_is_deterministic_and_only_removes_poles(seed: int) -> None:
    """[29] Machines untouched, output is a subset, repeated runs agree."""
    rng = random.Random(1000 + seed)
    machines, poles = _random_instance(rng)
    before = [(name, tuple(cells)) for name, cells in machines]
    first = ev.minimize_poles(machines, poles, clip=(0, 0, GRID, GRID))
    second = ev.minimize_poles(machines, poles, clip=(0, 0, GRID, GRID))

    assert first == second, "same input must give the same minimal set"
    assert set(first) <= set(poles), "minimisation may only remove poles"
    assert [(name, tuple(cells)) for name, cells in machines] == before
    assert first == tuple(sorted(first)), "output stays in deterministic order"


def test_minimisation_refuses_an_incomplete_cover() -> None:
    """[29b] Fail closed rather than silently return a non-cover."""
    machines = [("m0", ev.body_cells("manufacturing_3x3", 0, (0, 0)))]
    with pytest.raises(ValueError, match="does not cover"):
        ev.minimize_poles(machines, [(60, 60)], clip=(0, 0, GRID, GRID))


def test_minimisation_drops_a_plainly_redundant_pole() -> None:
    """[29c] Two poles covering one machine collapse to one.

    Candidates are tried for removal in ascending ``(x, y)`` order, so the
    survivor is the *later* one -- that is the determinism, not an accident.
    """
    machines = [("m0", ev.body_cells("manufacturing_3x3", 0, (30, 30)))]
    minimal = ev.minimize_poles(machines, [(29, 29), (31, 31)], clip=(0, 0, GRID, GRID))
    assert minimal == ((31, 31),)


def test_freeing_a_pole_never_shrinks_the_free_space() -> None:
    """[29d] Why minimisation is safe after the fact: it only adds free cells."""
    machines = [
        ("m0", ev.body_cells("manufacturing_3x3", 0, (30, 30))),
        ("m1", ev.body_cells("manufacturing_3x3", 0, (40, 40))),
    ]
    poles = [(29, 29), (31, 31), (39, 39), (41, 41)]
    minimal = ev.minimize_poles(machines, poles, clip=(0, 0, GRID, GRID))
    occupied_before = {
        cell for anchor in poles for cell in ev.pole_cells(anchor)
    }
    occupied_after = {
        cell for anchor in minimal for cell in ev.pole_cells(anchor)
    }
    assert occupied_after <= occupied_before
