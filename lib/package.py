#!/usr/bin/env python3

from pathlib import Path
import re
import shutil
from lib.gitrepo import GitRepo
from lib.witlogger import getLogger

log = getLogger()


class Package:

    def __init__(self, name, source, revision):
        """Create a package, cloning it to the .wit folder"""
        self.name = name
        self.source = source
        self.theory_revision = revision or "HEAD"

        self.dependents = []

    def __key(self):
        return (self.source, self.theory_revision, self.name)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()

    def add_dependent(self, dep):
        if dep not in self.dependents:
            self.dependents.append(dep)

    def load(self, wsroot, repo_paths, force_root, rev=None):
        """Load the package for a Dependency.
        If a suitable package already exists in the WorkSpace, load that.
        Otherwise, clone into `.wit`.

        force_root forces the repo to be cloned into WorkSpace.root
        """

        revision = rev or self.theory_revision
        non_hash = len(revision) != 40  # in case our remtoe pointer changed

        # Check if we are already checked out
        self.in_root = (wsroot/self.name).exists() or force_root
        if self.in_root:
            repo_root = wsroot
        else:
            repo_root = wsroot/'.wit'

        self.repo = GitRepo(self.source, self.theory_revision, self.name, repo_root)
        self.find_source(repo_paths)

        exists = Path(self.repo.get_path()).exists()
        if not exists or not self.repo.has_commit(revision) or non_hash:
            if not exists and not force_root:
                log.info("Repairing {}, run `wit update` to checkout again".format(self.name))
            self.repo.clone_or_fetch()

        self.theory_revision = self.repo.get_commit(self.theory_revision)

    def is_ancestor(self, other_commit):
        return self.repo.is_ancestor(other_commit, self.theory_revision)

    def find_source(self, repo_paths):
        for path in repo_paths:
            tmp_path = str(Path(path) / self.name)
            if GitRepo.is_git_repo(tmp_path):
                self.source = tmp_path
                self.repo.source = tmp_path
                return

    def get_dependencies(self):
        manifest = self.repo.read_manifest_from_commit(self.theory_revision)
        deps = manifest.packages
        for dep in deps:
            dep.add_dependent(self)
        return deps

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.theory_revision,
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
        self.repo.checkout()

    def move_to_root(self, wsroot):
        self.repo.set_wsroot(wsroot)
        self.repo.name = self.name  # in case we got renamed

    def __repr__(self):
        return "Pkg({})".format(self.tag())

    def tag(self):
        return "{}::{}".format(self.name, self.theory_revision[:8])

    def get_id(self):
        return "pkg_"+re.sub(r"([^\w\d])", "_", self.tag())

    def status(self, lock):
        if lock.contains_package(self.name):
            if not self.in_root:
                return "\033[93m(will be repaired)\033[m"
            elif self.theory_revision != self.repo.get_latest_commit():
                return "\033[35m(will be checked out to {})\033[m".format(self.theory_revision[:8])
        else:
            if not self.in_root:
                return "\033[92m(will be added to workspace and lockfile)\033[m"
            else:
                return "\033[31m(will be added to lockfile)\033[m"
