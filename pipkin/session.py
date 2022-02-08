import hashlib
import os.path
import shlex
import shutil
import subprocess
import sys
import venv
from logging import getLogger
from typing import Optional, List, Dict, Tuple, Set

import filelock
from filelock import FileLock, BaseFileLock

from pipkin import UserError
from pipkin.adapters import Adapter
from pipkin.proxy import PipkinProxy
from pipkin.util import (
    get_base_executable,
    get_user_cache_dir,
    get_venv_executable,
    get_venv_site_packages_path,
    parse_dist_info_dir_name,
)

logger = getLogger(__name__)

PRIVATE_PIP_VERSION = "22.0.*"
INITIAL_VENV_DISTS = ["pip", "setuptools", "pkg_resources"]
INITIAL_VENV_FILES = ["easy_install.py"]


class Session:
    """
    Session allows performing several commands on a target with a single device => venv
    synchronization.
    """

    def __init__(self, adapter: Adapter):
        self._adapter = adapter
        self._venv_lock, self._venv_dir = self._prepare_venv()
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

        self._invoke_pip_with_pipkin_proxy(
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

        self._invoke_pip_with_pipkin_proxy(
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

    def close(self) -> None:
        self._venv_lock.release()

    def _commit_changes(
        self, dists_before: Dict[str, float], dists_after: Dict[str, float]
    ) -> None:
        removed_meta_dirs = {name for name in dists_before if name not in dists_after}
        new_meta_dirs = {name for name in dists_after if name not in dists_before}
        changed_meta_dirs = {
            name
            for name in dists_after
            if name in dists_before and dists_after[name] != dists_before[name]
        }

        for meta_dir in removed_meta_dirs | changed_meta_dirs:
            self._adapter.remove_dist_by_meta_dir(meta_dir)

        for meta_dir in removed_meta_dirs | changed_meta_dirs:
            self._upload_dist_by_meta_dir(meta_dir)

    def _upload_dist_by_meta_dir(self, meta_dir_name) -> None:
        record_path = os.path.join(self._get_venv_site_packages_path(), meta_dir_name, "RECORD")
        assert os.path.exists(record_path)

        with open(record_path) as fp:
            for line in fp.read().splitlines():
                rel_path = line.split(",")[0]
                full_path = os.path.normpath(os.path.join(self._get_venv_site_packages_path(), rel_path))
                self._adapter.upload_to_target_dir(full_path, rel_path)


    def _prepare_venv(self) -> Tuple[BaseFileLock, str]:
        # 1. create sample venv (if doesn't exist yet)
        # 2. clone the venv for this session (Too slow in Windows ???)
        # https://github.com/edwardgeorge/virtualenv-clone/blob/master/clonevirtualenv.py
        path = self._compute_venv_path()
        if not os.path.exists(path):
            logger.info("Start preparing working environment ...")
            venv.main([path])
            subprocess.check_call(
                [
                    get_venv_executable(self._venv_dir),
                    "-I",
                    "-m",
                    "pip",
                    "--disable-pip-version-check",
                    "--no-warn-script-location",
                    "install",
                    "--upgrade",
                    f"pip=={PRIVATE_PIP_VERSION}",
                ]
            )
            logger.info("Done preparing working environment.\n")

        lock = FileLock(os.path.join("pipkin.lock"))
        try:
            lock.acquire(timeout=0)
        except filelock.Timeout:
            raise UserError(
                "Could not get exclusive access to the working environment. "
                "Is there another pipkin instance running?"
            )

        self._clear_venv()
        self._populate_venv()

        return lock, path

    def _get_venv_site_packages_path(self) -> str:
        return get_venv_site_packages_path(self._venv_dir)

    def _clear_venv(self) -> None:
        sp_path = self._get_venv_site_packages_path()
        for name in os.listdir(sp_path):
            full_path = os.path.join(sp_path, name)
            if self._is_initial_venv_item(name):
                continue
            elif os.path.isfile(full_path):
                os.remove(full_path)
            else:
                assert os.path.isdir(full_path)
                shutil.rmtree(full_path)

    def _populate_venv(self) -> None:
        meta_dirs = self._adapter.list_meta_dirs()
        for name in meta_dirs:
            assert name.endswith(".dist-info")
            self._prepare_dummy_dist(name)

    def _prepare_dummy_dist(self, meta_dir_name: str) -> None:
        sp_path = self._get_venv_site_packages_path()
        meta_path = os.path.join(sp_path, meta_dir_name)
        os.mkdir(meta_path, 0o755)

        for name in ["METADATA"]:
            content = self._adapter.read_meta_file(
                meta_dir_name + "/" + name
            )
            with open(os.path.join(meta_path, name), "bw") as fp:
                fp.write(content)

        with open(os.path.join(meta_path, "INSTALLER"), "w") as fp:
            fp.write("pip\n")

        # create dummy RECORD
        with open(os.path.join(meta_path, "RECORD"), "w") as fp:
            for name in ["METADATA", "INSTALLER", "RECORD"]:
                fp.write(f"{meta_dir_name}/{name},,\n")

    def _check_create_dummy(self, meta_dir_name: str, rel_path: str) -> None:
        # TODO: remove
        target_path = os.path.normpath(os.path.join(meta_dir_name, rel_path))
        if os.path.exists(target_path):
            return
        dir_name = os.path.dirname(target_path)
        os.makedirs(dir_name, 0o755, exist_ok=True)
        with open(target_path, "bw"):
            pass


    def _compute_venv_path(self) -> str:
        try:
            # try to share the pip-execution-venv among all pipkin-running-venvs created from
            # same base executable
            exe = get_base_executable()
        except:
            exe = sys.executable

        hash = hashlib.md5(str((exe, sys.version_info[0:2])).encode("utf-8")).hexdigest()
        return os.path.join(get_user_cache_dir(), "pipkin", hash)

    def _is_initial_venv_item(self, name: str) -> bool:
        return (
            name in INITIAL_VENV_FILES
            or name in INITIAL_VENV_DISTS
            or name.endswith(".dist-info")
            and name.split("-")[0] in INITIAL_VENV_DISTS
        )

    def _get_venv_state_all_files(self, root: str = None) -> Dict[str, float]:
        # TODO: remove if not used
        """Returns mapping from file names to modification timestamps"""
        if root is None:
            root = self._get_venv_site_packages_path()

        result = {}
        for item_name in os.listdir(root):
            if self._is_initial_venv_item(item_name):
                continue

            full_path = os.path.join(root, item_name)
            if os.path.isfile(full_path):
                result[full_path] = os.stat(full_path).st_mtime
            else:
                assert os.path.isdir(full_path)
                result.update(self._get_venv_state(full_path))

        return result

    def _get_venv_state(self, root: str = None) -> Dict[str, float]:
        """Returns mapping from meta_dir names to modification timestamps of METADATA files"""
        if root is None:
            root = self._get_venv_site_packages_path()

        result = {}
        for item_name in os.listdir(root):
            if self._is_initial_venv_item(item_name):
                continue

            if item_name.endswith(".dist-info"):
                metadata_full_path = os.path.join(root, item_name, "METADATA")
                assert os.path.exists(metadata_full_path)
                result[item_name] = os.stat(metadata_full_path).st_mtime

        return result

    def _invoke_pip_with_pipkin_proxy(
        self,
        pip_args: List[str],
        prefer_mp_org: Optional[bool],
        index_url: Optional[str],
        extra_index_urls: List[str],
    ):
        proxy = PipkinProxy(prefer_mp_org, index_url, extra_index_urls)
        logger.info("Using PipkinProxy at %s", proxy.get_index_url())
        try:
            self._invoke_pip(pip_args + ["--index-url", proxy.get_index_url()])
        finally:
            proxy.shutdown()

    def _invoke_pip(self, args: List[str]) -> None:
        pip_cmd = [
            get_venv_executable(self._venv_dir),
            "-I",
            "-m",
            "pip",
            "--disable-pip-version-check",
        ] + args
        logger.debug("Calling pip: %s", " ".join(shlex.quote(arg) for arg in pip_cmd))
        subprocess.check_call(pip_cmd)
