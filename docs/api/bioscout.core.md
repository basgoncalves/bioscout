# `bioscout.core`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/__init__.py)

Project / Subject / Session / Trial and the analysis engine.

    analysis.py          the object model + the Analyse engine  
    analysis_runner.py   drives Analyse over a selection  
    project_analysis.py  project-level roll-ups  
    subject_registry.py  per-project subjects.json  
    jcf_contributions.py muscle contributions to joint contact force

  
**Why this file imports bioscout.utils before anything else**

``analysis.py`` binds ``bioscout.utils`` at module level, and  
``bioscout/utils/__init__.py`` in turn imports Subject/Session/Analyse from  
``analysis.py`` -- a cycle that only resolves if ``bioscout.utils`` is the one  
that starts. While analysis.py lived INSIDE utils/ that was guaranteed for  
free: importing ``bioscout.utils.analysis`` runs the parent package's  
``__init__`` first. Moving it to ``bioscout.core`` (RESTRUCTURE_PLAN stage 8)  
removed that guarantee, so ``import bioscout.core.analysis`` as the very first  
bioscout import raised ImportError on ``Analyse``.

Importing utils here restores the invariant explicitly: whichever module of  
this package is reached first, ``bioscout.utils`` is fully initialised before  
``analysis.py`` starts executing. When utils IS the caller it is already in  
sys.modules and this is a no-op.
