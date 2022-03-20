pipkin
=======
Tool for managing distribution packages for MicroPython and CircuitPython on target devices or in a local directory.

Supports both `upip-compatible packages <https://docs.micropython.org/en/latest/reference/packages.html>`_,
and regular pip-compatible packages.

By default it prefers packages at micropython.org-s index. If the package or the required version is not
found there, then it turns to PyPI.

Unlike some of the package managers for MicroPython and CircuitPython, pipkin keeps a minimal set of package
metadata (trimmed .dist-info/METADATA and .dist-info/RECORD) next to the package itself, just like pip.
This enables straigthforward approach for uninstalling, listing and freezing.

When installing with ``--compile`` switch, pipkin uses suitable `mpy-cross` to compile the
py-files on the fly and transfers resulting mpy-files to the target.

Installation
--------------
``pip install pipkin``

Usage
-----

The basic structure of the command line is ``pipkin <target selection> <command> <command arguments>``.
For example:

* ``pipkin --port /dev/ttyACM0 install micropython-logging``
* ``pipkin --mount G:\lib install adafruit-circuitpython-ssd1306``
* ``pipkin --mount G:\lib install --compile adafruit-circuitpython-ssd1306``
* ``pipkin --dir my_project/lib install micropython-logging micropython-oled``
* ``pipkin --port COM5 uninstall micropython-logging micropython-oled``
* ``pipkin --port COM5 list --outdated``

If you have attached a single CircuitPython device (with its filesystem mounted as a disk) or
a single well known MicroPython device (eg. Raspberry Pi Pico), then you can omit the target selection
part:

* ``pipkin install adafruit-circuitpython-ssd1306``

pipkin -h
----------

::

    usage: pipkin [-h] [-V] [-v | -q] [-p <port> | -m <path> | -d <path>] {install,uninstall,list,show,freeze,check,download,wheel,cache} ...

    Tool for managing MicroPython and CircuitPython packages

    general:
      -h, --help            Show this help message and exit
      -V, --version         Show program version and exit
      -v, --verbose         Show more details about the process
      -q, --quiet           Don't show non-error output

    target selection (pick one or let pipkin autodetect the port or mount):
      -p <port>, --port <port>
                            Serial port of the target device
      -m <path>, --mount <path>
                            Mount point (volume, disk, drive) of the target device
      -d <path>, --dir <path>
                            Directory in the local filesystem

    commands:
      Use "pipkin <command> -h" for usage help of a command

      {install,uninstall,list,show,freeze,check,download,wheel,cache}
        install             Install packages.
        uninstall           Uninstall packages.
        list                List installed packages.
        show                Show information about one or more installed packages.
        freeze              Output installed packages in requirements format.
        check               Verify installed packages have compatible dependencies.
        download            Download packages.
        wheel               Build Wheel archives for your requirements and dependencies.
        cache               Inspect and manage pipkin cache.

pipkin install -h
------------------

::

    usage: pipkin install [-h] [-r [<file> [<file> ...]]] [-c [<file> [<file> ...]]] [--no-deps] [--pre] [-i <url>] [--extra-index-url [<url> [<url> ...]]]
                               [--no-index] [--no-mp-org] [-f <url|file|dir>] [-U] [--upgrade-strategy <upgrade_strategy>] [--force-reinstall] [--compile]
                               [<spec> [<spec> ...]]

    Installs upip or pip compatible distribution packages onto a MicroPython/CircuitPython device or into a local directory.

    positional arguments:
      <spec>                Package specification, eg. 'micropython-os' or 'micropython-os>=0.6'

    optional arguments:
      -h, --help            show this help message and exit
      -U, --upgrade         Upgrade all specified packages to the newest available version. The handling of dependencies depends on the upgrade-strategy used.
      --upgrade-strategy <upgrade_strategy>
                            Determines how dependency upgrading should be handled [default: only-if-needed]. 'eager' - dependencies are upgraded regardless of
                            whether the currently installed version satisfies the requirements of the upgraded package(s). 'only-if-needed' - are upgraded only when
                            they do not satisfy the requirements of the upgraded package(s).
      --force-reinstall     Reinstall all packages even if they are already up-to-date.
      --compile             Compile and install mpy files.

    package selection:
      -r [<file> [<file> ...]], --requirement [<file> [<file> ...]]
                            Install from the given requirements file.
      -c [<file> [<file> ...]], --constraint [<file> [<file> ...]]
                            Constrain versions using the given constraints file.
      --no-deps             Don't install package dependencies.
      --pre                 Include pre-release and development versions. By default, pipkin only finds stable versions.

    index selection:
      -i <url>, --index-url <url>
                            Base URL of the Python Package Index (default https://pypi.org/simple).
      --extra-index-url [<url> [<url> ...]]
                            Extra URLs of package indexes to use in addition to --index-url.
      --no-index            Ignore package index (only looking at --find-links URLs instead).
      --no-mp-org           Don't let micropython.org/pi override other indexes.
      -f <url|file|dir>, --find-links <url|file|dir>
                            If a URL or path to an html file, then parse for links to archives such as sdist (.tar.gz) or wheel (.whl) files. If a local path or
                            file:// URL that's a directory, then look for archives in the directory listing.

Adafruit-Blinka
---------------
`Adafruit-Blinka <https://pypi.org/project/Adafruit-Blinka/>`_ is a compatibility library which allows
running CircuitPython code with CPython. When publishing CircuitPython libraries at PyPI, Adafruit
and the community have so far targeted only CPython users, because tools for connecting PyPI with bare metal
CircuitPython did not exist (or because at the moment it is not clear how to publish wheels for Pythons
which can't run pip themselves). Therefore the CircuitPython libraries at PyPI usually have Adafruit-Blinka
dependency, which is not relevant (and would even cause problems) on bare metal CircuitPython devices.

pipkin's current approach is to let its custom index output dummy Adafruit-Blinka distribution, which contains
no modules and has no dependencies. This means when you're installing a library which depends on Adafruit-Blinka,
you'll get Blinka's .dist-info directory with METADATA and RECORD, but nothing else. Let's call it
an optimized build.

Implementation
--------------
pipkin delegates most of its work to our old friend pip. This is the reason it is able to offer
so much functionality.

Both upip-compatibility and support for micropython.org-s
index is achieved by setting up a temporary local index, which hides these issues from pip.

Non-CPython installation target is achieved by creating and maintaining private working environment (venv).
In the beginning of the session, pipkin collects package metadata from the target (eg. from the /lib directory
of the device connected over serial) and creates corresponding dummy packages in the working environment.
Then it starts the temporary local index and invokes venv-s pip aginst it. When pip finishes, it detects the
distributions which are removed, added or changed and applies corresponding changes to the target device or
directory.

