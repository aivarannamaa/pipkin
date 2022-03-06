#!/usr/bin/env bash

. venv/bin/activate

echo "isorting ..."
isort pipkin


echo
echo "blackening ..."
black pipkin
