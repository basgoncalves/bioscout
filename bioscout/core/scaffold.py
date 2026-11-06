"""Create a BioScout project folder -- ``bioscout init`` and ``Project.init``."""
from __future__ import annotations

from pathlib import Path

__all__ = ["scaffold_project"]

_PKG = Path(__file__).resolve().parents[1]      # the bioscout package (templates live here)


def scaffold_project(project_path, force: bool = False) -> int:
    """Initialise a new BioScout project at *project_path*.

    Actions
    -------
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
    """
    import shutil

    project = Path(project_path).resolve()
    standard_dirs = ['simulations', 'models', 'setup_files', 'logs', 'results']

    # Refuse to scaffold over folders that are not ours. A first init (no
    # project.yaml yet) into a folder that already has a non-empty models/,
    # setup_files/, ... would mix bioscout's ~100 template files into the
    # user's own. Re-running init on an existing bioscout project stays safe.
    if not (project / 'project.yaml').exists() and not force:
        clash = [d for d in standard_dirs
                 if (project / d).is_dir() and any((project / d).iterdir())]
        if clash:
            print(f"\n[init] ERROR: {project} is not a bioscout project yet, "
                  f"but these folders already exist and are not empty:")
            for d in clash:
                print(f"         {project / d}")
            print("       Nothing was created. Either:")
            print("         - rename/move them (e.g. models -> models_old) and run "
                  "`bioscout init` again, or")
            print("         - init into a new empty folder: `bioscout init <new_folder>`, or")
            print("         - `bioscout init --force` to add bioscout's files alongside "
                  "(existing files are never overwritten).")
            return 1

    print(f"\n{'='*60}")
    print(f"BioScout — Initialising project at: {project}")
    print(f"{'='*60}")

    # ---------------------------------------------------------------------- #
    # 1. Create standard folder structure
    # ---------------------------------------------------------------------- #
    for d in standard_dirs:
        target = project / d
        if not target.exists():
            target.mkdir(parents=True)
            print(f"  [created]  {target}")
        else:
            print(f"  [exists]   {target}")

    # ---------------------------------------------------------------------- #
    # 2. Copy bundled templates (setup_files and models)
    # ---------------------------------------------------------------------- #
    def _copy_template_dir(src: Path, dst: Path, extensions: tuple) -> tuple:
        """Copy files matching *extensions* from src → dst, skipping existing.
        Returns (copied_count, skipped_count).
        """
        if not src.exists():
            return 0, 0
        copied, skipped = 0, 0
        for item in sorted(src.rglob('*')):
            if '__pycache__' in item.parts:
                continue
            if item.is_file() and (not extensions or item.suffix in extensions):
                rel = item.relative_to(src)
                target = dst / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    skipped += 1
                else:
                    shutil.copy2(item, target)
                    copied += 1
        return copied, skipped

    for tmpl_name, dst_name, exts in [
        ('setup_files', 'setup_files', ('.xml', '.txt')),
        # models: the user's models + meshes only. bioscout/models is also a
        # Python package (force_model.py, *.pkl, __pycache__) — none of that
        # belongs in a project.
        ('models',      'models',      ('.osim', '.vtp', '.stl', '.obj', '.json', '.txt')),
    ]:
        src_dir = _PKG / tmpl_name
        dst_dir = project / dst_name
        c, s = _copy_template_dir(src_dir, dst_dir, exts)
        label = f"  [{dst_name}]"
        if c:
            print(f"\n{label} {c} file(s) copied to {dst_dir}")
        if s:
            print(f"{label} {s} file(s) already existed — not overwritten")
        if not c and not s:
            print(f"\n{label} No bundled templates found at {src_dir}")

    # ---------------------------------------------------------------------- #
    # 3. Write a starter project.yaml (replaces the old settings.py copy —
    #    docs/IMPLEMENTATIONS.md §2.9, step 4)
    # ---------------------------------------------------------------------- #
    yaml_dest = project / 'project.yaml'

    if yaml_dest.exists():
        print(f"\n  [skip] project.yaml already exists — not overwriting.")
        print(f"         Edit it directly: {yaml_dest}")
    else:
        yaml_dest.write_text(
            "# project.yaml — lab facts that differ from bioscout's bundled\n"
            "# defaults. No code, no run selection. Add `batch:` / `ceinms:`\n"
            "# entries only for what actually differs — everything else is\n"
            "# inherited (docs/IMPLEMENTATIONS.md §2.9). Migrating an\n"
            "# existing project off its own settings.py? Use\n"
            "# `bioscout init --from-settings` to extract one from it instead of\n"
            "# hand-writing this.\n"
            f"schema: 1\n"
            f"name: {project.name}\n",
            encoding='utf-8',
        )
        print(f"\n  [created]  {yaml_dest}")
        print(f"  This project needs no settings.py — it runs on bioscout's "
              f"bundled defaults until project.yaml says otherwise.")

    # ---------------------------------------------------------------------- #
    # 4. List existing simulation folders, if any
    # ---------------------------------------------------------------------- #
    sims_dir = project / 'simulations'
    if sims_dir.exists():
        sim_folders = sorted(
            d.name for d in sims_dir.iterdir() if d.is_dir()
        )
        if sim_folders:
            print(f"\n  Simulation folders found: {sim_folders}")
            print(f"  bioscout discovers subjects from simulations/ "
                  f"automatically — no SUBJECTS list to maintain.")

    print(f"\n{'='*60}")
    print(f"Project ready. Next steps:")
    print(f"  1. Drop captures into simulations/<subject>/... and set up each session.yaml")
    print(f"     (session.yaml is the source of truth for that session).")
    print(f"  2. Edit {yaml_dest} only for lab facts that differ from bioscout's defaults")
    print(f"     (marker conventions, GRF axes, EMG rig, sampling rate, ...).")
    print(f"  3. Python:  PROJECT = bioscout.Project(r\"{project}\")")
    print(f"{'='*60}\n")
    return 0
