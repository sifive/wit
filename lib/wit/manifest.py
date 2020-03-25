#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from .witlogger import getLogger

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
        contents = [p.manifest() for p in self.dependencies]
        manifest_json = json.dumps(contents, sort_keys=True, indent=4) + '\n'
        path.write_text(manifest_json)

    # FIXME It's maybe a little weird that we need wsroot but that's because
    # this method is being used for both wit-workspace and wit-manifest in
    # packages
    @staticmethod
    def read_manifest(path, safe=False):
        if safe and not Path(path).exists():
            return Manifest([])
        try:
          content = json.loads(path.read_text())
        except:
          log.fatal("Failed to parse " + str(path))
          sys.exit(1)
        return Manifest.process_manifest(content)

    @staticmethod
    def process_manifest(json_content):
        # import here to prevent circular dependency
        from .dependency import manifest_item_to_dep
        dependencies = [manifest_item_to_dep(x) for x in json_content]
        return Manifest(dependencies)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
