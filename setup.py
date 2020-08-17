#!/usr/bin/env python

import os
from io import open

from setuptools import find_packages, setup


def read(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


setup(
    name="fh-fablib",
    version="0.9.20200817",
    description="fh-fablib",
    long_description=read("README.rst"),
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
)
