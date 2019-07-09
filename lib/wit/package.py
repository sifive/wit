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
    """ Packages are the "winner" of several dependencies of the same name.
    These "winner" Packages are determined by WorkSpace.resolve and stored in the wit-lock.json
    """

    def __init__(self, name, repo_paths):
        """ Before we know which dependency "won," we need a Package object to
        link these same-named Dependencies together.

        This transitive state is indicated by Package.revision == None

        We need repo_paths here because we will use it to transform sources we need both for
        downloading repos while in the transitive state and for downloading the "winning" git repo
        """

        self.name = name
        self.source = None
        self.revision = None
        self.repo_paths = repo_paths

        self.repo = None
        self.dependents = []

    def short_revision(self):
        if self.revision:
            return self.repo.get_shortened_rev(self.revision)
        return None

    def __key(self):
        return (self.source, self.revision, self.name)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()

    def add_dependent(self, dep):
        if dep not in self.dependents:
            self.dependents.append(dep)

    def load_repo(self, wsroot, download=False, needed_commit=None):
        """Connect a Package to a GitRepo on disk.

        If found, self.repo will be updated.
        """

        needed_commit = needed_commit or self.revision

        if needed_commit is None:
            raise Exception("Cannot load repo for unknown commit.")

        # Check if we are already checked out
        self.in_root = (wsroot/self.name).exists()
        if self.in_root:
            repo_root = wsroot
        else:
            repo_root = wsroot/'.wit'
            if not repo_root.exists():
                os.mkdir(str(repo_root))

        self.repo = GitRepo(self.source, self.revision, self.name, repo_root)

        # we carefully use Python's boolean expression evalution short-circuiting
        # to avoid calling has_cmmit if the repo does not exist
        if (not self.repo.get_path().exists()
                or not self.repo.has_commit(needed_commit)
                or not self.repo.is_hash(needed_commit)):
            if not download:
                self.repo = None
                return
            self.repo.download()

    def is_ancestor(self, other_commit):
        return self.repo.is_ancestor(other_commit, self.revision)

    def set_source(self, source):
        self.source = self.resolve_source(source)

    def resolve_source(self, source):
        for path in self.repo_paths:
            tmp_path = str(Path(path) / self.name)
            if GitRepo.is_git_repo(tmp_path):
                return tmp_path
        return source

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
            'commit': self.revision,
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
        return "{}::{}".format(self.name, self.short_revision())

    def get_id(self):
        return "pkg_"+re.sub(r"([^\w\d])", "_", self.tag())

    def status(self, lock):
        if lock.contains_package(self.name):
            if self.repo and self.revision != self.repo.get_latest_commit():
                return "\033[35m(will be checked out to {})\033[m".format(
                    self.short_revision())
        else:
            if not self.in_root:
                return "\033[92m(will be added to workspace and lockfile)\033[m"
            else:
                return "\033[31m(will be added to lockfile)\033[m"
