#!/usr/bin/env python3

from pathlib import Path

from setuptools import find_packages, setup


_base = Path(__file__).parent
_prefix = "__version__ ="
_version = (
    next(
        line
        for line in (_base / "fh_fablib" / "__init__.py").open()
        if line.startswith(_prefix)
    )[len(_prefix) :]
    .strip()
    .strip('"')
)

setup(
    name="fh-fablib",
    version=_version,
    description="fh-fablib",
    long_description=(_base / "README.rst").read_text(),
    author="Matthias Kestenholz",
    author_email="mk@feinheit.ch",
    url="https://github.com/feinheit/fh-fablib/",
    license="BSD License",
    platforms=["OS Independent"],
    packages=find_packages(exclude=["tests", "testapp"]),
    include_package_data=True,
    install_requires=["fabric", "speckenv>=1.1"],
    python_requires=">=3",
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "fl = fabric.main:program.run",
        ]
    },
)
