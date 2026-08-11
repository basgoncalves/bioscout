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
    description=f"an open-source Python toolbox movement assessment (version {__version__})",
    long_description=f"{long_description}\n\nVersion: {__version__}",
    long_description_content_type="text/markdown",
    url="https://github.com/basgoncalves/bioscout",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
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
        'bioscout.utils': ['*.jpg', '*.png'],
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
    python_requires='>=3.8',
    include_package_data=True,
)
