import hashlib
import os.path
import shlex
import shutil
import subprocess
import sys
import venv
from logging import getLogger
from typing import Optional, List, Dict, Tuple

import filelock
from filelock import FileLock, BaseFileLock

from pipkin.adapters import Adapter
from pipkin.common import UserError
from pipkin.proxy import start_proxy
from pipkin.util import (
    get_base_executable,
    get_user_cache_dir,
    get_venv_executable,
    get_venv_site_packages_path,
    parse_meta_dir_name,
)

logger = getLogger(__name__)

PRIVATE_PIP_SPEC = "==22.0.*"
PRIVATE_WHEEL_SPEC = "==0.37.*"
INITIAL_VENV_DISTS = ["pip", "setuptools", "pkg_resources", "wheel"]
INITIAL_VENV_FILES = ["easy_install.py"]


class Session:
    def __init__(self, adapter: Adapter):
        self._adapter = adapter
        self._venv_lock, self._venv_dir = self._prepare_venv()

    def install(
        self,
        specs: Optional[List[str]] = None,
        requirement_files: Optional[List[str]] = None,
        constraint_files: Optional[List[str]] = None,
        pre: bool = False,
        no_deps: bool = False,
        no_mp_org: bool = False,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        no_index: bool = False,
        find_links: Optional[str] = None,
        target: Optional[str] = None,
        user: bool = False,
        upgrade: bool = False,
        upgrade_strategy: str = "only-if-needed",
        force_reinstall: bool = False,
        **_,
    ):

        args = ["install", "--no-compile"]

        if upgrade:
            args.append("--upgrade")
        if upgrade_strategy:
            args += ["--upgrade-strategy", upgrade_strategy]
        if force_reinstall:
            args.append("--force-reinstall")

        args += self._format_selection_args(
            specs=specs,
            requirement_files=requirement_files,
            constraint_files=constraint_files,
            pre=pre,
            no_deps=no_deps,
        )

        self._populate_venv()
        state_before = self._get_venv_state()
        self._invoke_pip_with_index_args(
            args,
            no_mp_org=no_mp_org,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
            no_index=no_index,
            find_links=find_links,
        )
        state_after = self._get_venv_state()

        removed_meta_dirs = {name for name in state_before if name not in state_after}
        assert not removed_meta_dirs

        new_meta_dirs = {name for name in state_after if name not in state_before}
        changed_meta_dirs = {
            name
            for name in state_after
            if name in state_before and state_after[name] != state_before[name]
        }

        if target:
            effective_target = target
        elif user:
            effective_target = self._adapter.get_user_packages_path()
        else:
            effective_target = self._adapter.get_default_target()

        for meta_dir in changed_meta_dirs:
            # if target is specified by --target or --user, then don't touch anything
            # besides corresponding directory, regardless of the sys.path and possible hiding
            dist_name, version = parse_meta_dir_name(meta_dir)
            if target:
                # pip doesn't remove old dist with --target unless --upgrade is given
                if upgrade:
                    self._adapter.remove_dist(dist_name=dist_name, target=target)
            elif user:
                self._adapter.remove_dist(
                    dist_name=dist_name, target=self._adapter.get_user_packages_path()
                )
            else:
                # remove the all installations of this dist, which would hide the new installation
                self._adapter.remove_dist(
                    dist_name=dist_name, target=effective_target, above_target=True
                )

        self._adapter.create_dir_if_doesnt_exist(effective_target)
        for meta_dir in new_meta_dirs | changed_meta_dirs:
            self._upload_dist_by_meta_dir(meta_dir, effective_target)

    def uninstall(
        self,
        packages: Optional[List[str]] = None,
        requirement_files: Optional[List[str]] = None,
        yes: bool = False,
        **_,
    ):
        args = ["uninstall"]
        if yes:
            args += ["--yes"]

        for rf in requirement_files or []:
            args += ["-r", rf]
        for package in packages or []:
            args.append(package)

        self._populate_venv()
        state_before = self._get_venv_state()
        self._invoke_pip(args)
        state_after = self._get_venv_state()

        removed_meta_dirs = {name for name in state_before if name not in state_after}
        for meta_dir_name in removed_meta_dirs:
            dist_name, version = parse_meta_dir_name(meta_dir_name)
            self._adapter.remove_dist(dist_name)

    def list(
        self,
        outdated: bool = False,
        uptodate: bool = False,
        not_required: bool = False,
        pre: bool = False,
        paths: Optional[List[str]] = None,
        user: bool = False,
        format: str = "columns",
        no_mp_org: Optional[bool] = False,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        no_index: bool = False,
        find_links: Optional[str] = None,
        excludes: Optional[List[str]] = None,
        **_,
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

        args += self._format_exclusion_args(excludes)

        self._populate_venv(paths=paths, user=user)

        self._invoke_pip_with_index_args(
            args,
            no_mp_org=no_mp_org,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
            no_index=no_index,
            find_links=find_links,
        )

    def show(self, packages: List[str], **_):
        self._populate_venv()
        self._invoke_pip(["show"] + packages)

    def freeze(
        self,
        paths: Optional[List[str]] = None,
        user: bool = False,
        excludes: Optional[List[str]] = None,
        **_,
    ):

        args = ["freeze"]

        args += self._format_exclusion_args(excludes)

        self._populate_venv(paths=paths, user=user)
        self._invoke_pip(args)

    def check(self, **_):
        self._populate_venv()
        self._invoke_pip(["check"])

    def download(
        self,
        specs: Optional[List[str]] = None,
        requirement_files: Optional[List[str]] = None,
        constraint_files: Optional[List[str]] = None,
        pre: bool = False,
        no_deps: bool = False,
        no_mp_org: bool = False,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        no_index: bool = False,
        find_links: Optional[str] = None,
        dest: Optional[str] = None,
        **_,
    ):
        args = ["download"]

        if dest:
            args += ["--dest", dest]

        args += self._format_selection_args(
            specs=specs,
            requirement_files=requirement_files,
            constraint_files=constraint_files,
            pre=pre,
            no_deps=no_deps,
        )

        self._populate_venv()
        self._invoke_pip_with_index_args(
            args,
            no_mp_org=no_mp_org,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
            no_index=no_index,
            find_links=find_links,
        )

    def wheel(
        self,
        specs: Optional[List[str]] = None,
        requirement_files: Optional[List[str]] = None,
        constraint_files: Optional[List[str]] = None,
        pre: bool = False,
        no_deps: bool = False,
        no_mp_org: bool = False,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        no_index: bool = False,
        find_links: Optional[str] = None,
        wheel_dir: Optional[str] = None,
        **_,
    ):
        args = ["wheel"]

        if wheel_dir:
            args += ["--wheel-dir", wheel_dir]

        args += self._format_selection_args(
            specs=specs,
            requirement_files=requirement_files,
            constraint_files=constraint_files,
            pre=pre,
            no_deps=no_deps,
        )

        self._populate_venv()
        self._invoke_pip_with_index_args(
            args,
            no_mp_org=no_mp_org,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
            no_index=no_index,
            find_links=find_links,
        )

    def cache(self, cache_command: str, **_) -> None:
        self._invoke_pip(["cache", cache_command])

        if cache_command == "purge":
            self.close()
            for name in os.listdir(self._get_workspaces_dir()):
                full_path = os.path.join(self._get_workspaces_dir(), name)
                shutil.rmtree(full_path)

    def close(self) -> None:
        # self._clear_venv()
        self._venv_lock.release()

    def _format_exclusion_args(self, excludes: Optional[List[str]]) -> List[str]:
        args = []
        for exclude in (excludes or []) + ["pip", "pkg_resources", "setuptools", "wheel"]:
            args += ["--exclude", exclude]

        return args

    def _format_selection_args(
        self,
        specs: Optional[List[str]],
        requirement_files: Optional[List[str]],
        constraint_files: Optional[List[str]],
        pre: bool,
        no_deps: bool,
    ):
        args = []

        for path in requirement_files or []:
            args += ["-r", path]
        for path in constraint_files or []:
            args += ["-c", path]

        if no_deps:
            args.append("--no-deps")
        if pre:
            args.append("--pre")

        args += specs or []

        return args

    def _upload_dist_by_meta_dir(self, meta_dir_name: str, target: str) -> None:
        record_path = os.path.join(self._get_venv_site_packages_path(), meta_dir_name, "RECORD")
        assert os.path.exists(record_path)

        with open(record_path) as fp:
            record_lines = fp.read().splitlines()

        ensured_dirs = {target}

        for line in record_lines:
            rel_path = line.split(",")[0]

            # don't consider files installed to eg. bin-directory
            if rel_path.startswith(".."):
                continue

            # TODO: skip some meta files

            full_path = os.path.normpath(
                os.path.join(self._get_venv_site_packages_path(), rel_path)
            )

            full_device_path = self._adapter.join_path(target, rel_path)
            device_dir_name, _ = self._adapter.split_dir_and_basename(full_device_path)
            if device_dir_name not in ensured_dirs:
                self._adapter.create_dir_if_doesnt_exist(device_dir_name)
                ensured_dirs.add(device_dir_name)

            with open(full_path, "rb") as fp:
                content = fp.read()

            # TODO: simplify METADATA and RECORD

            self._adapter.write_file(full_device_path, content)

    def _prepare_venv(self) -> Tuple[BaseFileLock, str]:
        # 1. create sample venv (if doesn't exist yet)
        # 2. clone the venv for this session (Too slow in Windows ???)
        # https://github.com/edwardgeorge/virtualenv-clone/blob/master/clonevirtualenv.py
        path = self._compute_venv_path()
        if not os.path.exists(path):
            logger.info("Start preparing working environment at %s ...", path)
            venv.main([path])
            subprocess.check_call(
                [
                    get_venv_executable(path),
                    "-I",
                    "-m",
                    "pip",
                    "--disable-pip-version-check",
                    "install",
                    "--no-warn-script-location",
                    "--upgrade",
                    f"pip{PRIVATE_PIP_SPEC}",
                    f"wheel{PRIVATE_WHEEL_SPEC}",
                ]
            )
            logger.info("Done preparing working environment.")
        else:
            logger.debug("Using existing working environment at %s", path)

        lock = FileLock(os.path.join(path, "pipkin.lock"))
        try:
            lock.acquire(timeout=0)
        except filelock.Timeout:
            raise UserError(
                "Could not get exclusive access to the working environment. "
                "Is there another pipkin instance running?"
            )

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

    def _populate_venv(self, paths: Optional[List[str]] = None, user: bool = False) -> None:
        """paths and user should be used only with list and freeze commands"""
        assert not (paths and user)
        if user:
            effective_paths = [self._adapter.get_user_packages_path()]
        else:
            effective_paths = paths
        self._clear_venv()
        dist_infos = self._adapter.list_dists(effective_paths)
        for name in dist_infos:
            meta_dir_name, original_path = dist_infos[name]
            self._prepare_dummy_dist(meta_dir_name, original_path)

    def _prepare_dummy_dist(self, meta_dir_name: str, original_path: str) -> None:
        sp_path = self._get_venv_site_packages_path()
        meta_path = os.path.join(sp_path, meta_dir_name)
        os.mkdir(meta_path, 0o755)

        for name in ["METADATA"]:
            content = self._read_dist_meta_file(meta_dir_name, name, original_path)
            with open(os.path.join(meta_path, name), "bw") as fp:
                fp.write(content)

        with open(os.path.join(meta_path, "INSTALLER"), "w") as fp:
            fp.write("pip\n")

        # create dummy RECORD
        with open(os.path.join(meta_path, "RECORD"), "w") as fp:
            for name in ["METADATA", "INSTALLER", "RECORD"]:
                fp.write(f"{meta_dir_name}/{name},,\n")

    def _read_dist_meta_file(
        self, meta_dir_name: str, file_name: str, original_container_path: str
    ) -> bytes:
        # TODO: add cache
        path = self._adapter.join_path(original_container_path, meta_dir_name, file_name)
        return self._adapter.read_file(path)

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

        venv_name = hashlib.md5(str((exe, sys.version_info[0:2])).encode("utf-8")).hexdigest()
        return os.path.join(self._get_workspaces_dir(), venv_name)

    def _get_workspaces_dir(self) -> str:
        return os.path.join(self._get_pipkin_cache_dir(), "workspaces")

    def _get_pipkin_cache_dir(self) -> str:
        result = os.path.join(get_user_cache_dir(), "pipkin")
        if sys.platform == "win32":
            # Windows doesn't have separate user cache dir
            result = os.path.join(result, "cache")
        return result

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

    def _invoke_pip_with_index_args(
        self,
        pip_args: List[str],
        no_mp_org: bool,
        index_url: str,
        extra_index_urls: List[str],
        no_index: bool,
        find_links: Optional[str],
    ):

        if no_index:
            assert find_links
            self._invoke_pip(pip_args + ["--no-index", "--find-links", find_links])
        else:
            proxy = start_proxy(no_mp_org, index_url, extra_index_urls)
            logger.info("Using PipkinProxy at %s", proxy.get_index_url())

            index_args = ["--index-url", proxy.get_index_url()]
            if find_links:
                index_args += ["--find-links", find_links]

            try:
                self._invoke_pip(pip_args + index_args)
            finally:
                proxy.shutdown()

    def _invoke_pip(self, args: List[str]) -> None:
        pip_cmd = [
            get_venv_executable(self._venv_dir),
            "-I",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--trusted-host",
            "127.0.0.1",
        ] + args
        logger.debug("Calling pip: %s", " ".join(shlex.quote(arg) for arg in pip_cmd))

        env = {key: os.environ[key] for key in os.environ if not key.startswith("PIP_")}
        env["PIP_CACHE_DIR"] = self._get_pipkin_cache_dir()

        subprocess.check_call(pip_cmd, env=env)
