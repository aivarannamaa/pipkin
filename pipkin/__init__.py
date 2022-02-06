from http.server import HTTPServer
from typing import Optional, List, Dict


class Target:
    pass

class Pipkin:
    def __init__(self, target: Target, proxy: HTTPServer):
        self._target = target
        self._proxy = proxy

    def install(self, specs: List[str],
                requirement_files: List[str]=None,
                constraint_files: List[str]=None,
                no_deps: bool = False,
                pre: bool = False,
                upgrade: bool = False,
                upgrade_strategy: str = "only-if-needed",
                force_reinstall: bool = False,
                ignore_installed: bool = False,
                no_warn_conflicts: bool = False,

                ):

        requirement_files = requirement_files or []
        constraint_files = constraint_files or []

        dists_before = self._get_dists_in_working_dir()

        specific_args = ["install"]
        for path in requirement_files:
            specific_args += ["-r", path]
        for path in constraint_files:
            specific_args += ["-c", path]
        for spec in specs:
            specific_args.append(spec)

        self._invoke_pip(specific_args)

        dists_after = self._get_dists_in_working_dir()
        self._commit_changes(dists_before, dists_after)

    def uninstall(self, specs: List[str],
                requirement_files: List[str]):

        dists_before = self._get_dists_in_working_dir()

        specific_args = ["uninstall"]
        for rf in requirement_files:
            specific_args += ["-r", rf]
        for spec in specs:
            specific_args.append(spec)

        self._invoke_pip(specific_args)

        dists_after = self._get_dists_in_working_dir()
        self._commit_changes(dists_before, dists_after)

    def _commit_changes(self, dists_before: Dict[str, int], dists_after: Dict[str, int]):
        ...

    def _get_dists_in_working_dir(self) -> Dict[str, int]:
        ...


    def _get_proxy_url(self) -> str:
        ...

    def _invoke_pip(self, specific_args):
        args = specific_args + ["--index-url", self._get_proxy_url()]
        ...

