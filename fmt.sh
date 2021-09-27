#!/bin/sh

set -ex
pipx run pyupgrade $(git ls-files "*py")
pipx run black .
pipx run isort --profile=black --lines-after-imports=2 --combine-as .
pipx run flake8 .
