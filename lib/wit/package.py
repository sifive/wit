#!/usr/bin/env python3

from pathlib import Path
import re
import os
import shutil
from .gitrepo import GitRepo
from .witlogger import getLogger

log = getLogger()


class WitBug(Exception):
    pass


class Package:

    def __init__(self, name, source, unresolved_revision, repo_paths):
        """Create a package, cloning it to the .wit folder"""
        self.name = name
        self.source = source
        self.unresolved_revision = unresolved_revision or "HEAD"
        self.revision = None

        self.repo = None

        self.find_source(repo_paths)

        self.dependents = []

    def __key(self):
        return (self.source, self.unresolved_revision, self.name)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()

    def add_dependent(self, dep):
        if dep not in self.dependents:
            self.dependents.append(dep)

    def load_repo(self, wsroot, download=False):
        """Connect a Package to a GitRepo on disk.

        If found, self.repo will be updated
        and self.revision will be updated to the resolved self.unresolved_revision
        """

        non_hash = len(self.unresolved_revision) < 40

        if non_hash and not download:
            log.error("Cannot create a reproducible workspace!")
            raise WitBug("Cannot resolve '{}' without permission to download".format(non_hash))

        # Check if we are already checked out
        self.in_root = (wsroot/self.name).exists()
        if self.in_root:
            repo_root = wsroot
        else:
            repo_root = wsroot/'.wit'
            if not repo_root.exists():
                os.mkdir(str(repo_root))

        self.repo = GitRepo(self.source, self.unresolved_revision, self.name, repo_root)

        # we carefully use Python's boolean expression evalution short-circuiting
        # to avoid calling has_cmmit if the repo does not exist
        if (not self.repo.get_path().exists()
                or non_hash or not self.repo.has_commit(self.unresolved_revision)):
            if not download:
                self.repo = None
                return
            self.repo.clone_or_fetch()

        self.revision = self.repo.get_commit(self.unresolved_revision)

    def is_ancestor(self, other_commit):
        return self.repo.is_ancestor(other_commit, self.unresolved_revision)

    def find_source(self, repo_paths):
        for path in repo_paths:
            tmp_path = str(Path(path) / self.name)
            if GitRepo.is_git_repo(tmp_path):
                self.source = tmp_path
                if self.repo is not None:
                    self.repo.source = tmp_path
                return

    def get_dependencies(self):
        manifest = self.repo.read_manifest_from_commit(self.revision)
        deps = manifest.dependencies
        for dep in deps:
            dep.add_dependent(self)
        return deps

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.unresolved_revision,
        }

    # this is in Package because update_dependency is in Package
    # it could be confusing to keep the two functions separate
    def add_dependency(self):
        """Change the wit-manifest.json to add a dependency."""
        pass

    def checkout(self, wsroot):
        """Move to root directory and checkout"""
        shutil.move(str(self.repo.get_path()), str(wsroot/self.name))
        self.move_to_root(wsroot)
        self.repo.revision = self.revision
        self.repo.checkout()

    def move_to_root(self, wsroot):
        self.repo.set_wsroot(wsroot)
        self.repo.name = self.name  # in case we got renamed

    def __repr__(self):
        return "Pkg({})".format(self.tag())

    def tag(self):
        return "{}::{}".format(self.name, self.unresolved_revision[:8])

    def get_id(self):
        return "pkg_"+re.sub(r"([^\w\d])", "_", self.tag())

    def status(self, lock):
        if lock.contains_package(self.name):
            if not self.in_root:
                return "\033[93m(will be repaired)\033[m"
            elif self.revision != self.repo.get_latest_commit():
                return "\033[35m(will be checked out to {})\033[m".format(
                    self.unresolved_revision[:8])
        else:
            if not self.in_root:
                return "\033[92m(will be added to workspace and lockfile)\033[m"
            else:
                return "\033[31m(will be added to lockfile)\033[m"
