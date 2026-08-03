"""``python -m bioscout.model_edit`` — the CLI; no arguments means guided."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
