# `bioscout.devtools.qrgen`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/qrgen.py)

Make a QR code for a link — ``bioscout utils qr_code``.

Interactive by default: asks for the link, then where to save. Uses ``segno``  
(pure Python, no Pillow needed for PNG/SVG); installs it with pip on first use.  
Each output is verified by checking the file was written and is non-empty.

## Contents

- [`make_qr`](#make_qr) — 

### `make_qr`

```python
make_qr(
    link: Optional[str] = None,
    out: Optional[str] = None,
    scale: int = 10,
    border: int = 4
) -> int
```

| input | type | default |
|---|---|---|
| `link` | Optional[str] | `None` |
| `out` | Optional[str] | `None` |
| `scale` | int | `10` |
| `border` | int | `4` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/qrgen.py#L30)</sub>
