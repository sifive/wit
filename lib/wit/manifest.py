#!/usr/bin/env python3

import json
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

    @staticmethod
    def read_manifest(path, safe=False):
        if safe and not Path(path).exists():
            return Manifest([])
        content = json.loads(path.read_text())
        return Manifest.process_manifest(content, path)

    @staticmethod
    def process_manifest(json_content, location):
        # Fail if there are dependencies with the same name
        dep_names = [dep['name'] for dep in json_content]
        if len(dep_names) != len(set(dep_names)):
            dup = set([x for x in dep_names if dep_names.count(x) > 1])
            raise Exception("Two dependencies have the same name in '{}': {}".format(location, dup))

        # import here to prevent circular dependency
        from .dependency import manifest_item_to_dep
        dependencies = [manifest_item_to_dep(x) for x in json_content]
        return Manifest(dependencies)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
