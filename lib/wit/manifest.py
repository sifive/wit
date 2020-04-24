#!/usr/bin/env python3

from pathlib import Path
from .witlogger import getLogger
from .repo_entries import RepoEntries

log = getLogger()


# TODO
# Should this actually be shared between package manifests and workspace descriptions?
# Should we use different datastructures?
class Manifest:
    """
    Common class for the description of package dependencies and a workspace
    """

    def __init__(self, dependencies):
        self.dependencies = dependencies

    def get_dependency(self, name: str):
        for d in self.dependencies:
            if d.name == name:
                return d
        return None

    def contains_dependency(self, name: str) -> bool:
        return self.get_dependency(name) is not None

    def add_dependency(self, dep):
        resolved = dep.resolved()
        log.debug("Adding to manifest: {}".format(resolved))
        self.dependencies.append(resolved)

    def replace_dependency(self, dep) -> None:
        newdeps = []
        found = False
        for d in self.dependencies:
            if d.name == dep.name:
                resolved = dep.resolved()
                log.debug("New replace dep: {}".format(resolved))
                newdeps.append(resolved)
                found = True
            else:
                newdeps.append(d)
        assert found, \
            "Trying to update '{}' but it doesn't exist in manifest!".format(dep.name)
        self.dependencies = newdeps

    def write(self, path):
        contents = [d.to_repo_entry() for d in self.dependencies]
        RepoEntries.write(path, contents)

    @staticmethod
    def read_manifest(path, safe=False):
        if safe and not Path(path).exists():
            return Manifest([])
        entries = RepoEntries.read(path)

        from .dependency import Dependency
        deps = [Dependency.from_repo_entry(e) for e in entries]
        return Manifest(deps)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
