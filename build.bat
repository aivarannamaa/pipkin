echo "isorting ..."
venv\Scripts\isort pipkin


echo
echo "blackening ..."
venv\Scripts\black pipkin

echo
echo "running mypy ..."
venv\Scripts\mypy pipkin

echo
echo "running pylint ..."
venv\Scripts\pylint --msg-template='{abspath}:{line},{column:2d}: {msg} ({symbol})' pipkin
