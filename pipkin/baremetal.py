from abc import ABC
from typing import Optional, List

from pipkin.adapters import BaseAdapter


class BareMetalConnection:
    pass


class BareMetalAdapter(BaseAdapter, ABC):
    def __init__(self, connection: BareMetalConnection):
        self.connection = connection

    def get_user_packages_path(self) -> Optional[str]:
        return None

    def read_file(self, path: str) -> bytes:
        ...

    def write_file(self, path: str, content: bytes) -> None:
        ...

    def remove_file(self, path: str) -> None:
        ...

    def remove_dir_if_empty(self, path: str) -> None:
        ...

    def create_dir_if_doesnt_exist(self, path: str) -> None:
        ...

    def list_meta_dir_names(self, path: str, dist_name: Optional[str] = None) -> List[str]:
        ...


class SerialAdapter(BareMetalAdapter):
    ...


class WebReplAdapter(BareMetalAdapter):
    ...


