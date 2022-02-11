from typing import Optional, List, Dict


class Adapter:
    def get_user_packages_path(self) -> str:
        """Unix / Windows ports return the location of user packages"""

    def get_default_target(self) -> str:
        """Installation location if neither --user nor --target is specified"""

    def list_dists(self, paths: List[str] = None) -> Dict[str, str]:
        """Return canonic names of the distributions mapped to their versions.

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

    def read_dist_meta_file(self, dist_name: str, version: str, file_name: str) -> bytes:
        """Returns the content of the metadata file under meta dir of the given canonic dist_name.

        If the same dist is installed to different sys.path locations, then considers the first one.
        """

    def mpy_cross(self, input_path: str, embedded_source_path: str, output_path: str) -> None:
        """
        TODO:
        """


class MountAdapter(Adapter):
    pass


def create_adapter(port: Optional[str]) -> Adapter:
    ...
