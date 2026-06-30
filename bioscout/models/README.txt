OpenSim model templates
========================
Place generic .osim model files here. They will be copied to
<project>/Models/ when you run:

    python -m bioscout --init <project_path>

Expected models
---------------
  GPK_generic.osim     — full-body GPK model (default assigned to new subjects)

Geometry folders (mesh files) are gitignored via *Geometry/ in .gitignore.
Add any Geometry/ subfolder alongside its .osim file; it will be copied on
--init even though it is not tracked in git.

Each subject's generic_model field in subjects.json resolves relative to the
project root, e.g.:
  "generic_model": "Models/GPK_generic.osim"
