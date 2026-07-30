"""Command-line entry point.

Replaces the "run nine notebooks in order" workflow with a single command::

    tps-personalise --config config.yaml
    tps-personalise --bioscout PROJECT_ROOT --player 012 --trial HAB1

Exits non-zero with a clear message on missing inputs (fail-fast), matching
BioScout conventions.
"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import PersonalisationConfig
from .logging_utils import add_file_handler, get_logger
from .pipeline import Personaliser

logger = get_logger("tps_personalise.cli")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tps-personalise",
        description="TPS personalisation of an OpenSim model from MRI bone geometry.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("-c", "--config", metavar="YAML", help="Path to a YAML config.")
    src.add_argument("-b", "--bioscout", metavar="PROJECT_ROOT",
                     help="BioScout project root (uses players.json).")
    p.add_argument("--player", metavar="ID", help="Player id (with --bioscout).")
    p.add_argument("--trial", metavar="NAME", help="Trial subfolder (with --bioscout).")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    p.add_argument("--log-file", metavar="PATH",
                   help="Write logs to this file (default: <output_dir>/personalise.log).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verbose:
        logging.getLogger("tps_personalise").setLevel(logging.DEBUG)

    try:
        if args.config:
            cfg = PersonalisationConfig.from_yaml(args.config)
        else:
            if not args.player:
                logger.error("--player is required with --bioscout")
                return 2
            cfg = PersonalisationConfig.from_bioscout(
                player_id=args.player, project_root=args.bioscout, trial=args.trial
            )
        cfg.ensure_dirs()
        log_path = args.log_file or (cfg.output_dir / "personalise.log")
        add_file_handler(log_path)
        logger.info("Logging to %s", log_path)
        Personaliser(cfg).run()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
