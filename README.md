# jv-console

Browser tool for grouping and analysing LabVIEW solar-cell J(V) measurements.

Step one is grouping: the left pane is the measurement folder, the right pane is
what you have grouped. Everything downstream — the four parameter panels, the
J(V) overlay, the summary table, the exports — reads exactly the groups you built
and the pixels you left ticked.

No build step, no server, no upload. `index.html` is a single self-contained file;
`.dat` files are parsed in the browser and never leave the machine.

## Use it

Open `index.html` in Chrome or Edge, then either

- **Watch folder…** — pick the measurement folder once and leave it running, or
- **Import files…** / drag `.dat` files onto the left pane for a one-off look.

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

**Watching a folder.** Pick the folder and the page polls it every three seconds,
comparing each file's size and modification time and re-parsing only what moved. A
new file arrives as its own group, so the figure follows the run; a file that
changed is replaced in place, keeping its group and its name, and its tile carries
a `new` flag for fifteen seconds. A file caught mid-write parses to a shorter but
self-consistent sweep and completes on the next poll. The folder handle is kept in
IndexedDB, so reopening the page reconnects — Chrome asks you to confirm the
permission once, which is the *Reconnect* button. Chrome and Edge only: the File
System Access API does not exist in Firefox or Safari, and the button says so.

**Results.** The summary table leads, at mean ± SD with n pixels and substrates.
Below it one plate: panels a–d are box-and-whisker over every included pixel — box
the interquartile range, centre line the median, whiskers 1.5 × IQR, open symbol
the mean, points beyond the whiskers drawn open — and panel e overlays the
best-PCE pixel of each group. One key serves all five panels.

**Export.** The figure is drawn at final print size, in points: the plate 183 mm,
the parameters alone 120 mm, the J(V) panel alone 89 mm, Arial, 7 pt labels and
8 pt bold panel letters, which is Nature's figure specification. SVG carries its
width in millimetres, so placing it lands those point sizes literally; PNG rasters
at 600 dpi. The summary exports as CSV carrying SD, min, max and n.

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

There is no separate live measurement screen — watching the folder feeds the same
two panes, which so far has been enough. No local process is needed: the watcher
runs in the page, which is why there is still no server to start.

Over a network share, expect the poll to take longer than it does locally; the
watch bar reports how long each pass took, so the cost is visible rather than
guessed at.
