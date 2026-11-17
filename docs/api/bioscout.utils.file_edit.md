# `bioscout.utils.file_edit`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py)

bioscout.utils.file_edit — one document model for every config file we edit.

BioScout's configuration is spread over three formats and the GUI had no way to  
touch any of them:

* **YAML** — ``session.yaml`` (the source of truth for a session),  
  ``config/default_config.yaml``, ``tps_personalise/data/config.yaml``  
* **XML**  — OpenSim setup files, ``GRF.xml``, markersets, CEINMS setup/config  
* **JSON** — ``load_credentials.json``, ``video_batch_settings.json``

This module is the format-agnostic layer the GUI editor sits on. Every format  
gets the same shape::

    doc = load_document(path)       # -> YamlDocument | XmlDocument | JsonDocument  
    doc.root                        # -> Node tree, for a treeview  
    doc.fields_for(node)            # -> [Field, ...], for a properties form  
    field.set("0.42")               # stage a change  
    doc.save()                      # atomic write, .bak kept



**Why YAML is not simply re-dumped**

``session.yaml`` carries load-bearing prose. The only record of why a trial was  
dropped is a comment::

    # Walking_02 REMOVED 2026-08-04 — do NOT re-enable. All 10 SO reserve  
    # actuators hit the 50 Nm cap in four of the six models...

``yaml.safe_dump`` deletes every one of those, reorders keys, expands flow maps  
and turns ``0.00`` into ``0.0``. So this module never re-dumps YAML. It composes  
the document with PyYAML to get the **exact character span of every scalar**,  
then edits the original text in place, replacing only the spans that changed.  
Everything else — comments, blank lines, key order, quoting, alignment, flow  
style, number formatting — is preserved byte-for-byte because it is never  
rewritten. A one-field change produces a one-token diff.

Nothing here imports a GUI toolkit, so it is testable headless.

## Contents

