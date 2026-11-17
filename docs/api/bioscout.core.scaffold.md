# `bioscout.core.scaffold`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/scaffold.py)

Create a BioScout project folder -- `bioscout init`, and `Project(path)` on a new folder.

## Contents

- [`scaffold_project`](#scaffold_project) — Initialise a new BioScout project at *project_path*.
- [`write_template_subject`](#write_template_subject) — simulations/_template/session_01/: the bundled example session (OrthoLoad H1L -- static + level walking with measured hip contact force, see its SOURCE.md) with an empty 1_c3dfiles/. Never overwrites a file.

### `scaffold_project`

```python
scaffold_project(project_path, force: bool = False) -> int
```

| input | type | default |
|---|---|---|
| `project_path` | – | required |
| `force` | bool | `False` |

**returns** `int`

Initialise a new BioScout project at *project_path*.

  
**Actions**

1. Create standard subdirectories (simulations/, models/, setup_files/,  
   logs/, results/).  
2. Copy bundled setup_files templates (XML) into <project>/setup_files/ —  
   skips files that already exist so re-running is safe.  
3. Write a starter project.yaml (skipped if one already exists). A new  
   project needs no settings.py: it runs on bioscout's bundled defaults  
   until project.yaml declares a lab fact that differs  
   (docs/IMPLEMENTATIONS.md §2.9, step 4 — this used to copy the old  
   all-in-one settings.py template in here instead; that copy is retired  
   for new projects). Migrating an EXISTING project off its own  
   settings.py is still `bioscout init --from-settings`, which extracts a  
   project.yaml FROM it.  
4. If simulations/ already contains participant sub-folders, list them —  
   bioscout discovers subjects from simulations/ automatically, no  
   SUBJECTS list to maintain.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/scaffold.py#L11)</sub>

### `write_template_subject`

```python
write_template_subject(project) -> Path
```

| input | type | default |
|---|---|---|
| `project` | – | required |

**returns** `Path`

simulations/_template/session_01/: the bundled example session (OrthoLoad  
H1L -- static + level walking with measured hip contact force, see its  
SOURCE.md) with an empty 1_c3dfiles/. Never overwrites a file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/scaffold.py#L181)</sub>
