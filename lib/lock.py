#!/usr/bin/env python3

import json
from lib.package import Package
from lib.gitrepo import GitRepo
from collections import OrderedDict
from typing import Optional
from lib.witlogger import getLogger

log = getLogger()


# TODO
# Should we use different datastructures?
# The JSON file format slightly differs from manifest, why?
class LockFile:
    """
    Common class for the description of package dependencies and a workspace
    """

    def __init__(self, packages=[]):
        # type: Package
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
        contents = OrderedDict((p.name, p.manifest()) for p in self.packages)
        manifest_json = json.dumps(contents, sort_keys=True, indent=4) + '\n'
        path.write_text(manifest_json)

    @staticmethod
    def read(ws, path):
        log.debug("Reading lock file from {}".format(path))
        content = json.loads(path.read_text())
        return LockFile.process(ws, content)

    @staticmethod
    def process(ws, content):
        from lib.dependency import manifest_item_to_dep
        deps = [manifest_item_to_dep(ws, x) for _, x in content.items()]
        for dep in deps:
            dep.load_package({}, False)
        packages = [dep.package for dep in deps]
        return LockFile(packages)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
