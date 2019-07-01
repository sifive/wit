#!/usr/bin/env python3

import sys
from pathlib import Path
from pprint import pformat
from .gitrepo import GitRepo, GitCommitNotFound
from .manifest import Manifest
from .lock import LockFile
from .package import Package
from typing import List, Optional
from .common import error, WitUserError
from .witlogger import getLogger

log = getLogger()


# TODO: hide the stacktrace when not debugging
class NotAncestorError(Exception):
    def __init__(self, parent_a, child_a, parent_b, child_b):
        self.parent_a = parent_a
        self.child_a = child_a
        self.parent_b = parent_b
        self.child_b = child_b

    def __str__(self):
        assert self.child_a.name == self.child_b.name
        child_name = self.child_a.name

        if self.parent_a is None:
            parent_a_tag = "[root]"
            parent_a_name = "[root]"
        else:
            parent_a_tag = "{}::{}".format(self.parent_a.name, self.parent_a.short_revision())
            parent_a_name = self.parent_a.name

        if self.parent_b is None:
            parent_b_tag = "[root]"
            parent_b_name = "[root]"
        else:
            parent_b_tag = "{}::{}".format(self.parent_b.name, self.parent_b.short_revision())
            parent_b_name = self.parent_b.name

        if self.child_a.get_timestamp() > self.child_b.get_timestamp():
            newer_child = self.child_a
            newer_parent_tag = parent_a_tag
            older_child = self.child_b
            older_parent_tag = parent_b_tag
        else:
            newer_child = self.child_b
            newer_parent_tag = parent_b_tag
            older_child = self.child_a
            older_parent_tag = parent_a_tag

        # TODO: add color
        return ("\n\nAncestry issue:\n"
                "'{parent_a_name}' and '{parent_b_name}' both depend on '{child_name}':\n"
                "    {newer_parent_tag} (newer parent) depends on "
                "{older_child_tag} (older child)\n"
                "    {older_parent_tag} (older parent) depends on "
                "{newer_child_tag} (newer child)\n\n"
                "Although {newer_child_tag} is newer than "
                "{older_child_tag},\n{newer_child_tag} is not "
                "a descendent of {older_child_tag}.\n\n"
                "Therefore, there is no guarantee that "
                "the dependee needed by {older_parent_tag} will be satisfied "
                "by the dependee needed by {newer_parent_tag}."
                "".format(
                    parent_a_name=parent_a_name,
                    parent_b_name=parent_b_name,
                    parent_a_tag=parent_a_tag,
                    parent_b_tag=parent_b_tag,

                    child_name=child_name,
                    child_a_hash=self.child_a.short_revision(),
                    child_b_hash=self.child_b.short_revision(),

                    newer_child_tag="\033[36m{}::{}\033[m".format(
                                        child_name, newer_child.short_revision()),
                    older_child_tag="\033[95m{}::{}\033[m".format(
                                        child_name, older_child.short_revision()),

                    newer_parent_tag="\033[94m"+newer_parent_tag+"\033[m",
                    older_parent_tag="\033[91m"+older_parent_tag+"\033[m",
                ))


class PackageNotInWorkspaceError(WitUserError):
    pass


