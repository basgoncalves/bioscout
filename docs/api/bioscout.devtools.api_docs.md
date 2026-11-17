# `bioscout.devtools.api_docs`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py)

Build the browsable API reference in docs/api/ (GitHub-rendered Markdown).

    python -m bioscout.devtools.api_docs

Reads the source with ``ast`` -- nothing is imported, so it runs without  
OpenSim, CEINMS or a display. For every public module it writes one page:  
the module summary, a clickable list of its functions and classes, and for  
each one the call signature, an inputs table (name, type, default), the  
return type, the docstring and a link to the source line on GitHub.  
docs/api/index.md lists every module, grouped by package.

## Contents

- [`modules`](#modules) — 
- [`first_line`](#first_line) — 
- [`anchor`](#anchor) — 
- [`ann`](#ann) — 
- [`args_table`](#args_table) — 
- [`signature`](#signature) — 
- [`esc_cell`](#esc_cell) — 
- [`doc_md`](#doc_md) — Docstring -> Markdown: section headings (numpy / Google style) in bold, the rest kept as written.
- [`member_md`](#member_md) — 
- [`page`](#page) — 
- [`main`](#main) — 

### `modules`

```python
modules()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L27)</sub>

### `first_line`

```python
first_line(doc)
```

| input | type | default |
|---|---|---|
| `doc` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L37)</sub>

### `anchor`

```python
anchor(s)
```

| input | type | default |
|---|---|---|
| `s` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L41)</sub>

### `ann`

```python
ann(node)
```

| input | type | default |
|---|---|---|
| `node` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L45)</sub>

### `args_table`

```python
args_table(fn, skip_self)
```

| input | type | default |
|---|---|---|
| `fn` | – | required |
| `skip_self` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L49)</sub>

### `signature`

```python
signature(name, fn, skip_self)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `fn` | – | required |
| `skip_self` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L67)</sub>

### `esc_cell`

```python
esc_cell(s)
```

| input | type | default |
|---|---|---|
| `s` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L79)</sub>

### `doc_md`

```python
doc_md(doc)
```

| input | type | default |
|---|---|---|
| `doc` | – | required |

Docstring -> Markdown: section headings (numpy / Google style) in bold, the rest kept as written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L83)</sub>

### `member_md`

```python
member_md(name, node, path, skip_self=False, level=3, prefix='')
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `node` | – | required |
| `path` | – | required |
| `skip_self` | – | `False` |
| `level` | – | `3` |
| `prefix` | – | `''` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L104)</sub>

### `page`

```python
page(name, path)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L118)</sub>

### `main`

```python
main()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/api_docs.py#L188)</sub>
