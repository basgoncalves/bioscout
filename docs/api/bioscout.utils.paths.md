# `bioscout.utils.paths`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/paths.py)

Path helpers for the setup files bioscout writes.

OpenSim resolves a relative path in a setup XML against the setup file's own  
directory, so a setup that names its inputs relatively is portable: move the  
session folder, put it on a colleague's machine, open it in the OpenSim GUI --  
it still resolves. A setup full of ``C:\Users\<you>\...`` only ever works on  
one machine, and silently stops working when the project moves.

Every tool that writes a setup should therefore run :func:`relativise_xml` over  
it before handing it back. Two rules make that safe to do blindly:

* a path that CANNOT be made relative (a different drive on Windows, a UNC  
  share) is left absolute rather than mangled -- ``os.path.relpath`` raises  
  ``ValueError`` across drives, and a wrong relative path is worse than an  
  honest absolute one;  
* only values that actually look like absolute paths are touched, so numbers,  
  names and flags in the same file are never rewritten.

    from bioscout.utils.paths import relativise_xml, to_relative

    relativise_xml("scale_setup.xml")            # in place, against its own dir  
    to_relative("C:/proj/s1/x.trc", "C:/proj")   # -> "s1/x.trc"

Standard library only.

## Contents

- [`looks_absolute`](#looks_absolute) — True when ``text`` looks like an absolute path.
- [`path_root`](#path_root) — The root ``text`` hangs off: ``"c:"``, ``"//server/share"``, ``"/"``, or "".
- [`to_relative`](#to_relative) — ``path`` relative to ``base``, or ``path`` unchanged if that is impossible.
- [`relativise_value`](#relativise_value) — Relativise one XML value: a single path, or a space-separated list.
- [`relativise_xml`](#relativise_xml) — Rewrite absolute paths in an OpenSim/CEINMS setup XML to relative ones.

### `looks_absolute`

```python
looks_absolute(text)
```

| input | type | default |
|---|---|---|
| `text` | – | required |

True when ``text`` looks like an absolute path.

Drive-letter (``C:\x``, ``C:/x``), UNC (``\\server\share``) or  
POSIX-absolute (``/x``). Deliberately textual: the path need not exist, and  
a Windows path is recognised while running on Linux (that is the normal  
case when inspecting someone else's setup file).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/paths.py#L38)</sub>

### `path_root`

```python
path_root(text)
```

| input | type | default |
|---|---|---|
| `text` | – | required |

The root ``text`` hangs off: ``"c:"``, ``"//server/share"``, ``"/"``, or "".

Used to decide whether two paths CAN be relative to each other. Textual on  
purpose: ``os.path.relpath`` only raises across drives when it is running  
on Windows -- on Linux it happily returns ``../D:\models\x.osim`` for two  
different Windows drives, which is nonsense that would then be written  
into a setup file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/paths.py#L52)</sub>

### `to_relative`

```python
to_relative(path, base, sep=None)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `base` | – | required |
| `sep` | – | `None` |

``path`` relative to ``base``, or ``path`` unchanged if that is impossible.

  
**Args**

    path: the path to rewrite.  
    base: the directory to make it relative to (a setup file's folder).  
    sep: separator for the result. ``None`` keeps whatever ``os.path``  
        produces; pass ``"/"`` for forward slashes (OpenSim accepts them on  
        every platform) or ``"\\"`` for Windows-style.

A different drive or a UNC share has no relative form, so the absolute path  
is returned as-is -- correct, if not portable.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/paths.py#L72)</sub>

### `relativise_value`

```python
relativise_value(text, base, sep=None)
```

| input | type | default |
|---|---|---|
| `text` | – | required |
| `base` | – | required |
| `sep` | – | `None` |

Relativise one XML value: a single path, or a space-separated list.

Returns ``(new_text, changed)``. A single path that CONTAINS spaces is  
handled before the list case, so ``C:\Digital Athlete\x.osim`` is  
rewritten rather than shredded into fragments -- the bug that made the  
older per-tool copy of this silently skip any path with a space in it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/paths.py#L100)</sub>

### `relativise_xml`

```python
relativise_xml(xml_path, base=None, sep='/')
```

| input | type | default |
|---|---|---|
| `xml_path` | – | required |
| `base` | – | `None` |
| `sep` | – | `'/'` |

Rewrite absolute paths in an OpenSim/CEINMS setup XML to relative ones.

In place, best-effort: a file that will not parse is left alone rather than  
truncated. Returns the number of values rewritten (0 when nothing needed  
it, or on failure), so a caller can report honestly.

``base`` defaults to the XML's own directory, which is what OpenSim  
resolves against.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/paths.py#L124)</sub>
