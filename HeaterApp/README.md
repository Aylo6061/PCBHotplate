# HeaterApp

Standalone desktop app that generates a serpentine PCB heater and saves it as a
KiCad footprint (`.kicad_mod`).

- Draw the **heater area** as a rectangle, add rectangular **keepouts**
  (mounting holes, thermistor, …), and place the two **end pads** anywhere —
  inside the area (they snap to the trace grid) or outside (a straight lead is added).
- Optionally set the **PCB outline** (Design tab) when the board is larger than the
  heater, e.g. a 97 mm heater on a 100 mm board: it is drawn on the canvas, becomes
  the footprint courtyard, and is the plate size used by the thermal analysis.
- Enter **min trace width**, **min spacing**, **copper weight** and a
  **target resistance**; the app picks the trace width that hits the target
  (never below the minimums) and fills the area with a single continuous trace
  from pad 1 to pad 2, routing around keepouts.
- The result shows trace width, length, resistance at 20 °C and at your
  operating temperature, coverage, an inductance estimate (partial-inductance
  sum over the segments — the meander cancels most of it, leaving a few µH) and
  any warnings; the *Parameters* tab plots R vs temperature from room
  temperature to the design temperature.
- **Export .kicad_mod**: copper `fp_line`s on F.Cu, SMD pads `1` and `2`,
  keepouts as rule areas, courtyard/fab outlines. Copy the file into a
  `.pretty` library folder (or *File ▸ Import ▸ Footprint* in the footprint editor).

## Run

```bash
./run          # Git Bash on Windows, macOS, or Linux
```

`run` is idempotent: the first time it creates `.venv/` and installs PySide6,
afterwards it just starts the app. If Python 3.10+ isn't installed it prints
install instructions.

```bash
./remove                 # delete the venv; asks whether to keep settings/logs
./remove --keep-data
./remove --remove-data
```

## Using the app

| Tool (shortcut) | What it does |
|---|---|
| Select / Pan (V) | click a keepout or pad to select, drag to move, `Delete` removes; drag empty space / middle mouse to pan; wheel zooms; `F` fits |
| Draw Heater (H) | drag the heater rectangle |
| Draw Keepout (K) | drag a keepout rectangle; stays active for more, `Esc` to stop |
| Place Pad A / B (A / B) | click to place an endpoint |

Everything can also be typed into the side panel. The trace regenerates
automatically after each edit (`Ctrl+G` forces it, needed for very large designs).

`File ▸ Save design` stores the whole design as JSON so it can be reopened later.

## Options / logging

The *Options* group has an **Enable logging** checkbox (on by default). The
log records tool changes, drawing/moving/deleting, parameter changes,
generation results, files opened/saved/exported, errors and crashes, so a bug
can be traced back to the actions that caused it. *Open log folder* shows where
it lives (`%LOCALAPPDATA%\HeaterApp\logs` on Windows,
`~/Library/Application Support/HeaterApp/logs` on macOS,
`~/.local/share/HeaterApp/logs` on Linux).

## How the trace is generated

The area is discretised into cells of pitch *width + space*. A shortest,
fewest-turn corridor is routed from pad A to pad B, the remaining free cells are
paired into dominoes (maximum bipartite matching), and dominoes/rings are
spliced into the corridor across 2×2 squares until one Hamiltonian path
remains. Coverage is 100 % except for cells forced out by checkerboard parity
(at most a handful), which are highlighted in yellow.

Resistance uses ρ<sub>Cu</sub> = 1.72 × 10⁻⁸ Ω·m, 34.79 µm per oz, and a
temperature coefficient of 0.393 %/°C.

## Analysis tab

Estimates whether the generated heater can reach the design temperature
(*Parameters > Design temperature*) with a constant-voltage, PWM'd-voltage or
constant-current supply, with the board lying flat (heater up) or standing
vertical, and the maximum temperature each combination settles at.

Inputs: supply voltage (CV/PWM), current set point and compliance voltage (CC),
ambient temperature, surface emissivity, board thickness and an optional extra
loss (W/K) for standoffs and wiring. The table shows T max, whether the design
temperature is reached (and by what margin), power needed vs. available (and
the PWM duty that holds the design temperature), current while holding
temperature and at switch-on, and a rough warm-up time. The loss breakdown
(convection / radiation / extra) is printed under the table.

The model is a lumped isothermal plate losing heat from both faces by natural
convection (flat-plate Nu-Ra correlations) and grey-body radiation, with the
heater resistance following copper's TCR; constant current turns into constant
voltage once the compliance limit is hit. The full list of assumptions is shown
in the tab itself. Treat it as a sizing guide (roughly +/-20 % on power).

## Tests

```bash
.venv/Scripts/python -m unittest discover -s tests      # Windows
.venv/bin/python -m unittest discover -s tests          # macOS / Linux
```