class WorkSpace:
    MANIFEST = "wit-workspace.json"
    LOCK = "wit-lock.json"

    def __init__(self, path, manifest, lock=None):
        self.path = path
        self.manifest = manifest
        self.lock = lock
        self.repo_paths = []

    # create a new workspace root given a name.
    @staticmethod
    def create(name: str, packages: List[Package]):
        path = Path.cwd() / name
        manifest_path = WorkSpace._manifest_path(path)
        if path.exists():
            log.info("Using existing directory [{}]".format(str(path)))

            if manifest_path.exists():
                log.error("Manifest file [{}] already exists.".format(manifest_path))
                sys.exit(1)

        else:
            log.info("Creating new workspace [{}]".format(str(path)))
            try:
                path.mkdir()

            except Exception as e:
                log.error("Unable to create workspace [{}]: {}".format(str(path), e))
                sys.exit(1)

        manifest = Manifest([])
        manifest.write(manifest_path)
        return WorkSpace(path, manifest)

    # FIXME It's a little weird that we have these special classmethod ones
    # They're here to calculate the paths in staticmethods
    @classmethod
    def _manifest_path(cls, path):
        return path / cls.MANIFEST

    def manifest_path(self):
        return WorkSpace._manifest_path(self.path)

    @classmethod
    def _lockfile_path(cls, path):
        return path / cls.LOCK

    def lockfile_path(self):
        return WorkSpace._lockfile_path(self.path)

    @classmethod
    def is_workspace(cls, path):
        manifest_path = Path(path) / cls.MANIFEST
        return manifest_path.is_file()

    # find a workspace root by iteratively walking up the path
    # until a manifest file is found.
    @staticmethod
    def find(start):
        cwd = start.resolve()
        for p in ([cwd] + list(cwd.parents)):
            manifest_path = WorkSpace._manifest_path(p)
            log.debug("Checking [{}]".format(manifest_path))
            if Path(manifest_path).is_file():
                log.debug("Found workspace at [{}]".format(p))
                wspath = p
                manifest = Manifest.read_manifest(wspath, manifest_path)

                lockfile_path = WorkSpace._lockfile_path(p)
                if lockfile_path.is_file():
                    lock = LockFile.read(lockfile_path)
                else:
                    lock = None

                return WorkSpace(wspath, manifest, lock=lock)

        raise FileNotFoundError("Couldn't find workspace file")

    # FIXME Should we run this algorithm upon `wit status` to mention if
    # lockfile out of sync?
    def update(self):
        log.info("Updating workspace...")

        # FIXME: This is a hack to ensure that we don't have multiple repos
        # with the same name but different source paths. Ideally this could
        # use the version_selector_map but due to a shortcoming in wit we
        # do not update the version selector map in time.
        source_map = {}

        # This algorithm courtesy of Wes
        # https://sifive.atlassian.net/browse/FRAM-1
        # 1. Initialize an empty version selector map
        version_selector_map = {}

        root_repo = None

        # 2. For every existing repo put a tuple (name, hash, commit time) into queue
        queue = []
        for repo in self.manifest.packages:
            if GitRepo.is_git_repo(repo.get_path()):
                repo.fetch()
            else:
                repo.clone()
            commit = repo.revision
            commit_time = repo.commit_to_time(commit)

            queue.append((commit_time, commit, repo.name, repo, root_repo))
            source_map[repo.name] = repo.source

        # sort by the first element of the tuple (commit time in epoch seconds)
        queue.sort(key=lambda tup: tup[0])
        log.debug(queue)

        while queue:
            # 3. Pop the tuple with the newest committer date. This removes from
            # the end of the queue, which is the latest commit date.
            commit_time, commit, reponame, repo, dependent = queue.pop()
            if reponame in version_selector_map:
                selected_commit = version_selector_map[reponame]['commit']

                # 4. If the repo has a selected version, fail if that version
                # does not include this tuple's hash
                if not repo.is_ancestor(commit, selected_commit):
                    raise NotAncestorError(
                        parent_a=dependent,
                        child_a=repo,
                        parent_b=version_selector_map[reponame]['dependent'],
                        child_b=version_selector_map[reponame]['repo'],
                    )

                # 5. If the repo has a selected version, go to step 3
                continue

            # 6. set the version selector for this repo to the tuple's hash
            # FIXME: Right now I'm also storing the repo in here. This is for
            # convenience but is poor data hygiene. Need to think of a better
            # solution here.
            version_selector_map[reponame] = {
                'commit': commit,
                'repo': repo,
                'dependent': dependent,
            }

            # 7. Examine the repository's children
            dependencies = repo.get_dependencies(self.path)
            log.debug("Dependencies for [{}]: [{}]".format(repo.get_path(), dependencies))

            for dep_repo in dependencies:
                dep_repo.find_source(self.repo_paths)
                if dep_repo.name in source_map:
                    if dep_repo.source != source_map[dep_repo.name]:
                        log.error("Repo [{}] has multiple conflicting paths:\n"
                                  "  {}\n"
                                  "  {}\n".format(dep_repo.name, dep_repo.source,
                                                  source_map[dep_repo.name]))
                        sys.exit(1)

                # 8. Clone without checking out the dependency
                # FIXME: This should clone to a temporary area. If this were
                # fixed we could get rid of the source_map dictionary hack
                if GitRepo.is_git_repo(dep_repo.get_path()):
                    dep_repo.fetch()
                else:
                    dep_repo.clone()

                # 9. Find the committer date
                dep_commit_time = dep_repo.commit_to_time(dep_repo.revision)

                # 10. Fail if the dependent commit date is newer than the parent date
                if dep_commit_time > commit_time:
                    # dependent is newer than dependee. Panic.
                    msg = ("Repo [{}] has a dependent that is newer than the source. "
                           "This should not happen.\n".format(dep_repo.name))
                    log.error(msg)
                    sys.exit(1)

                # 11. Push a tuple onto the queue
                queue.append((dep_commit_time, dep_repo.revision, dep_repo.name, dep_repo, repo))
                source_map[dep_repo.name] = dep_repo.source

            # Keep the queue ordered
            queue.sort(key=lambda tup: tup[0])

            # 12. Go to step 3 (finish loop)

        # 13. Print out summary
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            log.info("Checked out '{}' at '{}'".format(reponame, commit))

        # 14. Check out repos and add to lock
        lock_packages = []
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            repo = version_selector_map[reponame]['repo']
            lock_repo = GitRepo(repo.source, commit, name=repo.name, wsroot=self.path)
            lock_repo.checkout()
            lock_packages.append(lock_repo)

        # TODO compare to current and print info?
        new_lock = LockFile(lock_packages)
        new_lock.write(self.lockfile_path())
        self.lock = new_lock

    def set_repo_path(self, repo_path):
        if repo_path is not None:
            self.repo_paths = repo_path.split(" ")
        else:
            self.repo_paths = []

    def add_package(self, package: GitRepo) -> None:
        package.set_path(self.path)
        package.find_source(self.repo_paths)

        if self.manifest.contains_package(package.name):
            error("Manifest already contains package {}".format(package.name))

        if GitRepo.is_git_repo(package.get_path()):
            log.debug("Package {} has already been cloned!".format(package.name))
            package.checkout()
            # copy remote to source
            package.source = package.get_remote()
        else:
            package.clone_and_checkout()

        log.info("Added '{}' to workspace at '{}'".format(package.source, package.revision))
        self.manifest.add_package(package)

        log.debug('my manifest_path = {}'.format(self.manifest_path()))
        self.manifest.write(self.manifest_path())

    def get_package(self, name: str) -> Optional[GitRepo]:
        return self.lock.get_package(name)

    def contains_package(self, name: str) -> bool:
        return self.get_package(name) is not None

    def update_package(self, pkg: GitRepo) -> None:
        old = self.manifest.get_package(pkg.name)
        if old is None:
            msg = "Cannot update package '{}'".format(pkg.name)
            if self.lock.contains_package(pkg.name):
                msg = msg + ", while it exists, it has not been added!"
            else:
                msg = msg + " as it does not exist in the workspace!"
            raise PackageNotInWorkspaceError(msg)

        old.fetch()
        # TODO should this be defined on GitRepo?
        # See if the commit exists
        rev = pkg.revision
        if not old.has_commit(rev):
            # Try origin
            rev = "origin/{}".format(rev)
            if not old.has_commit(rev):
                msg = "Package '{}' contains neither '{}' nor '{}'".format(
                        old.name, pkg.revision, rev)
                raise GitCommitNotFound(msg)

        rev = old.get_commit(rev)
        if rev == old.revision:
            log.warn("Updating '{}' to the same revision it already is!".format(old.name))
        # Do update
        old.revision = rev
        old.checkout()
        # Update and write manifest
        self.manifest.update_package(old)
        self.manifest.write(self.manifest_path())
        log.info("Updated package '{}' to '{}', don't forget to run 'wit update'!"
                 .format(old.name, old.revision))

    def repo_status(self, source):
        raise NotImplementedError

    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
