import subprocess
from typing import Optional, List, Dict
import sys
import textwrap
import logging

from pipkin.adapters import create_adapter
from pipkin.session import Session

logger = logging.getLogger(__name__)

__version__ = "0.2b1"


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

    parser.add_argument(
        "--version",
        help="Show program version and exit",
        action="version",
        version=__version__,
    )

    parser.add_argument(
        "-p",
        "--port",
        help="Serial port of the target device",
        nargs="?",
    )

    parser.add_argument(
        "-m",
        "--mount",
        help="Mount point (volume, disk, drive) of target device's filesystem",
        nargs="?",
    )

    parser.add_argument(
        "-d",
        "--dir",
        help="Mount point (volume, disk, drive) of target device's filesystem",
        nargs="?",
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
        Installs upip or pip compatible distribution packages onto a MicroPython/CircuitPython device 
        or into a local directory.
    """
        ).strip(),
    )

    import pip

    pip.main()

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

    try:
        adapter = create_adapter(args.port)
        session = Session(adapter)

        if args.command == "install":
            # TODO: more args
            session.install(args.specs, requirement_files=args.requirement_files)
        elif args.command == "list":
            session.list()  # TODO:
        elif args.command == "uninstall":
            session.uninstall(args.specs, requirement_files=args.requirement_files)
        else:
            raise UserError(f"Unknown command {args.command}")

        session.commit()
    except KeyboardInterrupt:
        return 1
    except UserError as e:
        return error(str(e))
    except subprocess.CalledProcessError:
        # assuming the subprocess (pip or rshell) already printed the error
        return 1
    finally:
        # TODO: close session
        pass

    return 0
