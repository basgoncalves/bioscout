"""Entry point so `python -m bioscout.tests` works.

`bioscout.tests` is a PACKAGE, and `python -m <package>` executes the package's
__main__.py -- the `if __name__ == "__main__"` guard in __init__.py never fires
that way. Without this file the command dies with

    No module named bioscout.tests.__main__; 'bioscout.tests' is a package
    and cannot be directly executed
"""
import sys

from . import run

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
