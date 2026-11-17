# `bioscout.devtools`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/__init__.py)

The `bioscout utils` VERB's implementation: environment, deps, docs, editor.

    envcheck.py             is the conda env the expected one? (stdlib only)  
    dependency_installer.py `utils install`  
    md2pdf.py               `utils md2pdf`  
    settings_updater.py     regenerate a project settings.py from the template  
    run_check.py            the anti-silent-failure toolbox

Named `devtools/` rather than `utils/` so it stops colliding with "utils"  
meaning generic shared code everywhere else in the codebase -- that clash was  
the actual problem, not which folder holds which five files.

Nothing is imported eagerly: `bioscout -h` must answer in a broken env.
