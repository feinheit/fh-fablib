#!/bin/sh

set -ex

D=$(date +%Y%m%d)
sed -i -e "s/__version__ =.*/__version__ = \"1.0.$D\"/" fh_fablib/__init__.py
git commit -a -m "fh-fablib 1.0.$D"
