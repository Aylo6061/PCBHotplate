import os
import tempfile
import unittest

from heaterapp.core.model import Design, Params, Rect
from heaterapp.core import generator as gen
from heaterapp.core import kicad_export, design_io


class ExportTests(unittest.TestCase):
    def test_footprint_text(self):
        d = Design(heater=Rect(0, 0, 20, 12), keepouts=[Rect(8, 4, 3, 3)],
                   pad_a=(0.5, 0.5), pad_b=(-2, 11), params=Params(target_ohms=None, name="My Heater"))
        r = gen.generate(d, 0.75)
        txt = kicad_export.footprint_text(d, r)
        self.assertTrue(txt.startswith('(footprint "My_Heater"'))
        self.assertEqual(txt.count("(fp_line"), len(r.segments()))
        self.assertIn('(pad "1" smd rect', txt)
        self.assertIn('(pad "2" smd rect', txt)
        self.assertEqual(txt.count("(zone"), 1)
        self.assertEqual(txt.count("("), txt.count(")"))

    def test_design_roundtrip(self):
        d = Design(heater=Rect(1, 2, 30, 40), keepouts=[Rect(5, 5, 2, 2)], pad_a=(1, 1), pad_b=(3, 3),
                   params=Params(target_ohms=4.2, orientation="vertical", name="X"))
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "d.json")
            design_io.save_design(p, d)
            d2 = design_io.load_design(p)
        self.assertEqual(d2.to_dict(), d.to_dict())


if __name__ == "__main__":
    unittest.main()
