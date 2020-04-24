#!/usr/bin/env python3

from .gitrepo import GitRepo
from typing import Optional
from .witlogger import getLogger
from .repo_entries import RepoEntries

log = getLogger()


class LockFile:
    """
    Common class for the description of package dependencies and a workspace
    """

    def __init__(self, packages=[]):
        self.packages = packages

    def get_package(self, name: str) -> Optional[GitRepo]:
        for p in self.packages:
            if p.name == name:
                return p
        return None

    def contains_package(self, name: str) -> bool:
        return self.get_package(name) is not None

    def add_package(self, package):
        self.packages.append(package)

    def write(self, path):
        log.debug("Writing lock file to {}".format(path))
        contents = [p.to_repo_entry() for p in self.packages]
        RepoEntries.write(path, contents)

    @staticmethod
    def read(path):
        log.debug("Reading lock file from {}".format(path))
        from .package import Package
        return LockFile([Package.from_repo_entry(x) for x in RepoEntries.read(path)])


if __name__ == '__main__':
    import doctest
    doctest.testmod()
