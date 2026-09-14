import math
import unittest

from heaterapp.core import inductance as ind

T = 35e-6


class InductanceTests(unittest.TestCase):
    def test_straight_trace_about_1nh_per_mm(self):
        L = ind.self_inductance(0.1, 1e-3, T)
        self.assertTrue(90e-9 < L < 140e-9)

    def test_mutual_equal_filaments_closed_form(self):
        l, d = 0.1, 1e-3
        expect = ind.MU0 * l / (2 * math.pi) * (math.log(l / d + math.sqrt(1 + (l / d) ** 2))
                                                - math.sqrt(1 + (d / l) ** 2) + d / l)
        self.assertAlmostEqual(ind.mutual_parallel(0, l, 0, l, d), expect, places=15)
        # symmetric and decreasing with distance
        self.assertAlmostEqual(ind.mutual_parallel(0, l, 0.02, l + 0.02, d), ind.mutual_parallel(0.02, l + 0.02, 0, l, d))
        self.assertGreater(ind.mutual_parallel(0, l, 0, l, d), ind.mutual_parallel(0, l, 0, l, 5 * d))

    def test_hairpin_cancels(self):
        segs = [((0, 0), (100, 0)), ((100, 0), (100, 1)), ((100, 1), (0, 1))]
        L = ind.trace_inductance(segs, 0.5, T)
        L_self = sum(ind.self_inductance(math.dist(a, b) * 1e-3, 0.5e-3, T) for a, b in segs)
        self.assertLess(L, 0.5 * L_self)
        self.assertGreater(L, 0)
        # wider spacing -> more inductance
        wide = [((0, 0), (100, 0)), ((100, 0), (100, 5)), ((100, 5), (0, 5))]
        self.assertGreater(ind.trace_inductance(wide, 0.5, T), L)

    def test_meander_direction_independent(self):
        segs = [((0, 0), (50, 0)), ((50, 0), (50, 1)), ((50, 1), (0, 1)), ((0, 1), (0, 2)), ((0, 2), (50, 2))]
        rev = [(b, a) for a, b in reversed(segs)]
        self.assertAlmostEqual(ind.trace_inductance(segs, 0.5, T), ind.trace_inductance(rev, 0.5, T), places=15)


if __name__ == "__main__":
    unittest.main()
