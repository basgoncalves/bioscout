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
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "matplotlib",
        "plotly",
        "customtkinter",
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
        "recording": ["opencv-python", "mediapipe"],
    },
    # Duplicate keys here are silently dropped by Python (the last one wins),
    # so this stays a single de-duplicated block.
    package_data={
        'bioscout': [
            '*.yaml', '*.xml', '*.json', '*.txt', '*.bat',
            '*.jpg', '*.png',
        ],
        'bioscout.config': ['*.yaml', '*.xml'],
        'bioscout.models': ['*.osim', '*.txt'],
        'bioscout.setup_files': ['*.xml', '*.txt'],
        'bioscout.tests': ['*.xml'],
        # The bone-landmark template is the source side of every TPS warp;
        # without it a wheel install fails at the first personalise call.
        'bioscout.tps_personalise': ['data/*.xml', 'data/*.yaml', '*.md'],
        'bioscout.change_moment_arms': ['*.md'],
        # paths.py resolves the literature corpus at PKG_DIR/validation/,
        # so without this a wheel install has no literature to validate
        # against and every muscle_inspect validate/fibre/strength call
        # falls back or fails. Source checkouts hid it.
        'bioscout.muscle_inspect': ['validation/*.csv', 'validation/*.json'],
        'bioscout.utils': ['*.jpg', '*.png'],
        # The force surrogate the markerless pipeline loads. Not the 9.4 MB
        # MediaPipe task file, which is gitignored and resolved at runtime.
        'bioscout.movement_detector.markerless': ['models/*.pkl', 'models/*.md'],
        # *.zip is torch_cpu.zip; torch_cpu.dll is excluded below.
        'bioscout.utils.ceinms.bin': ['*.exe', '*.dll', '*.txt', '*.zip'],
    },
    # package_data globs cannot express "every dll EXCEPT this one", and the one
    # exception is 252 MB — the difference between a publishable wheel and a
    # rejected upload. ceinms.py unzips it on first run.
    exclude_package_data={
        'bioscout.utils.ceinms.bin': ['torch_cpu.dll'],
    },
    entry_points={
        'console_scripts': [
            'bioscout-gui=bioscout:launch_gui',
            'bioscout=bioscout.__main__:main',
            'tps-personalise=bioscout.tps_personalise.cli:main',
            'change-moment-arms=bioscout.change_moment_arms.cli:run',
            'tps-landmarks=bioscout.tps_personalise.landmarks_cli:main',
        ],
    },
    # 3.9 is the documented floor (see the Requirements table in README.md).
    # It was '>=3.8', which let pip install a build that then failed on import.
    # No upper bound on purpose: OpenSim's supported range moves, and a pinned
    # ceiling here would block installs the day it widens.
    python_requires='>=3.9',
    include_package_data=True,
)
