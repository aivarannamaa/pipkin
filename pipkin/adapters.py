from logging import getLogger
from typing import Optional, List, Dict, Tuple

from pipkin.util import parse_meta_dir_name

META_ENCODING = "utf-8"

logger = getLogger(__name__)


class Adapter:
    def get_user_packages_path(self) -> Optional[str]:
        """Unix / Windows ports return the location of user packages"""
        raise NotImplementedError()

    def get_default_target(self) -> str:
        """Installation location if neither --user nor --target is specified"""
        raise NotImplementedError()

    def list_dists(self, paths: List[str] = None) -> Dict[str, Tuple[str, str]]:
        """Return canonic names of the distributions mapped to their meta dir names and
        installation paths.

        If a distribution is installed to different sys.path locations, then return only the first one.
        """
        raise NotImplementedError()

    def upload_file(self, source_path: str, target_path: str) -> None:
        raise NotImplementedError()

    def remove_dist(
        self, dist_name: str, target: Optional[str] = None, above_target: bool = False
    ) -> None:
        """If target is given, then remove from this directory.
        If above_path, then also remove from sys.path dirs which would hide the package at path.
        Otherwise remove the first visible instance of the dist according to sys.path.
        """
        raise NotImplementedError()

    def read_file(self, path: str) -> bytes:
        raise NotImplementedError()

    def join_path(self, *parts: str) -> str:
        raise NotImplementedError()

    def compile(self, input_path: str, embedded_source_path: str, output_path: str) -> None:
        """
        TODO:
        """
        raise NotImplementedError()


class BaseAdapter(Adapter):
    def _get_sys_path(self) -> List[str]:
        raise NotImplementedError()

    def get_user_packages_path(self) -> Optional[str]:
        return None

    def get_default_target(self) -> str:
        for entry in self._get_sys_path():
            if "lib" in entry:
                return entry
        raise AssertionError("Could not determine default target")

    def list_dists(self, paths: List[str] = None) -> Dict[str, Tuple[str, str]]:
        if not paths:
            paths = [entry for entry in self._get_sys_path() if entry != ""]

        result = {}
        for path in paths:
            for dir_name in self._list_meta_dir_names(path):
                dist_name, _ = parse_meta_dir_name(dir_name)
                if dist_name not in result:
                    result[dist_name] = dir_name, path

        return result

    def _list_meta_dir_names(self, path: str, dist_name: Optional[str] = None) -> List[str]:
        """Return meta dir names from the indicated directory"""
        raise NotImplementedError()

    def remove_dist(
        self, dist_name: str, target: Optional[str] = None, above_target: bool = False
    ) -> None:
        could_remove = False
        if target:
            result = self._check_remove_dist_from_path(dist_name, target)
            could_remove = could_remove or result
            if above_target and target in self._get_sys_path():
                for entry in self._get_sys_path():
                    if entry == "":
                        continue
                    elif entry == target:
                        break
                    else:
                        result = self._check_remove_dist_from_path(dist_name, entry)
                        could_remove = could_remove or result

        else:
            for entry in self._get_sys_path():
                if entry == "":
                    continue
                else:
                    result = self._check_remove_dist_from_path(dist_name, entry)
                    could_remove = could_remove or result
                    if result:
                        break

        if not could_remove:
            logger.warning("Could not find %r for removing", dist_name)

    def _check_remove_dist_from_path(self, dist_name: str, path: str) -> bool:
        meta_dirs = self._list_meta_dir_names(path, dist_name)
        result = False
        for meta_dir_name in meta_dirs:
            self._remove_dist_by_meta_dir(path, meta_dir_name)
            result = True

        return result

    def _remove_dist_by_meta_dir(self, containing_dir: str, meta_dir_name: str) -> None:
        record_bytes = self._read_file(self.join_path(containing_dir, meta_dir_name, "RECORD"))
        record_lines = record_bytes.decode(META_ENCODING).splitlines()

        dirs = set()
        for line in record_lines:
            rel_path, _, _ = line.split(",")
            abs_path = self.join_path(containing_dir, rel_path)
            self._remove_file(abs_path)
            abs_dir, _ = abs_path.rsplit("/", maxsplit=1)
            dirs.add(abs_dir)

        for abs_dir in dirs:
            self._remove_dir_if_empty(abs_dir)

    def _remove_file(self, path: str):
        raise NotImplementedError()

    def _remove_dir_if_empty(self, path: str):
        raise NotImplementedError()

    def join_path(self, *parts: str) -> str:
        assert parts
        return "/".join(parts)


class DirAdapter(BaseAdapter):
    pass


class MountAdapter(Adapter):
    pass


def create_adapter(port: Optional[str]) -> Adapter:
    ...
