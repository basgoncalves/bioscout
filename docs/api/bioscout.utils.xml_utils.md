# `bioscout.utils.xml_utils`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/xml_utils.py)

XML Utilities - Pretty printing and formatting XML files.  
Version: 1.0.0

## Contents

- [`indent`](#indent) — Add indentation to XML element tree for pretty printing.
- [`save_pretty_xml`](#save_pretty_xml) — Save XML ElementTree to file with proper formatting (indentation and newlines).

### `indent`

```python
indent(elem, level=0)
```

| input | type | default |
|---|---|---|
| `elem` | – | required |
| `level` | – | `0` |

Add indentation to XML element tree for pretty printing.

  
**Args**

    elem: ElementTree element  
    level: Current indentation level

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/xml_utils.py#L11)</sub>

### `save_pretty_xml`

```python
save_pretty_xml(xml_tree, file_path, encoding='utf-8', xml_declaration=True)
```

| input | type | default |
|---|---|---|
| `xml_tree` | – | required |
| `file_path` | – | required |
| `encoding` | – | `'utf-8'` |
| `xml_declaration` | – | `True` |

Save XML ElementTree to file with proper formatting (indentation and newlines).

  
**Args**

    xml_tree: ElementTree.ElementTree object or Element  
    file_path: Path to save XML file (str or Path)  
    encoding: Encoding for XML file (default: utf-8)  
    xml_declaration: Whether to include XML declaration (default: True)

  
**Returns**

    bool: True if successful, False otherwise

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/xml_utils.py#L34)</sub>
