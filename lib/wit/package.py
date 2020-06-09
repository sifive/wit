#!/usr/bin/env python3

from pathlib import Path
import re
import os
import shutil
from .gitrepo import GitRepo, BadSource
from .repo_entries import RepoEntry
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

    def set_source(self, source):
        self.source = self.resolve_source(source)

    def short_revision(self):
        if self.revision:
            if self.repo.is_tag(self.revision):
                return self.revision
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

    def load(self, wsroot, download, source=None, revision=None):
        """Connect a Package to a GitRepo on disk.

        If found, self.repo will be updated.
        """

        source = self.resolve_source(source) or self.resolve_source(self.source)
        revision = revision or self.revision

        assert revision is not None, "Cannot load repo for unknown commit."
        assert source is not None, "Cannot load repo for unknown source."

        # Check if we are already checked out
        self.in_root = (wsroot/self.name).exists()
        if self.in_root:
            repo_root = wsroot
        else:
            repo_root = wsroot/'.wit'
            if not repo_root.exists():
                os.mkdir(str(repo_root))

        self.repo = GitRepo(self.name, repo_root)

        # we carefully use Python's boolean expression evalution short-circuiting
        # to avoid calling has_commit if the repo does not exist
        if (not self.repo.path.exists()
                or not self.repo.has_commit(revision)
                or not (self.repo.is_hash(revision) or self.repo.is_tag(revision))):
            if not download:
                self.repo = None
                return
            try:
                self.repo.download(source, self.name)
            except BadSource:
                self.repo = None
                raise

    def is_ancestor(self, other_commit):
        return self.repo.is_ancestor(other_commit, self.revision)

    def resolve_source(self, source):
        for path in self.repo_paths:
            tmp_path = str(Path(path) / self.name)
            if GitRepo.is_git_repo(tmp_path):
                return tmp_path
        return source

    def get_dependencies(self):
        from .dependency import Dependency
        entries = self.repo.repo_entries_from_commit(self.revision)
        deps = [Dependency.from_repo_entry(e) for e in entries]
        for dep in deps:
            dep.add_dependent(self)
        return deps

    def to_repo_entry(self):
        return RepoEntry(self.name, self.revision, self.source)

    @staticmethod
    def from_repo_entry(entry):
        pkg = Package(entry.checkout_path, [])
        pkg.set_source(entry.remote_url)
        pkg.revision = entry.revision
        return pkg

    # this is in Package because update_dependency is in Package
    # it could be confusing to keep the two functions separate
    def add_dependency(self):
        """Change the wit-manifest.json to add a dependency."""
        pass

    def checkout(self, wsroot):
        """Move to root directory and checkout"""
        current_origin = self.repo.get_remote()
        wanted_origin = self.source
        if current_origin != wanted_origin:
            if self.repo.path.parts[-2] == '.wit':
                self.repo.set_origin(self.source)
            else:
                log.warn("Package '{}' wants a different git remote origin.\n"
                         "Origin is currently:\n  {}\n"
                         "Package '{}' wants origin:\n  {}\n"
                         "Please manually update the origin with:\n"
                         "  git -C {} \\\n    remote set-url origin {}"
                         "".format(self.name, current_origin, self.name,
                                   wanted_origin, self.repo.path, wanted_origin))
        assert self.repo.name == self.name
        shutil.move(str(self.repo.path), str(wsroot/self.repo.name))
        self.move_to_root(wsroot)
        self.repo.checkout(self.revision)

    def find_matching_dependent(self):
        """
        Finds first dependent that has the same revision as the resolved package
        """
        if self.revision is None:
            return None
        for dep in self.dependents:
            if dep.specified_revision == self.revision:
                return dep

    def dependents_have_common_ancestor(self):
        commits = [d.specified_revision for d in self.dependents]
        assert self.repo is not None
        return self.repo.have_common_ancestor(commits)

    def move_to_root(self, wsroot: Path):
        assert self.repo.name == self.name
        self.repo.path = wsroot/self.repo.name

    def __repr__(self):
        return "Pkg({})".format(self.id())

    def id(self):
        return "{}::{}".format(self.name, self.short_revision())

    def get_id(self):
        return "pkg_"+re.sub(r"([^\w\d])", "_", self.id())

    def status(self, lock):
        if lock.contains_package(self.name):
            if self.repo and self.revision != self.repo.get_head_commit():
                return "\033[35m(will be checked out to {})\033[m".format(
                    self.short_revision())
        else:
            if not self.in_root:
                return "\033[92m(will be added to workspace and lockfile)\033[m"
            else:
                return "\033[31m(will be added to lockfile)\033[m"
