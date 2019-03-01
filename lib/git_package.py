#!/usr/bin/env python3

import subprocess
from pathlib import Path
import logging
from pprint import pformat
import json
import sys
import lib.manifest

logging.basicConfig()
log = logging.getLogger('wit')


class GitPackage:
    """
    In memory data structure representing a Git repo package
    It may not be in sync with data structures on the file system
    Note there can be multiple GitPakage objects for the same GitRepo
    """
    PKG_DEPENDENCY_FILE = "wit-manifest.json"

    def __init__(self, commit, name, remote, dependencies=None):
        self.commit = commit
        self.name = name
        self.remote = remote
        self.dependencies = dependencies


    ## FIXME should we pass wsroot or should it be a member of the GitRepo?
    ## Should this be a separate mutation or part of normal construction?
    #def get_dependencies(self):
    #    proc = self._git_command("show", "{}:{}".format(self.revision, GitRepo.PKG_DEPENDENCY_FILE))
    #    if proc.returncode:
    #        log.info("No dependency file found in repo [{}:{}]".format(self.revision, self.path()))
    #        return []
    #    json_content = json.loads(proc.stdout)
    #    return lib.manifest.Manifest.process_manifest(wsroot, json_content).packages

    def add_dependency(self, package):
        path = self.manifest_path()
        lib.manifest.Manifest.read(path, safe=True).add_package(package).write(path)

    def manifest_path(self):
        return self.path() / self.PKG_DEPENDENCY_FILE

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.revision,
        }

    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
