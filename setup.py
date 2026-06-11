from setuptools import setup, find_packages

__version__ = '1.0.0'

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bioscout",
    version=__version__,
    author="Bas",
    author_email="basilio.goncalves7@gmail.com",
    description=f"A Python package for musculoskeletal modelling (version {__version__})",
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
    ],
    extras_require={
        "recording": ["opencv-python", "mediapipe"],
    },
    package_data={
        'bioscout': [
            '*.yaml', '*.xml', '*.json', '*.txt', '*.bat',
            '*.jpg', '*.png',
        ],
        'bioscout.config': ['*.yaml', '*.xml'],
        'bioscout.utils': [
            '*.jpg', '*.png',
            'ceinms/*.exe', 'ceinms/*.dll', 'ceinms/*.txt',
        ],
        'bioscout.utils.ceinms': ['*.exe', '*.dll', '*.txt'],
        'bioscout.tests': ['*.xml'],
        'bioscout.models': ['*.osim'],
    },
    entry_points={
        'console_scripts': [
            'bioscout-gui=bioscout:launch_gui',
            'bioscout=bioscout.__main__:main',
        ],
    },
    python_requires='>=3.8',
    include_package_data=True,
)
