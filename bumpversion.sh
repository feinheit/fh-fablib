#!/bin/sh

set -e

VERSION="1.0.$(date +%Y%m%d)"
if ! grep --quiet "$VERSION" CHANGELOG.rst
then
    echo "$VERSION not found in CHANGELOG.rst"
    exit 1
fi

set -x
sed -i -e "s/__version__ =.*/__version__ = \"$VERSION\"/" fh_fablib/__init__.py
git commit -a -m "fh-fablib $VERSION"
git tag -m "fh-fablib $VERSION" "$VERSION"
