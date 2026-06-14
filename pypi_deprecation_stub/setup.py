"""
Deprecation stub for msk-modelling-python.

Publish this as the final version of msk-modelling-python on PyPI.
It installs bioscout and prints a migration warning.

Steps:
    cd pypi_deprecation_stub
    pip install build twine
    python -m build
    twine upload dist/*
"""
from setuptools import setup

setup(
    name="msk-modelling-python",
    version="0.5.0",  # bump past current 0.4.x so pip picks it up
    author="Bas",
    author_email="basilio.goncalves7@gmail.com",
    description="DEPRECATED — use 'bioscout' instead",
    long_description=(
        "This package has been renamed to **bioscout**.\n\n"
        "Please run: `pip install bioscout`\n\n"
        "This stub exists only to redirect existing users."
    ),
    long_description_content_type="text/markdown",
    url="https://github.com/basgoncalves/bioscout",
    install_requires=["bioscout"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 7 - Inactive",
        "Programming Language :: Python :: 3",
    ],
    py_modules=[],
)
