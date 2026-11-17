# `bioscout.lab.record.screen_record`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/screen_record.py)

Screen recording utility with area selection, trimming, and preview capabilities.

## Contents

- class [`ScreenRecorder`](#screenrecorder) — Screen recording tool with interactive area selection and video trimming.
  - [`ScreenRecorder.run`](#screenrecorderrun) — Launch the screen recorder control panel.
  - [`ScreenRecorder.open_panel`](#screenrecorderopen_panel) — Launch the control panel as a Toplevel (when called from another Tk app).

<a id="screenrecorder"></a>

## class `ScreenRecorder`

```python
ScreenRecorder()
```

Screen recording tool with interactive area selection and video trimming.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/screen_record.py#L19)</sub>

<a id="screenrecorderrun"></a>

### `ScreenRecorder.run`

```python
ScreenRecorder.run()
```

Launch the screen recorder control panel.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/screen_record.py#L625)</sub>

<a id="screenrecorderopen_panel"></a>

### `ScreenRecorder.open_panel`

```python
ScreenRecorder.open_panel(parent=None)
```

| input | type | default |
|---|---|---|
| `parent` | – | `None` |

Launch the control panel as a Toplevel (when called from another Tk app).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/screen_record.py#L686)</sub>
