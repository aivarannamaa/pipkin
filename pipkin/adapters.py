from typing import Optional


class Adapter:
    def should_prefer_mp_org(self) -> bool:
        raise NotImplementedError()


def create_adapter(port: Optional[str]) -> Adapter:
    ...
