# LabVIEW JV `.dat` format — parser reference and design decisions

Verified against a 14-file batch (60 illuminated pixels), August 2026.
Both parsers in this repo implement exactly what follows.

## Physical file

| Property | Value |
|---|---|
| Encoding | ISO-8859-1 / cp1252 — **not** UTF-8 (the `cm²` superscripts break) |
| Line endings | CRLF |
| Separator | Tab |
| Length | **Not fixed** — it follows the voltage range and step |

## Block layout — parse by anchor token, never by line number

`Pixel` and `Voltage` each appear exactly once as a first-column token. Everything
is located relative to them.

| Position | Block | Content |
|---|---|---|
| head | Title | `Solar cell characteristics LabVIEW`, blank line |
| ↓ | Metadata | Compliance, stabilisation time, averages, intensity calibration factor, per-pixel contact areas, temperature |
| **anchor** | Pixel header | `Pixel` + one column per channel: `a_light … f_light`, `a_dark … f_dark`, `a_photo … f_photo` |
| between | Summary | `INT`, `V_OC`, `J_SC`, `FF`, `A`, `ECE`, `V_MMP`, `J_MMP` |
| **anchor** | Curve header | `Voltage` + `j_<pixel>_<mode>`, then a units row |
| to EOF | Sweep | Current density in mA/cm². Count, range, step and direction all read from column one |

Deriving the grid means a reverse sweep parses with no special case, and pairing a
forward and reverse file for hysteresis becomes possible later.

A substrate normally carries six pixels (`a`–`f`); a file may hold fewer when not
all were measured. The pixel set comes only from the header names; the interface
reserves six slots and shows gaps. `_photo` = light − dark. There is no timestamp
inside the file, so chronology comes from mtime.

## Parser traps — all of these occur in real data

1. **Column count varies.** 3, 7, 11 and 19 columns were all present in one
   folder. Map names from the `Pixel` row to indices; never index positionally.
2. **Headers lie about illumination.** Files named `*_dark.dat` label their
   columns `a_light … f_light` while INT reads ~5×10⁻⁶ mW/cm². Classify from the
   **INT row**: ≥ 10 light, ≥ 10⁻³ low-light, below that dark.
3. **Diagnostics sit beside real data.** Alignment and lock-in checks taken at
   ~0.02–0.04 mW/cm², and duplicate scans of a sample.
4. **A shunted pixel reads as valid numbers.** One pixel gave V_OC = 0.0106 V,
   FF = 0, PCE = 0 alongside a plausible J_SC of −4.2 mA/cm². Flag, never silently
   drop — the operator decides.
5. **LabVIEW overwrites the same file per pixel.** A file can legitimately parse
   with three of six pixels present and grow later, so a watcher must re-read on
   modify, not only on create.

## Intensity convention — verified

```
ECE = |J_SC| · V_OC · FF / INT      ratio 1.0001, within ±0.001 over 59 pixels
```

PCE is normalised to the **measured** intensity; `J_SC` is written **as
measured**. Over one batch the lamp ranged 93.65 → 104.30 mW/cm², so the
correction runs in both directions and the bias can exceed the pixel-to-pixel
scatter it hides in.

Correction for comparison: `J_SC(1 sun) = J_SC × 100 / INT`, applied to the whole
J(V) curve. Caveat: FF and V_OC stay at their measured-intensity values, so a
corrected PCE differs slightly from ECE — show both, never silently reconcile.

## Derived quantities

| Quantity | Method | Watch out for |
|---|---|---|
| R_s | Linear fit of dV/dJ over ±0.08 V around V_OC | Window must shrink for low-FF cells still bending at V_OC |
| R_sh | Linear fit of dV/dJ over ±0.15 V around V = 0 | Report as a lower bound when flat within noise |
| MPP | Parabolic interpolation of P(V) around the grid maximum | Removes the voltage-step quantisation in `V_MMP`; refitted FF differs slightly from the file's |
| QC flags | 0.5 ≤ V_OC ≤ 1.3 V; 1 ≤ \|J_SC\| ≤ 40 mA/cm²; 0.20 ≤ FF ≤ 0.90; 0.5 ≤ PCE ≤ 25 % | Flag only; inclusion stays the operator's choice |

Not implemented yet: the dark diode fit for ideality factor and J₀. It needs a
dark scan, and only some files carry dark columns.

## Interface decisions

Governing constraint: **do not build many utilities — keep deepening one until it
is obvious.**

- **Grouping is step one**, before any analysis. Groups are built by hand; there
  is no derived "group by".
- Every file starts as its own group, so opening the page and pressing nothing
  already plots every file individually.
- One file belongs to exactly one group. Explorer 1 always lists every file,
  marked when grouped.
- **Selection is one shared state living on files.** A group card's appearance is
  derived: filled when all its files are selected, a left bar when only some. The
  two panes cannot disagree by construction.
- Clicking a selected item again unselects it; clicking the *name* of a lone
  selection renames instead.
- Pixel checkboxes default to all on, including QC-flagged pixels.
- Groups are **numbered** in the figures, with the key drawn inside the SVG so an
  exported file is self-contained.
- The J(V) overlay plots **one curve per group — its best-PCE pixel**.
- Figures commit to a white ground with the light palette in both themes: it is
  what gets published, and no six-hue set clears the colourblind separation gate
  on a dark ground.

### Colour

The first six series use a set validated for all simultaneous pairs on a light
ground (normal-vision ΔE 15.6, CVD ΔE 6.9, relieved by direct axis labels and a
named key): blue `#2a78d6`, teal `#1baf7a`, gold `#eda100`, green `#008300`,
violet `#4a3aa7`, red `#e34948`. Past six the guarantee lapses and the page says
so under the figure.

## Roadmap — the watcher

Production data lives on a network share. The intended shape is a local Python
process serving `/live` and `/stats` on localhost:

- **Poll, don't subscribe.** Windows change notifications over SMB drop events,
  and a missed event on a rewrite means a pixel silently never appears. A ~1 s
  `os.scandir` comparing `(mtime_ns, size)` over one non-recursive folder costs
  almost nothing and never misses.
- Prefer the UNC path over a mapped drive letter, which is per-login-session.
- Debounce ~400 ms, retry on `PermissionError` and short reads; discard and
  re-read a file whose column count grew mid-read.
- Mirror each changed file to a local cache and parse the copy — free re-parsing,
  survives share dropouts, and gives a chronological archive.
- Show partial runs as partial (`3/6 pixels`) rather than reporting a three-pixel
  mean as a substrate result.
