# jv-console

Browser tool for grouping and analysing LabVIEW solar-cell J(V) measurements.

Step one is grouping: the left pane is the measurement folder, the right pane is
what you have grouped. Everything downstream — the four parameter panels, the
J(V) overlay, the summary table, the exports — reads exactly the groups you built
and the pixels you left ticked.

No build step, no server, no upload. `index.html` is a single self-contained file;
`.dat` files are parsed in the browser and never leave the machine.

## Use it

Open `index.html` in Chrome or Edge, then **Import files…** or drag `.dat` files
onto the left pane.

## What it does

**Explorer 1 — the folder.** Every file is a tile with a J(V) thumbnail framed on
the power quadrant, its illumination class, and a shunt badge where a pixel is
flagged. Drag a box over empty space to rubber-band select; Ctrl/Shift-click to
add or extend; click a selected item again to unselect. Click a selected file's
name to rename it (display only — nothing on disk is touched). Expand a tile to
see pixels a–f with PCE, V_OC, J_SC and FF, each with a checkbox, all on by
default. `×` removes a file from the workspace; "put back" restores it.

**Explorer 2 — the groups.** Every file starts as its own group. Drag a selection
across to make a new group, or onto a card to join it; drag one card onto another
to merge. `×` removes a group and its files return to explorer 1. One file belongs
to exactly one group. Selection is shared between the panes — a card is filled
when all of its files are selected and carries a left bar when only some are.

**Results.** Four panels (J_SC, V_OC, FF, PCE) with jittered pixel points, a mean
line, SD whiskers and a mean diamond; groups are numbered on the axis with the key
drawn inside the figure. The J(V) overlay shows one curve per group — its
best-PCE pixel — labelled directly. The summary table gives the mean of each
parameter per group.

**Export.** Parameter plots and J(V) curves as PNG or SVG, the summary as CSV
carrying SD, min, max and n. Figures export on a white ground with the light
palette whatever theme you are viewing in.

## Repository layout

```
index.html                 built, self-contained, empty dataset
src/app.template.html      the source page; /*__DATA__*/ is the dataset slot
src/build.py               injects a dataset and writes index.html
tools/parse_dat.py         reference .dat parser (Python)
docs/labview-dat-format.md file format, parser rules, design decisions
```

## Building with data pre-loaded

Useful for a demo or for handing a fixed batch to someone. Keep the output out of
git — `.gitignore` already excludes `data.json`, `demo.html` and `*.dat`.

```bash
python3 tools/parse_dat.py /path/to/measurement_folder -o data.json
python3 src/build.py --data data.json -o demo.html
```

`src/build.py` with no arguments rebuilds the empty `index.html`.

## Two parsers, kept identical

`tools/parse_dat.py` is the reference; the page carries a JavaScript port so it
can read files with no Python installed. They were cross-checked over a 14-file
batch — 968 numeric fields, worst relative difference 0.00. Change one and change
the other, then re-check.

## What this is not, yet

The folder watcher and the live measurement screen are not built. The intended
shape is a small local Python process (polling watcher + FastAPI/WebSocket)
serving `/live` and `/stats` on localhost, polling the share rather than
subscribing to change notifications — see `docs/labview-dat-format.md`.
