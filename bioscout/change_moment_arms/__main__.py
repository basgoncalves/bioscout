"""``python -m bioscout.change_moment_arms`` -> the interactive tool."""
import sys

from .cli import run

if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
