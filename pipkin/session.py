import shlex
import subprocess
from http.server import HTTPServer
from logging import getLogger
from typing import Optional, List, Dict

from pipkin.adapters import Adapter

logger = getLogger(__name__)


class Session:
    """
    Session allows performing several commands on a target with a single device => venv
    synchronization.
    """

    def __init__(self, adapter: Adapter):
        self._adapter = adapter
        self._venv_dir = self._prepare_venv()
        self._state_after_last_commit = self._get_venv_state()

    def install(
        self,
        specs: List[str],
        requirement_files: List[str] = None,
        constraint_files: List[str] = None,
        no_deps: bool = False,
        pre: bool = False,
        upgrade: bool = False,
        upgrade_strategy: str = "only-if-needed",
        force_reinstall: bool = False,
        ignore_installed: bool = False,
        no_warn_conflicts: bool = False,
        prefer_mp_org: Optional[bool] = None,
        index_url: Optional[str] = None,
        extra_index_urls: List[str] = None,
    ):

        requirement_files = requirement_files or []
        constraint_files = constraint_files or []

        args = ["install"]

        for path in requirement_files:
            args += ["-r", path]
        for path in constraint_files:
            args += ["-c", path]

        if no_deps:
            args.append("--no-deps")
        if pre:
            args.append("--pre")
        if upgrade:
            args.append("--upgrade")
        if upgrade_strategy:
            args += ["--upgrade-strategy", upgrade_strategy]
        if force_reinstall:
            args.append("--force-reinstall")
        if ignore_installed:
            args.append("--ignore-installed")
        if no_warn_conflicts:
            args.append("--no-warn-conflicts")

        for spec in specs:
            args.append(spec)

        self._invoke_pip_with_proxy(
            args,
            prefer_mp_org=prefer_mp_org,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
        )

    def list(
        self,
        outdated: bool = False,
        uptodate: bool = False,
        not_required: bool = False,
        pre: bool = False,
        format: str = "columns",
        prefer_mp_org: Optional[bool] = None,
        index_url: Optional[str] = None,
        extra_index_urls: List[str] = None,
    ):

        args = ["list"]

        if outdated:
            args.append("--outdated")
        if uptodate:
            args.append("--uptodate")
        if not_required:
            args.append("--not-required")
        if pre:
            args.append("--pre")
        if format:
            args += ["--format", format]

        self._invoke_pip_with_proxy(
            args,
            prefer_mp_org=prefer_mp_org,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
        )

    def uninstall(self, specs: List[str], requirement_files: List[str]):
        requirement_files = requirement_files or []

        args = ["uninstall"]
        for rf in requirement_files:
            args += ["-r", rf]
        for spec in specs:
            args.append(spec)

        self._invoke_pip(args)

    def commit(self) -> None:
        current_state = self._get_venv_state()
        self._commit_changes(self._state_after_last_commit, current_state)
        self._state_after_last_commit = current_state

    def _commit_changes(self, dists_before: Dict[str, int], dists_after: Dict[str, int]) -> None:
        ...

    def _prepare_venv(self) -> str:
        # 1. create sample venv (if doesn't exist yet)
        # 2. clone the venv for this session (Too slow in Windows ???)
        # https://github.com/edwardgeorge/virtualenv-clone/blob/master/clonevirtualenv.py
        pass

    def _get_venv_state(self) -> Dict[str, int]:
        ...

    def _get_venv_executable(self) -> str:
        ...

    def _get_proxy_url(self) -> str:
        ...

    def _invoke_pip_with_proxy(
        self,
        pip_args: List[str],
        prefer_mp_org: Optional[bool],
        index_url: Optional[str],
        extra_index_urls: List[str],
    ):
        ...
        self._invoke_pip(pip_args)
        ...

    def _invoke_pip(self, args):
        pip_cmd = [
            self._get_venv_executable(),
            "-m",
            "pip",
            "--disable-pip-version-check",
        ] + args
        logger.debug("Calling pip: %s", " ".join(shlex.quote(arg) for arg in pip_cmd))
        subprocess.check_call(pip_cmd)
