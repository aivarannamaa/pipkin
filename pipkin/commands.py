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


def install(
    specs: List[str],
    requirement_files: List[str],
    target_dir: str,
    index_urls: List[str] = None,
    port: Optional[str] = None,
):
    if not index_urls:
        index_urls = DEFAULT_INDEX_URLS

    if isinstance(spec, str):
        specs = [spec]
    else:
        specs = spec

    temp_dir = tempfile.mkdtemp()
    try:
        _install_with_pip(specs, temp_dir, index_urls)
        _remove_unneeded_files(temp_dir)
        if port is not None:
            _copy_to_micropython_over_serial(temp_dir, port, target_dir)
        else:
            _copy_to_local_target_dir(temp_dir, target_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _copy_to_local_target_dir(source_dir: str, target_dir: str):
    logger.info("Copying files to %s", os.path.abspath(target_dir))
    if not os.path.exists(target_dir):
        logger.info("Target directory '%s' doesn't exist. Creating.", target_dir)
        os.makedirs(target_dir, mode=0o700)

    # Copying manually in order to be able to use os.fsync
    # see https://learn.adafruit.com/adafruit-circuit-playground-express/creating-and-editing-code
    # #1-use-an-editor-that-writes-out-the-file-completely-when-you-save-it
    for root, dirs, files in os.walk(source_dir):
        relative_dir = root[len(source_dir) :].lstrip("/\\")
        full_target_dir = os.path.join(target_dir, relative_dir)
        for dir_name in dirs:
            full_path = os.path.join(full_target_dir, dir_name)
            if os.path.isdir(full_path):
                logger.info("Directory %s already exists", os.path.join(relative_dir, dir_name))
            elif os.path.isfile(full_path):
                raise UserError("Can't treat existing file %s as directory", full_path)
            else:
                logger.info("Creating %s", os.path.join(relative_dir, dir_name))
                os.makedirs(full_path, 0o700)

        for file_name in files:
            full_source_path = os.path.join(root, file_name)
            full_target_path = os.path.join(full_target_dir, file_name)
            logger.debug("Preparing %s => %s", full_source_path, full_target_path)

            if os.path.isfile(full_target_path):
                logger.info("Overwriting %s", os.path.join(relative_dir, file_name))
            elif os.path.isdir(full_target_path):
                raise UserError("Can't treat existing directory %s as file", full_target_path)
            else:
                logger.info("Copying %s", os.path.join(relative_dir, file_name))

            with open(full_source_path, "rb") as in_fp, open(full_target_path, "wb") as out_fp:
                out_fp.write(in_fp.read())
                out_fp.flush()
                os.fsync(out_fp)


def _copy_to_micropython_over_serial(source_dir: str, port: str, target_dir: str):
    assert target_dir.startswith("/")

    cmd = _get_rshell_command() + ["-p", port, "rsync", source_dir, "/pyboard" + target_dir]
    logger.debug("Uploading with rsync: %s", shlex_join(cmd))
    subprocess.check_call(cmd)


def _get_rshell_command() -> Optional[List[str]]:
    if shutil.which("rshell"):
        return ["rshell"]
    else:
        return None


def _install_with_pip(specs: List[str], target_dir: str, index_urls: List[str]):
    global _server

    logger.info("Installing with pip: %s", specs)

    suitable_indexes = [url for url in index_urls if url != MP_ORG_INDEX]
    if not suitable_indexes:
        raise UserError("No suitable indexes for pip")

    index_args = ["--index-url", suitable_indexes.pop(0)]
    while suitable_indexes:
        index_args += ["--extra-index-url", suitable_indexes.pop(0)]
    if index_args == ["--index-url", "https://pypi.org/pypi"]:
        # for some reason, this form does not work for some versions of some packages
        # (eg. micropython-os below 0.4.4)
        # TODO: ?
        index_args = []

    port = 8763  # TODO:
    _server = PipkinServer(("", port), PipkinProxyHandler)
    threading.Thread(name="pipkin proxy", target=_server.serve_forever).start()
    index_args = ["--index-url", "http://localhost:{port}/".format(port=port)]

    args = [
        "--no-input",
        "--disable-pip-version-check",
        "install",
        "--no-compile",
        "--no-cache-dir",
        "--upgrade",
        "--target",
        target_dir,
    ] + index_args

    pip_cmd = (
        [
            sys.executable,
            "-m",
            "pip",
        ]
        + args
        + specs
    )
    logger.debug("Calling pip: %s", shlex_join(pip_cmd))
    subprocess.check_call(pip_cmd)
    close_server()


def _remove_unneeded_files(path: str) -> None:
    unneeded = ["Scripts" if os.name == "nt" else "bin", "__pycache__"]

    if "adafruit_blinka" in os.listdir(path):
        unneeded += [
            "adafruit_blinka",
            "adafruit_platformdetect",
            "Adafruit_PureIO",
            "microcontroller",
            "pyftdi",
            "serial",
            "usb",
            "analogio.py",
            "bitbangio.py",
            "board.py",
            "busio.py",
            "digitalio.py",
            "micropython.py",
            "neopixel_write.py",
            "pulseio.py",
            "pwmio.py",
            "rainbowio.py",
        ]

    unneeded_suffixes = [".pyc"]

    for name in os.listdir(path):
        if name in unneeded or any(name.endswith(suffix) for suffix in unneeded_suffixes):
            full_path = os.path.join(path, name)
            if os.path.isfile(full_path):
                os.remove(full_path)
            else:
                shutil.rmtree(full_path)



