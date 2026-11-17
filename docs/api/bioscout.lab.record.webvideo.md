# `bioscout.lab.record.webvideo`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/webvideo.py)

Make recorded videos playable in a web browser.

OpenCV's stock 'mp4v' fourcc writes MPEG-4 Part 2, which Chrome, Edge, Firefox  
and Safari all refuse to decode - so BioScout Web's "Analyse a video file"  
answered "Could not read that video" for everything the screen recorder saved.  
Browsers want H.264 (avc1) with yuv420p pixels, and the moov atom at the front.

`make_web_playable` rewrites a file in place to that format. It prefers ffmpeg  
(on PATH, or the binary bundled with `pip install imageio-ffmpeg`) and falls  
back to OpenCV's own H.264 writer (Media Foundation on Windows).

## Contents

- [`ffmpeg_exe`](#ffmpeg_exe) — Path to an ffmpeg binary, or None.
- [`fourcc_of`](#fourcc_of) — Lower-case fourcc of the first video stream ('' if unreadable).
- [`is_web_playable`](#is_web_playable) — 
- [`make_web_playable`](#make_web_playable) — Rewrite `path` in place as browser-playable H.264, muxing `wav_path` in if given. Returns True when the file at `path` is H.264 afterwards (audio is only muxed on the ffmpeg route).

### `ffmpeg_exe`

```python
ffmpeg_exe()
```

Path to an ffmpeg binary, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/webvideo.py#L23)</sub>

### `fourcc_of`

```python
fourcc_of(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Lower-case fourcc of the first video stream ('' if unreadable).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/webvideo.py#L35)</sub>

### `is_web_playable`

```python
is_web_playable(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/webvideo.py#L47)</sub>

### `make_web_playable`

```python
make_web_playable(path, wav_path=None)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `wav_path` | – | `None` |

Rewrite `path` in place as browser-playable H.264, muxing `wav_path` in  
if given. Returns True when the file at `path` is H.264 afterwards (audio  
is only muxed on the ffmpeg route).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/webvideo.py#L105)</sub>
