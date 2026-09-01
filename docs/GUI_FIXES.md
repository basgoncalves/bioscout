# GUI fixes — 2026-08-25

Run `🔄 Reload App` (or Ctrl+R) once after updating. Backups of every touched
file are next to them as `*.py.bak_gui`.

---

## 1. The ⚠ next to the project path

**Cause.** `_load_project()` only ever looked at `<project>/settings.py`.
The Powerlifting project keeps it at `code/settings.py`, so the check found
nothing and reported "No settings.py" forever. The reason only appeared in the
sidebar status label for a few seconds, so the icon itself was a dead end.

**Fix** (`gui/main_window.py`)

* `_find_project_settings()` now looks in `settings.py`, `code/settings.py`,
  `scripts/settings.py`, `src/settings.py` — first hit wins. `_guess_project_dir()`
  and `↑ Update Settings` use the same list.
* The ⚠ / ✓ icon is now **hoverable and clickable**: it shows the exact check
  that failed, the project path, and which `settings.py` was used.

Your project should now show `✓ settings v2.0.0b1` (it matches the source).

## 2. "Update Markers" → "⟳ Load Channels"

`gui/widgets/batch_c3d_export.py`. Renamed, made bigger (140×28, 12 pt bold),
and the preview placeholder text follows. Same command — it reads the ticked
C3D and fills in the EMG channel list (markers come along with it).

## 3. Font rescaling

Two real bugs, both fixed in `gui/gui_settings.py`:

* **The window jumped / un-maximised.** `apply_appearance()` called
  `set_window_scaling()` on a live window; CTk then re-applies geometry through
  deferred callbacks. There is now `apply_appearance(live=True)` for mid-session
  changes — widget scaling only. Window scaling is set once, before the window exists.
* **Console and tables stayed small.** Plain-tk widgets ignore CTk scaling and
  took `font_size()` at creation only. New `register_tk_font(widget, family, base)`
  keeps them in a registry; `refresh_tk_fonts()` re-fonts them on every scale
  change. Applied to the console output and the Max-EMG table.

Result: the slider now takes effect everywhere immediately. "Apply cleanly
(reload)" is only needed if a panel ends up mid-layout.

## 4. Button text too small

~120 buttons were written with `font=("Segoe UI", 7…9)`. Instead of editing each
one, `CTkButton.__init__` is patched once (`_patch_button_fonts`) to raise any
button font below `MIN_BUTTON_FONT = 11`. Buttons only — labels and entries are
free to stay small.

## 5. Base colour in Settings

`ui.accent`, default `blue`. Seven swatches in Settings → Appearance:
blue, teal, green, purple, orange, red, grey. Chosen swatch gets a white border.

customtkinter reads colours when a widget is **created**, so a change applies to
the whole app after a reload — the status line says so rather than pretending.
Ships only blue/green/dark-blue itself; `_apply_accent()` patches
`ThemeManager.theme` directly so any hex works.

Add your own in `ACCENTS` in `gui_settings.py`: `"name": ("#fg", "#hover")`.

## 6. C3D Export layout

| what | before | after |
|---|---|---|
| Files ‖ Settings columns | 3 : 7 | 1 : 8 (files `minsize=190`) |
| EMG ‖ Markers columns | 3 : 2 | 5 : 1 (markers `minsize=230`) |
| Channels ‖ Preview | channels `minsize=210` | channels 175, preview `minsize=430` |
| preview row weight | 3 (vs 2 for Max EMG) | 6 (vs 1) |
| Left/Right marker lists | fill | `width=105` each |
| C3D file list | fill | `width=175` |

**Progress bar removed.** It duplicated what the console already prints, and the
console says *which* file. What is left is one status line. `self.progress_bar`
is now a `_NullBar` no-op so the export thread's `.set()` calls still work, and
every `progress_label` message goes through `_progress()` → console + log +
status bar.

## 7. 120 % is the new 100 %

`BASE_SCALE = 1.2` in `gui_settings.py`. Effective scale = `ui.scale × BASE_SCALE`,
so the Settings tab keeps saying 100 % while the app is drawn at the size you
were actually running.

* One-time migration (`_rebase`): a stored `1.2` becomes `1.0`, flagged by
  `ui.scale_rebased` so it runs once. Nothing to do by hand.
* Quick sizes rebased: 85 / 92 / **100** / 115 / 130 %
  (old 100 % ≈ new 83 %, old 140 % ≈ new 117 %).

---

## Files changed

```
bioscout/gui/gui_settings.py            BASE_SCALE, ACCENTS, live apply, tk-font registry, button patch
bioscout/gui/main_window.py             settings.py lookup, ⚠ tooltip, accent-safe theme
bioscout/gui/widgets/settings_tab.py    accent swatches, rebased quick sizes, live apply
bioscout/gui/widgets/batch_c3d_export.py  Load Channels, layout weights, no progress bar
bioscout/gui/widgets/console_terminal.py  console follows the UI scale
```

## Revert

```bash
cd /path/to/bioscout
for f in bioscout/gui/gui_settings.py bioscout/gui/main_window.py \
         bioscout/gui/widgets/settings_tab.py \
         bioscout/gui/widgets/batch_c3d_export.py; do cp "$f.bak_gui" "$f"; done
```

(`console_terminal.py` has no backup — `git checkout` it.)

---

# Round 2 — 2026-08-25

## 8. Preview plot was still cramped

The plot had ~200 px of height under ~110 px of settings chrome. Reshuffled
`gui/widgets/batch_c3d_export.py`:

* **Label+Search and Low/High/Notch are now ONE bar** (`emg_col` row 1). They
  were two stacked frames, each with its own heading row and its own
  label-above-value pairs. Everything on it is a short numeric field, so it
  fits on one line: `Label [____] [Search]  Band (Hz) [10]–[500]  Notch [50]  FPS: 1000`.
  Row 2 is now free.
* **Preview row weight 6 → 10**, and `minsize=300` so it cannot be squeezed
  below a usable height by whatever is under it.
* **Max-EMG table 8 → 5 lines.** It scrolls in both directions anyway; the two
  extra fixed lines were coming straight out of the plot.
* **Per-muscle scale list 110 → 84 px** (it reserves that height even hidden).

Net: roughly 130 px moved from chrome into the plot.

## 9. Destination folder now follows the session layout

A session is `<session>/1_c3dfiles`, `2_experimental`, `3_iterations`. The old
default was "same folder as the source", which exported the trials back into
`1_c3dfiles` — mixing outputs into the one folder the next stage globs for raw
C3Ds.

`_default_dest_for(source)` now returns, in order:

1. a sibling `2_experimental` / `experimental` (source is `…/1_c3dfiles`)
2. a child of the same names (source *is* the session folder)
3. any `*experimental*` folder in either place
4. `None` → falls back to the source folder, as before

It **only ever returns a folder that already exists** — inventing and creating
one would scatter half-sessions across the project.

It fires when you browse/type a source, and from `set_session_dir()` (which now
also points the source at `1_c3dfiles` rather than the session root).

**It never overwrites a destination you chose.** The box is replaced only when
it is empty, still equal to the source, or still equal to the last path the tab
auto-filled (remembered as `c3d_export.auto_dest`). Comparison is by resolved
`Path`, not string — the two boxes disagree on slash direction, and string
equality was reporting a self-filled path as user-chosen. `_restore_ui_state()`
restores the destination *before* the source for the same reason.
