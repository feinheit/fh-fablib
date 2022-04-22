#!/bin/sh

set -e

VERSION="1.0.$(date +%Y%m%d).1"
if ! grep --quiet "$VERSION" CHANGELOG.rst
then
    echo "$VERSION not found in CHANGELOG.rst"
    exit 1
fi

set -x
sed -i -e "s/__version__ =.*/__version__ = \"$VERSION\"/" fh_fablib/__init__.py
sed -i -e 's/fl.require(".*")/fl.require("'$VERSION'")/' README.rst
sed -i -e "s/version =.*/version = $VERSION/" setup.cfg
git commit -a -m "fh-fablib $VERSION"
git tag -m "fh-fablib $VERSION" "$VERSION"
