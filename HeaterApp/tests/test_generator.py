import math
import unittest

from heaterapp.core.model import Design, Params, Rect
from heaterapp.core import generator as gen
from heaterapp.core import resistance as res


def _check_invariants(tc: unittest.TestCase, design: Design, result: gen.GenResult, min_coverage=0.97):
    cells = result.cells_path
    tc.assertEqual(len(cells), len(set(cells)), "cells visited more than once")
    for i in range(len(cells) - 1):
        (x0, y0), (x1, y1) = cells[i], cells[i + 1]
        tc.assertEqual(abs(x0 - x1) + abs(y0 - y1), 1, f"non-adjacent step at {i}")
    grid = result.grid
    for c in cells:
        tc.assertIn(c, grid.free)
    # ends are the cells nearest the requested pads
    ax, ay = design.pad_a
    bx, by = design.pad_b
    a_c, b_c = grid.center(cells[0]), grid.center(cells[-1])
    tc.assertLessEqual(math.dist(a_c, (ax, ay)), max(grid.px, grid.py) * 0.75 + 5)
    tc.assertLessEqual(math.dist(b_c, (bx, by)), max(grid.px, grid.py) * 0.75 + 5)
    tc.assertGreaterEqual(result.coverage, min_coverage, f"coverage {result.coverage:.3f}")
    # trace stays clear of keepouts
    half = result.width / 2
    for c in cells:
        cx, cy = grid.center(c)
        for k in design.keepouts:
            tc.assertFalse(k.intersects_box(cx - half, cy - half, cx + half, cy + half))
    # polyline consistent with cells
    tc.assertEqual(result.path[0], grid.center(cells[0]))
    tc.assertEqual(result.path[-1], grid.center(cells[-1]))


class GeneratorTests(unittest.TestCase):
    def test_corner_to_corner(self):
        d = Design(heater=Rect(0, 0, 40, 30), pad_a=(0.5, 0.5), pad_b=(39.5, 29.5),
                   params=Params(min_width=0.75, min_space=0.19, target_ohms=None))
        r = gen.generate(d, 0.75)
        _check_invariants(self, d, r, 0.99)

    def test_same_edge_far_apart(self):
        d = Design(heater=Rect(-20, -20, 40, 40), pad_a=(-19.5, -19.5), pad_b=(19.5, -19.5),
                   params=Params(target_ohms=None))
        r = gen.generate(d, 0.75)
        _check_invariants(self, d, r, 0.99)

    def test_keepouts_opposite_sides(self):
        d = Design(heater=Rect(0, 0, 60, 50),
                   keepouts=[Rect(10, 10, 8, 8), Rect(35, 25, 12, 6), Rect(0, 40, 5, 10)],
                   pad_a=(0.5, 25), pad_b=(59.5, 25),
                   params=Params(target_ohms=None))
        r = gen.generate(d, 0.75)
        _check_invariants(self, d, r, 0.97)

    def test_vertical_orientation(self):
        d = Design(heater=Rect(0, 0, 30, 45), keepouts=[Rect(12, 20, 6, 6)],
                   pad_a=(0.5, 44.5), pad_b=(29.5, 0.5),
                   params=Params(target_ohms=None, orientation="vertical"))
        r = gen.generate(d, 0.75)
        _check_invariants(self, d, r, 0.97)

    def test_pads_outside_with_leads(self):
        d = Design(heater=Rect(0, 0, 30, 30), pad_a=(-3, 5), pad_b=(-3, 25),
                   params=Params(target_ohms=None))
        r = gen.generate(d, 0.75)
        _check_invariants(self, d, r, 0.99)
        self.assertIsNotNone(r.lead_a)
        self.assertIsNotNone(r.lead_b)
        self.assertEqual(r.pad_a, (-3, 5))
        self.assertEqual(r.pad_b, (-3, 25))
        self.assertFalse(any("crosses" in w for w in r.warnings), r.warnings)

    def test_adjacent_pads(self):
        d = Design(heater=Rect(0, 0, 20, 20), pad_a=(0.5, 0.5), pad_b=(1.5, 0.5),
                   params=Params(target_ohms=None))
        r = gen.generate(d, 0.75)
        _check_invariants(self, d, r, 0.99)

    def test_target_resistance(self):
        d = Design(heater=Rect(0, 0, 97, 97), pad_a=(0.5, 0.5), pad_b=(96.5, 0.5),
                   params=Params(min_width=0.3, min_space=0.19, copper_oz=1.0, target_ohms=6.5))
        r = gen.run(d)
        _check_invariants(self, d, r, 0.99)
        r_act = res.resistance(r.length_mm, r.width, 1.0)
        self.assertAlmostEqual(r_act, 6.5, delta=6.5 * 0.05)
        self.assertGreaterEqual(r.width, 0.3)

    def test_unreachable_target_warns(self):
        d = Design(heater=Rect(0, 0, 20, 20), pad_a=(0.5, 0.5), pad_b=(19.5, 0.5),
                   params=Params(min_width=1.0, min_space=0.2, target_ohms=100.0))
        r = gen.run(d)
        self.assertEqual(r.width, 1.0)
        self.assertTrue(any("unreachable" in w for w in r.warnings), r.warnings)

    def test_disconnected_pads_error(self):
        d = Design(heater=Rect(0, 0, 20, 20), keepouts=[Rect(9, -1, 2, 22)],
                   pad_a=(0.5, 0.5), pad_b=(19.5, 0.5), params=Params(target_ohms=None))
        with self.assertRaises(gen.GenError):
            gen.generate(d, 0.75)

    def test_too_small_error(self):
        d = Design(heater=Rect(0, 0, 0.5, 0.5), pad_a=(0, 0), pad_b=(0.5, 0.5),
                   params=Params(target_ohms=None))
        with self.assertRaises(gen.GenError):
            gen.generate(d, 0.75)


if __name__ == "__main__":
    unittest.main()
