#!/usr/bin/env bash

. venv/bin/activate

echo "isorting ..."
isort pipkin


echo
echo "blackening ..."
black pipkin

echo
echo "running mypy ..."
mypy pipkin

echo
echo "running pylint ..."
pylint --msg-template='{abspath}:{line},{column:2d}: {msg} ({symbol})' pipkin
