set PATH=C:\Python310-64\Scripts;%PATH%
rmdir build /s /q

@echo ............... CREATING wheel ................................
python setup.py bdist_wheel

@echo ............... CREATING sdist ................................
python setup.py sdist --formats=gztar

rmdir pipkin.egg-info /s /q
