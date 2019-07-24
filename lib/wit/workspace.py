#!/usr/bin/env python3

import sys
import shutil
from pathlib import Path
from pprint import pformat
from .manifest import Manifest
from .dependency import Dependency
from .lock import LockFile
from .common import WitUserError, error, passbyval
from .witlogger import getLogger

log = getLogger()


# TODO: hide the stacktrace when not debugging
class NotAncestorError(WitUserError):
    def __init__(self, orig_child: Dependency, old_child: Dependency):
        self.orig_child = orig_child
        self.old_child = old_child

    def __str__(self):
        # orig is later in time because we traverse the queue backwards in time
        assert self.orig_child.name == self.old_child.name
        child_name = self.old_child.name

        orig_parent = self.orig_child.dependents[0].dependents[0]
        old_parent = self.old_child.dependents[0].dependents[0]
        return ("\n\nAncestry error:\n"
                "'{orig_parent_name}' and '{old_parent_name}' both depend on '{child_name}':\n"
                "    {orig_parent_tag} depends on "
                "{orig_child_tag}\n"
                "    {old_parent_tag} depends on "
                "{old_child_tag}\n\n"
                "Although {orig_child_tag} is newer than "
                "{old_child_tag},\n{orig_child_tag} is not "
                "a descendent of {old_child_tag}.\n\n"
                "Therefore, there is no guarantee that "
                "the dependee needed by {old_parent_tag} will be satisfied "
                "by the dependee needed by {orig_parent_tag}."
                "".format(
                    orig_parent_name=orig_parent.name,
                    old_parent_name=old_parent.name,

                    orig_parent_tag=orig_parent.tag(),
                    old_parent_tag=old_parent.tag(),

                    child_name=child_name,
                    orig_child_tag=self.orig_child.tag(),
                    old_child_tag=self.old_child.tag(),
                ))


class PackageNotInWorkspaceError(WitUserError):
    pass


