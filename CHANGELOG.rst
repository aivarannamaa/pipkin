===============
Version history
===============

2.1b1 (2024-03-31)
==================
* Use `packaging` instead of `pkg_resources`
* Start using pip 24.0
* Create new workspace if pip version on pipkin major version changes
* Don't install setuptools and wheel into workspace

2.0b2 (2023-05-07)
==================
* Restore support for old micropython.org index
* Use different proxy port with --no-mp-org (to avoid pip taking the wrong wheel from the cache)

2.0b1 (2023-05-01)
==================
* Support micropython-lib index v2, #5

1.0b8 (2023-01-14)
==================
* Fix AssertionError when upgrading a package

1.0b7 (2022-12-30)
==================
* Optimize and enhance `cache` command
* Add extra debug logging
* Upgrade `wheel` and `setuptools`

1.0b6 (2022-10-30)
==================
* Fix the problem with distribution names containing period, #4

1.0b5 (2022-10-22)
==================
* Fix wheel name parsing, #1, by @surdouski
* Experiment with different style of creating subprocess

1.0b4 (2022-08-14)
==================
* Take OSC sequences into account when parsing bare metal output

1.0b3 (2022-04-10)
==================
* Fix file operations for CircuitPython boards used over serial
* Fix file operations for boards without errno module
* Fix file operations for boards without binascii module

1.0b2 (2022-03-21)
==================
* Various fixes

1.0b1 (2022-03-21)
==================
* First release after big redesign
