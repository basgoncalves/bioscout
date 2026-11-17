# `bioscout.devtools.settings_updater`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/settings_updater.py)

Migrate a project's settings.py to the current schema version.

Reads the project's existing settings.py, extracts user-customised values  
(PROJECT_ROOT, SUBJECTS, EMG mappings, DOF lists, model paths, …) and injects  
them into a fresh copy of the source (bioscout/settings.py) template, so the  
project gets all new fields while keeping every value the user had set.

  
**Public API**

    build_updated_settings(project_settings_path) -> str  
        Returns the text of the updated settings.py.

    write_updated_settings(project_settings_path) -> list[str]  
        Writes the file in-place (backs up the old one first) and returns a  
        list of human-readable lines describing what was preserved.

## Contents

- [`build_updated_settings`](#build_updated_settings) — Return (updated_text, preserved_descriptions).
- [`write_updated_settings`](#write_updated_settings) — Write updated settings.py in-place, backing up the original first.

### `build_updated_settings`

```python
build_updated_settings(project_settings_path: Path) -> tuple[str, list[str]]
```

| input | type | default |
|---|---|---|
| `project_settings_path` | Path | required |

**returns** `tuple[str, list[str]]`

Return (updated_text, preserved_descriptions).

updated_text            — full text of the new settings.py  
preserved_descriptions  — human-readable list of what was carried forward

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/settings_updater.py#L194)</sub>

### `write_updated_settings`

```python
write_updated_settings(project_settings_path: Path) -> list[str]
```

| input | type | default |
|---|---|---|
| `project_settings_path` | Path | required |

**returns** `list[str]`

Write updated settings.py in-place, backing up the original first.

Returns the list of preserved-value description lines.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/settings_updater.py#L228)</sub>
