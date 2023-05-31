#!/bin/sh

set -e

VERSION="1.0.$(date +%Y%m%d)"
VERSION="${1:-$VERSION}"

if ! grep --quiet "$VERSION" CHANGELOG.rst
then
    echo "$VERSION not found in CHANGELOG.rst"
    exit 1
fi

set -x
sed -i -e 's/fl.require(".*")/fl.require("'$VERSION'")/' README.rst
hatch version $VERSION
git commit -a -m "fh-fablib $VERSION"
git tag -m "fh-fablib $VERSION" "$VERSION"
