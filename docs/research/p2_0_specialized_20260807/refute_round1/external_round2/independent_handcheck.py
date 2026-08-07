from fractions import Fraction
from math import ceil


def lane_count(rate: Fraction, cap: Fraction = Fraction(1)) -> int:
    return ceil(rate / cap)


def forced_crop(name: str, planter_x: Fraction, planter_n: int,
                crusher_x: Fraction, crusher_n: int,
                collector_x: Fraction, collector_n: int) -> None:
    # Under the supplied current census, every duty is strictly positive and <= 1.
    assert planter_x == planter_n
    producer_lanes = planter_n  # all planter duties are 1; one full-rate output lane each
    assert crusher_n == ceil(crusher_x)
    assert collector_n == ceil(collector_x)
    consumer_lanes = crusher_n + collector_n  # every active full-rate input port needs >=1 lane
    print(f"{name}: producer_lanes={producer_lanes}, consumer_lanes={consumer_lanes}, "
          f"deficit={consumer_lanes-producer_lanes}, forced_split={producer_lanes < consumer_lanes}")


def denominator_counterexample() -> None:
    # crusher_buckwheat: n=6, sum duties=11/2. Perturb uniform 11/12 by +/-1/84.
    duties = [Fraction(13, 14), Fraction(19, 21)] + [Fraction(11, 12)] * 4
    assert len(duties) == 6
    assert all(Fraction(0) < d <= 1 for d in duties)
    assert sum(duties) == Fraction(11, 2)
    scaled = [d * 660 for d in duties]
    print("free-duty denominator counterexample:")
    print(" duties=", ",".join(str(d) for d in duties))
    print(" sum=", sum(duties), " all_660_integral=", all(x.denominator == 1 for x in scaled))
    print(" scaled_by_660=", ",".join(str(x) for x in scaled))


def continuous_residual_optima() -> None:
    # For a full-rate c=2 port and duty d>1/2, the residual after one full lane is 2d-1.
    # If all six residuals were >5/6, all duties would be >11/12, contradicting sum=11/2.
    print("crusher_buckwheat continuous upper: min residual <= 5/6; uniform attains 5/6")
    # c=3, X=21/2,n=11. In the final branch residual=3d-2.
    # min residual >19/22 implies d>21/22 for all 11, contradicting the sum.
    print("crusher_sandleaf continuous upper: min residual <= 19/22; uniform attains 19/22")
    # c=2, X=21/2,n=11. min residual >10/11 implies d>21/22 for all 11.
    print("seed_collector_sandleaf continuous upper: min residual <= 10/11; uniform attains 10/11")


if __name__ == "__main__":
    forced_crop("buckwheat", Fraction(11), 11, Fraction(11, 2), 6, Fraction(11, 2), 6)
    forced_crop("sandleaf", Fraction(21), 21, Fraction(21, 2), 11, Fraction(21, 2), 11)
    denominator_counterexample()
    continuous_residual_optima()
