pipkin
=======
Tool for installing distribution packages for MicroPython and CircuitPython.

Supports both `upip-compatible packages <https://docs.micropython.org/en/latest/reference/packages.html>`_,
and regular pip-compatible
packages (by using `pip install --target ... <https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-t>`_).

By default it prefers packages at micropython.org-s index. If the package or the required version is not
found there, then it turns to PyPI.

If ``--port`` is given and `rshell <https://pypi.org/project/rshell/>`_ is available then it uploads
the extracted files to the target device, otherwise it just extracts modules to a directory in the local filesystem.
``--target`` directory must be explicitly given in both cases. If target is at local filesystem, then
makes sure data gets synced (useful, if target is a USB volume representing MicroPython or
CircuitPython filesystem)

Installation
--------------
``pip install pipkin``

Requires Python 3.6+. The only required dependencies are ``pip`` and ``setuptools``
(most likely already present).  ``rshell`` is an optional dependency.

Usage examples
--------------

* ``pipkin install --port /dev/ttyACM0 --target /lib micropython-logging``
* ``pipkin install --target G:\lib adafruit-circuitpython-ssd1306``

pipkin -h
----------

::

    usage: pipkin.py [-h] [--version] {install,list} ...

    Tool for managing MicroPython and CircuitPython packages

    optional arguments:
      -h, --help      show this help message and exit
      --version       Show program version and exit

    commands:
      Use "pipkin <command> -h" for usage help of a command

      {install,list}
        install       Install a package
        list          List installed packages
    (venv) annamaa@a2:~/python_stuff/pipkin $

pipkin install -h
------------------

::

    usage: pipkin.py install [-h] [-r [REQUIREMENT_FILE [REQUIREMENT_FILE ...]]] [-p [PORT]] -t TARGET_DIR [-i INDEX_URL] [-v] [-q] [package_spec [package_spec ...]]

    Meant for installing both upip and pip compatible distribution packages from PyPI and micropython.org/pi to a local directory, USB volume or directly to MicroPython filesystem over
    serial connection (requires rshell).

    positional arguments:
      package_spec          Package specification, eg. 'micropython-os' or 'micropython-os>=0.6'

    optional arguments:
      -h, --help            show this help message and exit
      -r [REQUIREMENT_FILE [REQUIREMENT_FILE ...]], --requirement [REQUIREMENT_FILE [REQUIREMENT_FILE ...]]
                            Install from the given requirements file.
      -p [PORT], --port [PORT]
                            Serial port of the device (specify if you want pipkin to upload the result to the device)
      -t TARGET_DIR, --target TARGET_DIR
                            Target directory (on device, if port is given, otherwise local)
      -i INDEX_URL, --index-url INDEX_URL
                            Custom index URL
      -v, --verbose         Show more details about the process
      -q, --quiet           Don't show non-error output
