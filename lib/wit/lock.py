#!/usr/bin/env python3

import json
import sys
from .gitrepo import GitRepo
from collections import OrderedDict
from typing import Optional
from .witlogger import getLogger
from .package import Package

log = getLogger()


# TODO
# Should we use different datastructures?
# The JSON file format slightly differs from manifest, why?
class LockFile:
    """
    Common class for the description of package dependencies and a workspace
    """

    WRITE_VERSION = "v0"

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

    def replace_package(self, package) -> None:
        newpkgs = []
        found = False
        for p in self.packages:
            if p.name == package.name:
                newpkgs.append(package)
                found = True
            else:
                newpkgs.append(p)
        assert found, \
            "Trying to update '{}' but it doesn't exist in manifest!".format(package.name)
        self.packages = newpkgs

    def write(self, path):
        log.debug("Writing lock file to {}".format(path))
        packages = OrderedDict((p.name, p.manifest()) for p in self.packages)
        ver = self.WRITE_VERSION
        if ver == 'v0':
            body = packages
        elif ver == 'v1':
            body = {
                "version": self.VERSION,
                "packages": packages,
            }
        else:
            raise NotImplementedError

        manifest_json = json.dumps(body, sort_keys=True, indent=4) + '\n'
        path.write_text(manifest_json)

    @staticmethod
    def read(path):
        log.debug("Reading lock file from {}".format(path))
        content = json.loads(path.read_text())
        return LockFile.process(content)

    @classmethod
    def process(cls, content):
        pkgs = []
        ver = LockFile.get_version(content)
        if ver == 'v0':
            pkgs = content
        elif ver == 'v1':
            pkgs = content['packages']
        else:
            log.error("Unable to read lockfile.")
            log.error("We are at {}, lockfile is at {}.".format(cls.VERSION, ver))
            log.error("Please update wit.")
            sys.exit(1)

        pkgs = [lockfile_item_to_pkg(x) for _, x in pkgs.items()]
        return LockFile(pkgs)

    @staticmethod
    def get_version(content):
        if 'version' not in content:
            return 'v0'
        else:
            return content['version']


if __name__ == '__main__':
    import doctest
    doctest.testmod()


def lockfile_item_to_pkg(item):
    return Package(item['name'], item.get('source'), item['commit'], [])
