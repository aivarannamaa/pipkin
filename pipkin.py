#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2022 Aivar Annamaa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import copy
import io
import json
import os.path
import sys
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import textwrap
import threading
from html.parser import HTMLParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import BaseRequestHandler, BaseServer
from textwrap import dedent
from typing import Union, List, Dict, Any, Optional, Tuple, Callable
from urllib.error import HTTPError
from urllib.request import urlopen
import pkg_resources
import logging

import typing

try:
    from shlex import join as shlex_join
except ImportError:
    # before Python 3.8
    def shlex_join(split_command):
        """Return a shell-escaped string from *split_command*."""
        return " ".join(shlex.quote(arg) for arg in split_command)


from pkg_resources import Requirement

import email.parser

logger = logging.getLogger(__name__)

MP_ORG_INDEX = "https://micropython.org/pi"
PYPI_INDEX = "https://pypi.org/pypi"
PYPI_SIMPLE_INDEX = "https://pypi.org/simple"
DEFAULT_INDEX_URLS = [MP_ORG_INDEX, PYPI_INDEX]
SERVER_ENCODING = "utf-8"

__version__ = "0.2b1"

"""
steps:
    - infer target if no explicit connection parameters are given
    - connect (MP)
    - determine target location on the device/mount
    - sync RTC (MP, install, uninstall). Not required for CP?
    - ensure temp venv for pip operations
    - fetch METADATA-s and RECORD-s (may be empty in all cases except "show -f") and populate venv
    - record current state
    - invoke pip (translate paths in the output)
    - determine deleted and changed dists and remove these on the target (according to actual RECORD-s)
    - determine new and changed dists and copy these to the target
    - clear venv



"""


_server: Optional[PipkinServer] = None


def close_server():
    global _server

    if _server is not None:
        _server.shutdown()
        _server = None


class UserError(RuntimeError):
    pass



def error(msg):
    msg = "ERROR: " + msg
    if sys.stderr.isatty():
        print("\x1b[31m", msg, "\x1b[0m", sep="", file=sys.stderr)
    else:
        print(msg, file=sys.stderr)

    return 1


def main(raw_args: Optional[List[str]] = None) -> int:
    if raw_args is None:
        raw_args = sys.argv[1:]

    import argparse

    parser = argparse.ArgumentParser(
        description="Tool for managing MicroPython and CircuitPython packages"
    )
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description='Use "pipkin <command> -h" for usage help of a command ',
        required=True,
    )

    install_parser = subparsers.add_parser(
        "install",
        help="Install a package",
        description=textwrap.dedent(
            """
        Meant for installing both upip and pip compatible distribution packages from
        PyPI and micropython.org/pi to a local directory, USB volume or directly to
        MicroPython filesystem over serial connection (requires rshell).
    """
        ).strip(),
    )

    install_parser.add_argument(
        "specs",
        help="Package specification, eg. 'micropython-os' or 'micropython-os>=0.6'",
        nargs="*",
        metavar="package_spec",
    )
    install_parser.add_argument(
        "-r",
        "--requirement",
        help="Install from the given requirements file.",
        nargs="*",
        dest="requirement_files",
        metavar="REQUIREMENT_FILE",
        default=[],
    )
    install_parser.add_argument(
        "-p",
        "--port",
        help="Serial port of the device "
        "(specify if you want pipkin to upload the result to the device)",
        nargs="?",
    )
    install_parser.add_argument(
        "-t",
        "--target",
        help="Target directory (on device, if port is given, otherwise local)",
        default=".",
        dest="target_dir",
        metavar="TARGET_DIR",
        required=True,
    )

    list_parser = subparsers.add_parser("list", help="List installed packages")

    for p in [install_parser, list_parser]:
        p.add_argument(
            "-i",
            "--index-url",
            help="Custom index URL",
        )
        p.add_argument(
            "-v",
            "--verbose",
            help="Show more details about the process",
            action="store_true",
        )
        p.add_argument(
            "-q",
            "--quiet",
            help="Don't show non-error output",
            action="store_true",
        )

    parser.add_argument(
        "--version", help="Show program version and exit", action="version", version=__version__
    )
    args = parser.parse_args(args=raw_args)

    if args.quiet and args.verbose:
        print("Can't be quiet and verbose at the same time", file=sys.stderr)
        sys.exit(1)


    if args.verbose:
        logging_level = logging.DEBUG
    elif args.quiet:
        logging_level = logging.ERROR
    else:
        logging_level = logging.INFO

    logger.setLevel(logging_level)
    logger.propagate = True
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging_level)
    logger.addHandler(console_handler)

    # infer target
    if args.port and not _get_rshell_command():
        return error("Could not find rshell (required for uploading when serial port is given)")

    if args.port and not args.target_dir.startswith("/"):
        return error("If port is given then target dir must be absolute Unix-style path")
    target = ...

    if args.command == "install":


    if not all_specs:
        return error("At least one package specifier or non-empty requirements file is required")

    try:
        install(args.specs, requirement_files=args.requirement_files, target_dir=args.target_dir, index_urls=index_urls, port=args.port)
    except KeyboardInterrupt:
        return 1
    except UserError as e:
        return error(str(e))
    except subprocess.CalledProcessError:
        # assuming the subprocess (pip or rshell) already printed the error
        return 1
    finally:
        close_server()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
