import unittest

from heaterapp.core import thermal as th

CV, PWM, CC = th.MODES
FLAT, VERT = th.ORIENTATIONS


def plate(**kw):
    base = dict(width_m=0.097, height_m=0.097, r20=6.5, t_amb_c=25.0)
    base.update(kw)
    return th.Plate(**base)


class ThermalTests(unittest.TestCase):
    def test_loss_monotone_and_zero_at_ambient(self):
        p = plate()
        self.assertEqual(th.power_loss(p, 25.0, FLAT), 0.0)
        prev = 0.0
        for t in range(30, 400, 10):
            cur = th.power_loss(p, t, FLAT)
            self.assertGreater(cur, prev)
            prev = cur

    def test_radiation_comparable_to_convection_at_250c(self):
        lb = th.loss_breakdown(plate(), 250.0, FLAT)
        self.assertGreater(lb.radiation_w, 0.5 * lb.convection_w)
        self.assertLess(lb.radiation_w, 3 * lb.convection_w)
        # 2 faces * 0.9 * sigma * A * (T^4 - Ta^4)
        expect = 2 * 0.9 * th.SIGMA * 0.097 ** 2 * (523.15 ** 4 - 298.15 ** 4)
        self.assertAlmostEqual(lb.radiation_w, expect, places=6)

    def test_emissivity_and_extra_loss(self):
        base = th.power_loss(plate(), 200.0, FLAT)
        self.assertLess(th.power_loss(plate(emissivity=0.1), 200.0, FLAT), base)
        self.assertAlmostEqual(th.power_loss(plate(extra_loss_w_per_k=0.5), 200.0, FLAT), base + 0.5 * 175, places=6)

    def test_cv_tmax_scales_with_voltage(self):
        p = plate()
        t24, ra = th.steady_state(p, th.Supply(CV, voltage=24), FLAT)
        t12, rb = th.steady_state(p, th.Supply(CV, voltage=12), FLAT)
        self.assertFalse(ra or rb)
        self.assertGreater(t24, t12)
        self.assertGreater(t12, 60)
        self.assertLess(t24, 300)
        # power balance holds at the solution
        sup = th.Supply(CV, voltage=24)
        self.assertAlmostEqual(sup.power_in(p, t24), th.power_loss(p, t24, FLAT), delta=1e-3)

    def test_vertical_close_to_flat(self):
        p = plate()
        tf, _ = th.steady_state(p, th.Supply(CV, voltage=24), FLAT)
        tv, _ = th.steady_state(p, th.Supply(CV, voltage=24), VERT)
        self.assertLess(abs(tf - tv), 15)

    def test_pwm_full_duty_equals_cv_and_duty_needed(self):
        p = plate()
        a_cv = th.analyse(p, th.Supply(CV, voltage=24), FLAT, 120)
        a_pwm = th.analyse(p, th.Supply(PWM, voltage=24), FLAT, 120)
        self.assertAlmostEqual(a_cv.t_max_c, a_pwm.t_max_c, places=6)
        self.assertIsNone(a_cv.duty_at_design)
        self.assertTrue(0 < a_pwm.duty_at_design < 1)
        self.assertAlmostEqual(a_pwm.duty_at_design * a_pwm.p_available_w, a_pwm.p_needed_w, places=6)

    def test_cc_compliance_limits_and_runaway(self):
        p = plate()
        # 2 A into 6.5 ohm needs 13 V cold and more when hot; 10 V compliance -> effectively CV at 10 V
        t_cc, ra = th.steady_state(p, th.Supply(CC, current=2, compliance_v=10), FLAT)
        t_cv, _ = th.steady_state(p, th.Supply(CV, voltage=10), FLAT)
        self.assertFalse(ra)
        self.assertAlmostEqual(t_cc, t_cv, places=3)
        # huge current with unlimited compliance -> equilibrium above the 1500 C ceiling
        _, runaway = th.steady_state(p, th.Supply(CC, current=30, compliance_v=1e6), FLAT)
        self.assertTrue(runaway)
        a = th.analyse(p, th.Supply(CC, current=30, compliance_v=1e6), FLAT, 200)
        self.assertTrue(a.runaway and a.reaches)

    def test_reaches_and_time(self):
        p = plate(board_thickness_m=1.6e-3)
        a = th.analyse(p, th.Supply(CV, voltage=24), FLAT, 120)
        self.assertTrue(a.reaches)
        self.assertIsNotNone(a.time_to_design_s)
        self.assertTrue(5 < a.time_to_design_s < 600)
        b = th.analyse(p, th.Supply(CV, voltage=24), FLAT, 400)
        self.assertFalse(b.reaches)
        self.assertIsNone(b.time_to_design_s)
        self.assertEqual(len(th.analyse_all(p, 24, 2, 30, 120)), 6)

    def test_air_properties_interpolate(self):
        k, nu, pr = th.air_properties(325.0)
        self.assertAlmostEqual(k, (0.0263 + 0.0300) / 2, places=6)
        self.assertAlmostEqual(nu, (1.589e-5 + 2.092e-5) / 2, places=9)
        self.assertEqual(th.air_properties(100.0), th._AIR[0][1:])
        self.assertEqual(th.air_properties(5000.0), th._AIR[-1][1:])


if __name__ == "__main__":
    unittest.main()
