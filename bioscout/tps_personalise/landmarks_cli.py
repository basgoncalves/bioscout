"""``tps-landmarks`` — derive bone landmarks from MRI segmentation masks.

Writes a Slicer-compatible ``.mrk.json`` you can review/adjust in 3D Slicer,
then pass to ``tps-personalise`` as ``mri_landmarks``.

Examples
--------
    tps-landmarks --seg-dir mri/segmentation --out mri/results/auto_landmarks.mrk.json
    tps-landmarks --config config.yaml         # uses segmentation_dir/mri_landmarks
"""
from __future__ import annotations

import argparse
import sys

from .landmarks_from_mri import extract_and_write
from .logging_utils import add_file_handler, get_logger

logger = get_logger("tps_personalise.landmarks")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tps-landmarks",
        description="Extract bone landmarks from MRI segmentation masks -> Slicer .mrk.json",
    )
    p.add_argument("--seg-dir", metavar="DIR",
                   help="Folder of per-bone segmentation masks (.nii.gz).")
    p.add_argument("--out", metavar="PATH",
                   help="Output .mrk.json path.")
    p.add_argument("-c", "--config", metavar="YAML",
                   help="Read segmentation_dir / mri_landmarks from a config instead.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    seg_dir, out = args.seg_dir, args.out

    if args.config:
        from .config import PersonalisationConfig
        cfg = PersonalisationConfig.from_yaml(args.config)
        seg_dir = seg_dir or getattr(cfg, "segmentation_dir", None)
        out = out or cfg.mri_landmarks
        add_file_handler(cfg.output_dir / "landmarks.log")

    if not seg_dir or not out:
        logger.error("need --seg-dir and --out (or --config providing them)")
        return 2

    try:
        extract_and_write(seg_dir, out)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    logger.info("Review the landmarks in 3D Slicer, then run tps-personalise.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