- class [`UnsupportedFormat`](#unsupportedformat) — The file's suffix maps to no structured editor.
- class [`Node`](#node) — One row in the structure tree (left pane).
  - [`Node.add`](#nodeadd) — 
  - [`Node.path`](#nodepath) — 
  - [`Node.path_str`](#nodepath_str) — 
- class [`Field`](#field) — One editable scalar in the properties form (right pane).
  - [`Field.set`](#fieldset) — Stage *raw* (display string, or bool from a checkbox) as this field's value.
- class [`Document`](#document) — Common behaviour: load, tree, form, atomic save with backup.
  - [`Document.dumps`](#documentdumps) — 
  - [`Document.build_tree`](#documentbuild_tree) — 
  - [`Document.fields_for`](#documentfields_for) — 
  - [`Document.validate_text`](#documentvalidate_text) — 
  - [`Document.load`](#documentload) — 
  - [`Document.reload`](#documentreload) — 
  - [`Document.mark_dirty`](#documentmark_dirty) — 
  - [`Document.dirty`](#documentdirty) — True when the in-memory document differs from the last load/save.
  - [`Document.revert`](#documentrevert) — Throw away every unsaved change.
  - [`Document.diff`](#documentdiff) — Unified diff of unsaved changes, for the Changes pane.
  - [`Document.raw_text`](#documentraw_text) — 
  - [`Document.save`](#documentsave) — Write the document. Atomic: temp file first, then ``os.replace``.
  - [`Document.choices_for`](#documentchoices_for) — Offer a combobox where a key behaves like an enumeration.
  - [`Document.help_for`](#documenthelp_for) — 
  - [`Document.problems`](#documentproblems) — Semantic checks beyond 'does it parse'.
- class [`YamlDocument`](#yamldocument) — 
  - [`YamlDocument.dumps`](#yamldocumentdumps) — Apply staged span edits to the original source, right-to-left.
  - [`YamlDocument.validate_text`](#yamldocumentvalidate_text) — 
  - [`YamlDocument.apply_staged`](#yamldocumentapply_staged) — Fold staged span edits into the working text and re-compose.
  - [`YamlDocument.build_tree`](#yamldocumentbuild_tree) — 
  - [`YamlDocument.fields_for`](#yamldocumentfields_for) — 
  - [`YamlDocument.map_node`](#yamldocumentmap_node) — The :class:`yaml.MappingNode` at ``keys``, or None.
  - [`YamlDocument.has_entry`](#yamldocumenthas_entry) — 
  - [`YamlDocument.set_entry_source`](#yamldocumentset_entry_source) — Replace ``key``'s VALUE with raw YAML *value_src* (add it if absent).
  - [`YamlDocument.ensure_mapping`](#yamldocumentensure_mapping) — Return the top-level mapping at *key*, creating ``key: {}`` if absent.
  - [`YamlDocument.entry_source`](#yamldocumententry_source) — The raw source lines of ``key`` within *map_node* (block style only).
  - [`YamlDocument.add_entry`](#yamldocumentadd_entry) — Append ``key: value_src`` to *map_node*, matching its indentation.
  - [`YamlDocument.duplicate_entry`](#yamldocumentduplicate_entry) — Copy ``key``'s source block under *new_key* — how you add a trial.
  - [`YamlDocument.replace_entry`](#yamldocumentreplace_entry) — Replace ``key``'s WHOLE entry — key line plus any block children — with a single ``key: value_src`` line at the key's indentation.
  - [`YamlDocument.delete_entry`](#yamldocumentdelete_entry) — Remove ``key`` from *map_node* (block style: whole lines).
  - [`YamlDocument.problems`](#yamldocumentproblems) — 
- class [`XmlDocument`](#xmldocument) — 
  - [`XmlDocument.dumps`](#xmldocumentdumps) — 
  - [`XmlDocument.validate_text`](#xmldocumentvalidate_text) — 
  - [`XmlDocument.build_tree`](#xmldocumentbuild_tree) — 
  - [`XmlDocument.fields_for`](#xmldocumentfields_for) — 
- class [`JsonDocument`](#jsondocument) — 
  - [`JsonDocument.dumps`](#jsondocumentdumps) — 
  - [`JsonDocument.validate_text`](#jsondocumentvalidate_text) — 
  - [`JsonDocument.build_tree`](#jsondocumentbuild_tree) — 
  - [`JsonDocument.fields_for`](#jsondocumentfields_for) — 
- [`describe_format`](#describe_format) — Return ``'yaml'`` / ``'xml'`` / ``'json'`` for *path*, else None.
- [`load_document`](#load_document) — Open *path* as a structured document.

<a id="unsupportedformat"></a>

## class `UnsupportedFormat`(Exception)

The file's suffix maps to no structured editor.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L60)</sub>

<a id="node"></a>

## class `Node`

One row in the structure tree (left pane).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L84)</sub>

<a id="nodeadd"></a>

### `Node.add`

```python
Node.add(child: 'Node') -> 'Node'
```

| input | type | default |
|---|---|---|
| `child` | 'Node' | required |

**returns** `'Node'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L94)</sub>

<a id="nodepath"></a>

### `Node.path`

```python
Node.path() -> Tuple[Any, ...]
```

**returns** `Tuple[Any, ...]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L99)</sub>

<a id="nodepath_str"></a>

### `Node.path_str`

```python
Node.path_str() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L106)</sub>

<a id="field"></a>

## class `Field`

One editable scalar in the properties form (right pane).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L111)</sub>

<a id="fieldset"></a>

### `Field.set`

```python
Field.set(raw) -> None
```

| input | type | default |
|---|---|---|
| `raw` | – | required |

**returns** `None`

Stage *raw* (display string, or bool from a checkbox) as this field's value.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L122)</sub>

<a id="document"></a>

## class `Document`

```python
Document(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Common behaviour: load, tree, form, atomic save with backup.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L209)</sub>

<a id="documentdumps"></a>

### `Document.dumps`

```python
Document.dumps() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L228)</sub>

<a id="documentbuild_tree"></a>

### `Document.build_tree`

```python
Document.build_tree() -> Node
```

**returns** `Node`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L231)</sub>

<a id="documentfields_for"></a>

### `Document.fields_for`

```python
Document.fields_for(node: Node) -> List[Field]
```

| input | type | default |
|---|---|---|
| `node` | Node | required |

**returns** `List[Field]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L234)</sub>

<a id="documentvalidate_text"></a>

### `Document.validate_text`

```python
Document.validate_text(text: str) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `text` | str | required |

**returns** `Optional[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L237)</sub>

<a id="documentload"></a>

### `Document.load`

```python
Document.load() -> 'Document'
```

**returns** `'Document'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L241)</sub>

<a id="documentreload"></a>

### `Document.reload`

```python
Document.reload() -> 'Document'
```

**returns** `'Document'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L253)</sub>

<a id="documentmark_dirty"></a>

### `Document.mark_dirty`

```python
Document.mark_dirty() -> None
```

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L256)</sub>

<a id="documentdirty"></a>

### `Document.dirty`

```python
Document.dirty() -> bool
```

**returns** `bool`

True when the in-memory document differs from the last load/save.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L260)</sub>

<a id="documentrevert"></a>

### `Document.revert`

```python
Document.revert() -> None
```

**returns** `None`

Throw away every unsaved change.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L267)</sub>

<a id="documentdiff"></a>

### `Document.diff`

```python
Document.diff() -> str
```

**returns** `str`

Unified diff of unsaved changes, for the Changes pane.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L272)</sub>

<a id="documentraw_text"></a>

### `Document.raw_text`

```python
Document.raw_text() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L287)</sub>

<a id="documentsave"></a>

### `Document.save`

```python
Document.save(path=None, backup: bool = True, text: Optional[str] = None) -> Path
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |
| `backup` | bool | `True` |
| `text` | Optional[str] | `None` |

**returns** `Path`

Write the document. Atomic: temp file first, then ``os.replace``.

An exception mid-write leaves the original intact rather than half a  
file, which the pipeline would read happily and then fail on somewhere  
unrelated.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L290)</sub>

<a id="documentchoices_for"></a>

### `Document.choices_for`

```python
Document.choices_for(key, value=None) -> Sequence[str]
```

| input | type | default |
|---|---|---|
| `key` | – | required |
| `value` | – | `None` |

**returns** `Sequence[str]`

Offer a combobox where a key behaves like an enumeration.

A key taking a handful of distinct values across the file (``side``:  
left/right/both) is an enum in practice, and a free-text box is where a  
typo silently becomes a new category.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L320)</sub>

<a id="documenthelp_for"></a>

### `Document.help_for`

```python
Document.help_for(key) -> str
```

| input | type | default |
|---|---|---|
| `key` | – | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L339)</sub>

<a id="documentproblems"></a>

### `Document.problems`

```python
Document.problems() -> List[str]
```

**returns** `List[str]`

Semantic checks beyond 'does it parse'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L342)</sub>

<a id="yamldocument"></a>

## class `YamlDocument`(Document)

```python
YamlDocument(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L350)</sub>

<a id="yamldocumentdumps"></a>

### `YamlDocument.dumps`

```python
YamlDocument.dumps() -> str
```

**returns** `str`

Apply staged span edits to the original source, right-to-left.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L369)</sub>

<a id="yamldocumentvalidate_text"></a>

### `YamlDocument.validate_text`

```python
YamlDocument.validate_text(text: str) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `text` | str | required |

**returns** `Optional[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L378)</sub>

<a id="yamldocumentapply_staged"></a>

### `YamlDocument.apply_staged`

```python
YamlDocument.apply_staged() -> None
```

**returns** `None`

Fold staged span edits into the working text and re-compose.

Structural edits (add/duplicate/delete) shift every span after them, so  
the node marks must be recomputed before the next edit is staged —  
otherwise the second edit patches the wrong characters.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L385)</sub>

<a id="yamldocumentbuild_tree"></a>

### `YamlDocument.build_tree`

```python
YamlDocument.build_tree() -> Node
```

**returns** `Node`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L414)</sub>

<a id="yamldocumentfields_for"></a>

### `YamlDocument.fields_for`

```python
YamlDocument.fields_for(node: Node) -> List[Field]
```

| input | type | default |
|---|---|---|
| `node` | Node | required |

**returns** `List[Field]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L451)</sub>

<a id="yamldocumentmap_node"></a>

### `YamlDocument.map_node`

```python
YamlDocument.map_node(*keys)
```

| input | type | default |
|---|---|---|
| `*keys` | – | – |

The :class:`yaml.MappingNode` at ``keys``, or None.

Lets callers outside the GUI (e.g. the Trial Analysis tab) patch one  
block of a session.yaml without walking the node tree themselves.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L567)</sub>

<a id="yamldocumenthas_entry"></a>

### `YamlDocument.has_entry`

```python
YamlDocument.has_entry(map_node, key) -> bool
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | – | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L582)</sub>

<a id="yamldocumentset_entry_source"></a>

### `YamlDocument.set_entry_source`

```python
YamlDocument.set_entry_source(map_node, key, value_src: str) -> None
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | – | required |
| `value_src` | str | required |

**returns** `None`

Replace ``key``'s VALUE with raw YAML *value_src* (add it if absent).

Only the value span is touched, so a trailing ``# comment`` on that  
line — and every other line in the file — is left alone.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L585)</sub>

<a id="yamldocumentensure_mapping"></a>

### `YamlDocument.ensure_mapping`

```python
YamlDocument.ensure_mapping(key: str)
```

| input | type | default |
|---|---|---|
| `key` | str | required |

Return the top-level mapping at *key*, creating ``key: {}`` if absent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L599)</sub>

<a id="yamldocumententry_source"></a>

### `YamlDocument.entry_source`

```python
YamlDocument.entry_source(map_node, key) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | – | required |

**returns** `Optional[str]`

The raw source lines of ``key`` within *map_node* (block style only).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L653)</sub>

<a id="yamldocumentadd_entry"></a>

### `YamlDocument.add_entry`

```python
YamlDocument.add_entry(map_node, key: str, value_src: str = '{}') -> None
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | str | required |
| `value_src` | str | `'{}'` |

**returns** `None`

Append ``key: value_src`` to *map_node*, matching its indentation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L667)</sub>

<a id="yamldocumentduplicate_entry"></a>

### `YamlDocument.duplicate_entry`

```python
YamlDocument.duplicate_entry(map_node, key, new_key: str) -> None
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | – | required |
| `new_key` | str | required |

**returns** `None`

Copy ``key``'s source block under *new_key* — how you add a trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L687)</sub>

<a id="yamldocumentreplace_entry"></a>

### `YamlDocument.replace_entry`

```python
YamlDocument.replace_entry(map_node, key, value_src: str) -> None
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | – | required |
| `value_src` | str | required |

**returns** `None`

Replace ``key``'s WHOLE entry — key line plus any block children —  
with a single ``key: value_src`` line at the key's indentation.

This is the safe way to change a value that IS or WAS a block  
sequence/mapping: ``set_entry_source`` patches only the value span,  
which for block values glues the replacement onto the next key's line.  
Adds the entry when absent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L702)</sub>

<a id="yamldocumentdelete_entry"></a>

### `YamlDocument.delete_entry`

```python
YamlDocument.delete_entry(map_node, key) -> None
```

| input | type | default |
|---|---|---|
| `map_node` | – | required |
| `key` | – | required |

**returns** `None`

Remove ``key`` from *map_node* (block style: whole lines).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L723)</sub>

<a id="yamldocumentproblems"></a>

### `YamlDocument.problems`

```python
YamlDocument.problems() -> List[str]
```

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L738)</sub>

<a id="xmldocument"></a>

## class `XmlDocument`(Document)

```python
XmlDocument(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L807)</sub>

<a id="xmldocumentdumps"></a>

### `XmlDocument.dumps`

```python
XmlDocument.dumps() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L828)</sub>

<a id="xmldocumentvalidate_text"></a>

### `XmlDocument.validate_text`

```python
XmlDocument.validate_text(text: str) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `text` | str | required |

**returns** `Optional[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L841)</sub>

<a id="xmldocumentbuild_tree"></a>

### `XmlDocument.build_tree`

```python
XmlDocument.build_tree() -> Node
```

**returns** `Node`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L860)</sub>

<a id="xmldocumentfields_for"></a>

### `XmlDocument.fields_for`

```python
XmlDocument.fields_for(node: Node) -> List[Field]
```

| input | type | default |
|---|---|---|
| `node` | Node | required |

**returns** `List[Field]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L879)</sub>

<a id="jsondocument"></a>

## class `JsonDocument`(Document)

```python
JsonDocument(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L922)</sub>

<a id="jsondocumentdumps"></a>

### `JsonDocument.dumps`

```python
JsonDocument.dumps() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L933)</sub>

<a id="jsondocumentvalidate_text"></a>

### `JsonDocument.validate_text`

```python
JsonDocument.validate_text(text: str) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `text` | str | required |

**returns** `Optional[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L936)</sub>

<a id="jsondocumentbuild_tree"></a>

### `JsonDocument.build_tree`

```python
JsonDocument.build_tree() -> Node
```

**returns** `Node`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L959)</sub>

<a id="jsondocumentfields_for"></a>

### `JsonDocument.fields_for`

```python
JsonDocument.fields_for(node: Node) -> List[Field]
```

| input | type | default |
|---|---|---|
| `node` | Node | required |

**returns** `List[Field]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L985)</sub>

### `describe_format`

```python
describe_format(path) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Optional[str]`

Return ``'yaml'`` / ``'xml'`` / ``'json'`` for *path*, else None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L75)</sub>

### `load_document`

```python
load_document(path) -> Document
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Document`

Open *path* as a structured document.

Raises :class:`UnsupportedFormat` for a suffix with no editor — the GUI  
catches that and falls back to plain-text editing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/file_edit.py#L1110)</sub>