class WorkSpace:
    MANIFEST = "wit-workspace.json"
    LOCK = "wit-lock.json"

    def __init__(self, root, repo_paths):
        self.root = root
        self.repo_paths = repo_paths
        self.manifest = self._load_manifest()
        self.lock = self._load_lockfile()

    def tag(self):
        return "[root]"

    def get_id(self):
        return "root"

    @classmethod
    def create(cls, name, repo_paths):
        """Create a wit workspace on disk with the appropriate json files"""
        root = Path.cwd() / name
        manifest_path = cls._manifest_path(root)
        if root.exists():
            log.info("Using existing directory [{}]".format(str(root)))

            if manifest_path.exists():
                log.error("Manifest file [{}] already exists.".format(manifest_path))
                sys.exit(1)
        else:
            log.info("Creating new workspace [{}]".format(str(root)))
            try:
                root.mkdir()
            except Exception as e:
                log.error("Unable to create workspace [{}]: {}".format(str(root), e))
                sys.exit(1)

        dotwit = root/'.wit'
        if dotwit.exists():
            # we could keep the old cached repos, but if the user is explicitly re-initing,
            # they probably want a 100% clean slate
            shutil.rmtree(str(dotwit))
        dotwit.mkdir()

        manifest = Manifest([])
        manifest.write(manifest_path)

        lockfile = LockFile([])
        lockfile.write(cls._lockfile_path(root))

        return WorkSpace(root, repo_paths)

    def _load_manifest(self):
        return Manifest.read_manifest(self.manifest_path())

    def _load_lockfile(self):
        return LockFile.read(self.lockfile_path())

    @classmethod
    def _manifest_path(cls, root):
        return root / cls.MANIFEST

    def manifest_path(self):
        return WorkSpace._manifest_path(self.root)

    @classmethod
    def _lockfile_path(cls, path):
        return path / cls.LOCK

    def lockfile_path(self):
        return WorkSpace._lockfile_path(self.root)

    @staticmethod
    def find(start, repo_paths):
        cwd = start.resolve()
        for p in ([cwd] + list(cwd.parents)):
            manifest_path = WorkSpace._manifest_path(p)
            log.debug("Checking [{}]".format(manifest_path))
            if Path(manifest_path).is_file():
                log.debug("Found workspace at [{}]".format(p))
                return WorkSpace(p, repo_paths)

        raise FileNotFoundError("Couldn't find workspace file")

    def resolve(self, download=False):
        source_map, packages, queue, errors = \
            self.resolve_deps(self.root, self.repo_paths, download, {}, {}, [], [])

        while queue:
            commit_time, dep = queue.pop()
            log.debug("{} {}".format(commit_time, dep))

            name = dep.package.name
            if name in packages and packages[name].revision is not None:
                package = packages[name]
                if not package.repo.is_ancestor(dep.specified_revision, package.revision):
                    errors.append(NotAncestorError(package.dependents[0], dep))
                continue

            packages[dep.name] = dep.package
            packages[dep.name].revision = dep.resolved_rev()
            packages[dep.name].set_source(dep.source)

            source_map, packages, queue, errors = \
                dep.resolve_deps(self.root, self.repo_paths, download,
                                 source_map, packages, queue, errors)
        return packages, errors

    @passbyval
    def resolve_deps(self, wsroot, repo_paths, download, source_map, packages, queue, errors):
        for dep in self.manifest.dependencies:
            dep.load(packages, repo_paths, wsroot, download)

            source_map[dep.name] = dep.source

            commit_time = dep.get_commit_time()
            queue.append((commit_time, dep))

        queue.sort(key=lambda tup: tup[0])

        return source_map, packages, queue, []

    def checkout(self, packages):
        lock_packages = []
        for name in packages:
            package = packages[name]
            package.checkout(self.root)
            lock_packages.append(package)

        new_lock = LockFile(lock_packages)
        new_lock_path = WorkSpace._lockfile_path(self.root)
        new_lock.write(new_lock_path)
        self.lock = new_lock

    def add_dependency(self, tag) -> None:
        """ Resolve a dependency then add it to the wit-workspace.json """
        from .main import dependency_from_tag
        dep = dependency_from_tag(self.root, tag)

        if self.manifest.contains_dependency(dep.name):
            error("Manifest already contains package {}".format(dep.name))

        packages = {pkg.name: pkg for pkg in self.lock.packages}
        dep.load(packages, self.repo_paths, self.root, True)
        dep.package.revision = dep.resolved_rev()

        assert dep.package.repo is not None

        self.manifest.add_dependency(dep)

        log.debug('my manifest_path = {}'.format(self.manifest_path()))
        self.manifest.write(self.manifest_path())

        log.info("The workspace now depends on '{}'".format(dep.package.tag()))

    def update_dependency(self, tag) -> None:
        # init requested Dependency
        from .main import dependency_from_tag
        req_dep = dependency_from_tag(self.root, tag)

        manifest_dep = self.manifest.get_dependency(req_dep.name)

        # check if the package is missing from the wit-workspace.json
        if manifest_dep is None:
            log.error("Package {} not in wit-workspace.json".format(req_dep.name))
            log.error("Did you mean to run 'wit add-pkg' or 'wit update-dep'?")
            sys.exit(1)

        # load their Package
        packages = {pkg.name: pkg for pkg in self.lock.packages}
        req_dep.load(packages, self.repo_paths, self.root, True)

        manifest_dep.load(packages, self.repo_paths, self.root, True)

        # check if the dependency is missing from disk
        if req_dep.package.repo is None:
            msg = "Cannot update package '{}'".format(req_dep.name)
            if self.lock.contains_package(req_dep.name):
                msg += (":\nAlthough '{}' exists (according to the wit-lock.json), "
                        "it has not been cloned to the root workspace.").format(req_dep.name)
            else:
                msg += "because it does not exist in the workspace."
            raise PackageNotInWorkspaceError(msg)

        req_resolved_rev = req_dep.resolved_rev()

        # compare the requested revision to the revision in the wit-workspace.json
        if manifest_dep.resolved_rev() == req_resolved_rev:
            log.warn("Updating '{}' to the same revision it already is!".format(req_dep.name))

        self.manifest.replace_dependency(req_dep)
        self.manifest.write(self.manifest_path())

        log.info("The workspace now depends on '{}'".format(req_dep.package.tag()))

        # if we differ from the lockfile, tell the user to update
        if not self.lock.get_package(req_dep.name).revision == req_resolved_rev:
            log.info("Don't forget to run 'wit update'!")

    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
