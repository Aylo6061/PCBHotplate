"""Write a heater design + generated trace as a KiCad 8/9 footprint (.kicad_mod)."""
from __future__ import annotations

import re
import uuid

from .generator import GenResult
from .model import Design

KICAD_VERSION = 20240108


def _f(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _uuid() -> str:
    return str(uuid.uuid4())


def safe_name(name: str) -> str:
    name = re.sub(r'[\/:*?"<>|\s]+', "_", name.strip())
    return name or "Heater"


def footprint_text(design: Design, result: GenResult) -> str:
    """Return the .kicad_mod contents. Footprint origin is the heater centre."""
    p = design.params
    heater = design.heater
    board = design.board_rect() or heater
    ox, oy = heater.cx, heater.cy
    name = safe_name(p.name)
    w = result.width

    def pt(x: float, y: float) -> str:
        return f"{_f(x - ox)} {_f(y - oy)}"

    out: list[str] = []
    out.append(f'(footprint "{name}"')
    out.append(f"\t(version {KICAD_VERSION})")
    out.append('\t(generator "heaterapp")')
    out.append('\t(generator_version "1.0")')
    out.append('\t(layer "F.Cu")')
    out.append(f'\t(descr "PCB heater, {_f(heater.w)} x {_f(heater.h)} mm heater on {_f(board.w)} x {_f(board.h)} mm '
               f'board, trace {_f(w)} mm, length {_f(result.length_mm)} mm")')
    out.append('\t(tags "heater")')
    out.append('\t(attr smd exclude_from_bom)')

    ref_y = board.y - oy - 1.5
    val_y = board.y2 - oy + 1.5
    out.append(f'\t(property "Reference" "REF**"\n\t\t(at 0 {_f(ref_y)} 0)\n\t\t(layer "F.SilkS")\n'
               f'\t\t(uuid "{_uuid()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n'
               f'\t\t\t)\n\t\t)\n\t)')
    out.append(f'\t(property "Value" "{name}"\n\t\t(at 0 {_f(val_y)} 0)\n\t\t(layer "F.Fab")\n'
               f'\t\t(uuid "{_uuid()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n'
               f'\t\t\t)\n\t\t)\n\t)')
    for prop, layer in (("Footprint", "F.Fab"), ("Datasheet", "F.Fab"), ("Description", "F.Fab")):
        out.append(f'\t(property "{prop}" ""\n\t\t(at 0 0 0)\n\t\t(layer "{layer}")\n\t\t(hide yes)\n'
                   f'\t\t(uuid "{_uuid()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n'
                   f'\t\t\t)\n\t\t)\n\t)')

    # Courtyard around the board outline (falls back to the heater area)
    m = 0.25
    x1, y1, x2, y2 = board.x - m, board.y - m, board.x2 + m, board.y2 + m
    out.append(f'\t(fp_rect\n\t\t(start {pt(x1, y1)})\n\t\t(end {pt(x2, y2)})\n'
               f'\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill none)\n'
               f'\t\t(layer "F.CrtYd")\n\t\t(uuid "{_uuid()}")\n\t)')
    out.append(f'\t(fp_rect\n\t\t(start {pt(heater.x, heater.y)})\n\t\t(end {pt(heater.x2, heater.y2)})\n'
               f'\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill none)\n'
               f'\t\t(layer "F.Fab")\n\t\t(uuid "{_uuid()}")\n\t)')
    if board is not heater:
        out.append(f'\t(fp_rect\n\t\t(start {pt(board.x, board.y)})\n\t\t(end {pt(board.x2, board.y2)})\n'
                   f'\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type dash)\n\t\t)\n\t\t(fill none)\n'
                   f'\t\t(layer "F.Fab")\n\t\t(uuid "{_uuid()}")\n\t)')

    # Heater trace
    for (ax, ay), (bx, by) in result.segments():
        out.append(f'\t(fp_line\n\t\t(start {pt(ax, ay)})\n\t\t(end {pt(bx, by)})\n'
                   f'\t\t(stroke\n\t\t\t(width {_f(w)})\n\t\t\t(type solid)\n\t\t)\n'
                   f'\t\t(layer "F.Cu")\n\t\t(uuid "{_uuid()}")\n\t)')

    # Pads
    for num, (px, py) in (("1", result.pad_a), ("2", result.pad_b)):
        out.append(f'\t(pad "{num}" smd rect\n\t\t(at {pt(px, py)})\n\t\t(size {_f(p.pad_w)} {_f(p.pad_h)})\n'
                   f'\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n\t\t(uuid "{_uuid()}")\n\t)')

    # Keepouts as rule areas
    for i, k in enumerate(design.keepouts, 1):
        pts = "\n".join(f"\t\t\t\t(xy {pt(x, y)})" for x, y in
                        ((k.x, k.y), (k.x2, k.y), (k.x2, k.y2), (k.x, k.y2)))
        out.append(f'\t(zone\n\t\t(net 0)\n\t\t(net_name "")\n\t\t(layers "F.Cu")\n\t\t(name "keepout{i}")\n'
                   f'\t\t(uuid "{_uuid()}")\n\t\t(hatch edge 0.5)\n'
                   f'\t\t(connect_pads\n\t\t\t(clearance 0)\n\t\t)\n\t\t(min_thickness 0.25)\n'
                   f'\t\t(filled_areas_thickness no)\n'
                   f'\t\t(keepout\n\t\t\t(tracks not_allowed)\n\t\t\t(vias not_allowed)\n\t\t\t(pads not_allowed)\n'
                   f'\t\t\t(copperpour not_allowed)\n\t\t\t(footprints not_allowed)\n\t\t)\n'
                   f'\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n'
                   f'\t\t(polygon\n\t\t\t(pts\n{pts}\n\t\t\t)\n\t\t)\n\t)')

    out.append(")")
    return "\n".join(out) + "\n"


def write_footprint(path: str, design: Design, result: GenResult) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(footprint_text(design, result))
