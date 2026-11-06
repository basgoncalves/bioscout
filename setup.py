import re
from pathlib import Path
from setuptools import setup, find_packages

# Single source of truth for the version: bioscout/__init__.py
__version__ = re.search(
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    Path(__file__).parent.joinpath("bioscout", "__init__.py").read_text(encoding="utf-8"),
    re.M,
).group(1)

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
# the version under the logo always says the version being built, not whatever the README last had
long_description = re.sub(r'(<p align="center">)v[0-9][0-9.]*', rf"\g<1>v{__version__}", long_description, count=1)

setup(
    name="bioscout",
    version=__version__,
    author="Bas",
    author_email="basilio.goncalves7@gmail.com",
    # PyPI prints this one line directly under the project name, and it is what
    # shows in index listings. "BETA" goes HERE rather than in the version
    # string: a 2.0.0bN version would make pip treat the release as a
    # pre-release and hide it from the landing page entirely.
    description=(
        f"BETA ({__version__}) - an open-source Python toolbox for "
        "musculoskeletal modelling and movement assessment"
    ),
    long_description=f"{long_description}\n\nVersion: {__version__}",
    long_description_content_type="text/markdown",
    url="https://github.com/basgoncalves/bioscout",
    packages=find_packages(),
    classifiers=[
        # "Beta" is declared HERE, not in the version string. A PEP 440
        # pre-release (2.0.0bN) is hidden from the PyPI landing page and
        # skipped by pip unless --pre; this classifier says the same thing
        # while 2.0.0 stays a normal, installable release.
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "matplotlib",
        "plotly",
        "Pillow",
        "pyyaml",
        "c3d",
        "packaging",
        "pyperclip",
        "psutil",
        "pyautogui",
        "pygetwindow",
        "screeninfo",
        "fitparse",
        "requests",
    ],
    extras_require={
        "recording": ["opencv-python", "mediapipe", "imageio-ffmpeg"],
        # bioscout.model.mri2msk (personalised models from MRI segmentations)
        "mri2msk": ["trimesh", "fast-simplification", "openpyxl", "customtkinter"],
    },
    # Duplicate keys here are silently dropped by Python (the last one wins),
    # so this stays a single de-duplicated block.
    package_data={
        'bioscout': [
            '*.yaml', '*.xml', '*.json', '*.txt', '*.bat',
            '*.jpg', '*.png',
        ],
        'bioscout.config': ['*.yaml', '*.xml'],
        # the task-event definitions the figures read (editable defaults)
        'bioscout.session': ['*.yaml'],
        'bioscout.models': ['*.osim', '*.txt'],
        'bioscout.setup_files': ['*.xml', '*.txt'],
        'bioscout.model.mri2msk': ['templates/*.xml', 'assets/*.png', 'assets/*.ico', '*.md'],
        'bioscout.tests': ['*.xml'],
        # The bone-landmark template is the source side of every TPS warp;
        # without it a wheel install fails at the first personalise call.
        'bioscout.model.tps': ['data/*.xml', 'data/*.yaml', '*.md'],
        'bioscout.model.moment_arms': ['*.md'],
        # paths.py resolves the literature corpus at PKG_DIR/validation/,
        # so without this a wheel install has no literature to validate
        # against and every muscle_inspect validate/fibre/strength call
        # falls back or fails. Source checkouts hid it.
        'bioscout.model.inspect': ['validation/*.csv', 'validation/*.json'],
        'bioscout.utils': ['*.jpg', '*.png'],
        'bioscout.simulate.mrs': ['*.m'],
        # *.zip is torch_cpu.zip; torch_cpu.dll is excluded below.
        'bioscout.simulate.ceinms.bin': ['*.exe', '*.dll', '*.txt', '*.zip'],
    },
    # package_data globs cannot express "every dll EXCEPT this one", and the one
    # exception is 252 MB — the difference between a publishable wheel and a
    # rejected upload. ceinms.py unzips it on first run.
    exclude_package_data={
        'bioscout.simulate.ceinms.bin': ['torch_cpu.dll'],
    },
    entry_points={
        'console_scripts': [
            # the VERB grammar (`bioscout simulate so ...`). __main__ is the
            # older flag CLI (`--scale-session`); cli.main forwards to it, so
            # both spellings keep working from one launcher.
            'bioscout=bioscout.cli:main',
            'tps-personalise=bioscout.model.tps.cli:main',
            'change-moment-arms=bioscout.model.moment_arms.cli:run',
            'tps-landmarks=bioscout.model.tps.landmarks_cli:main',
        ],
    },
    # 3.9 is the documented floor (see the Requirements table in README.md).
    # It was '>=3.8', which let pip install a build that then failed on import.
    # No upper bound on purpose: OpenSim's supported range moves, and a pinned
    # ceiling here would block installs the day it widens.
    python_requires='>=3.9',
    include_package_data=True,
)
