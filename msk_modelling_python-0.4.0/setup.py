from setuptools import setup, find_packages

__version__ = '0.4.0'

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="msk_modelling_python",
    version=__version__,
    author="Bas",
    author_email="basilio.goncalves7@gmail.com",
    description=f"A Python package for musculoskeletal modelling (version {__version__})",
    long_description=f"{long_description}\n\nVersion: {__version__}",
    long_description_content_type="text/markdown",
    url="https://github.com/basgoncalves/msk_modelling_python",
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
        'msk_modelling_python': [
            '*.yaml', '*.xml', '*.json', '*.txt', '*.bat',
            '*.jpg', '*.png',
        ],
        'msk_modelling_python.config': ['*.yaml', '*.xml'],
        'msk_modelling_python.utils': [
            '*.jpg', '*.png',
            'ceinms/*.exe', 'ceinms/*.dll', 'ceinms/*.txt',
        ],
        'msk_modelling_python.utils.ceinms': ['*.exe', '*.dll', '*.txt'],
        'msk_modelling_python.tests': ['*.xml'],
    },
    entry_points={
        'console_scripts': [
            'msk-gui=msk_modelling_python:launch_gui',
            'msk-batch=msk_modelling_python.__main__:main',
        ],
    },
    python_requires='>=3.8',
    include_package_data=True,
)
