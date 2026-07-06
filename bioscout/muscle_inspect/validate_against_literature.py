"""validate_against_literature.py  --  standalone literature validation.

Edit CONFIG, then:  python validate_against_literature.py
Writes validation_moment_arms.png + validation_rmse.csv into validation_<model>/
next to the model. (The same validation also runs inside run_moment_arm_inspection.py
when CONFIG["validate"] is True.)
"""
from __future__ import annotations
import logging, os

CONFIG = {
    "model": "scaled.osim",                 # use your corrected _modWO model
    "literature_csv": "validation/literature_moment_arms.csv",
    "out": None,                            # None = validation_<model>/ next to the model
    "side": "_r",
    "n": 60,
}


def main():
    here = os.getcwd()
    from .logutil import setup_logging
    from . import muscle_length_validation as validation  # up-to-date loader/colours/knee-flip
    from .paths import resolve_literature_csv
    setup_logging(logging.INFO)
    model = CONFIG["model"] if os.path.isabs(CONFIG["model"]) else os.path.join(here, CONFIG["model"])
    # prefer the configured CSV; fall back to the copy bundled with the package
    csv_path = resolve_literature_csv(CONFIG["literature_csv"])
    out = CONFIG["out"] or os.path.join(os.path.dirname(model),
                                        f"validation_{os.path.splitext(os.path.basename(model))[0]}")
    validation.run_validation(model, csv_path, out, side=CONFIG["side"], n=CONFIG["n"])


if __name__ == "__main__":
    main()
