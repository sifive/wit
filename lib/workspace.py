#!/usr/bin/env python3

import sys
from pathlib import Path
from pprint import pformat
import logging
from lib.gitrepo import GitRepo, GitCommitNotFound
from lib.manifest import Manifest
from lib.lock import LockFile
from lib.package import Package
from typing import List, Optional
from lib.common import error, WitUserError
from lib.propagating_thread import PropagatingThread
import datetime
import threading

log = logging.getLogger('wit')


class NotAncestorError(Exception):
    pass


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

        self._update_thread_lock = threading.Lock()

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

        raise FileNotFoundError("Couldn't find manifest file")

    # FIXME: Should we run this algorithm upon `wit status` to mention if lockfile out of sync?
    # FIXME: We should be able to do this in a tmp directory, without touching the workspace
    def update(self):
        log.info("Updating workspace...")

        # folder_name -> commit, requester timestamp, ready lock
        # ready_lock should be released when the repo is finished cloning
        self._downloaded_packages = {}  # folder_name -> {commit, dependant}
        self._done_updating = threading.Event()

        now = datetime.datetime.now()
        for repo in self.manifest.packages:
            repo.find_source(self.repo_paths)
            if GitRepo.is_git_repo(repo.get_path()):
                repo.fetch()
            else:
                repo.clone()
            self._downloaded_packages[repo.name] = {
                'commit': repo.revision,
                'source': repo.source,
                'timestamp_of_requester': now,
                'ready_lock': threading.Lock(),
            }

        threads = []
        for repo in self.manifest.packages:
            t = PropagatingThread(target=self.handle_repo_parallel, args=(repo,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        for repo_name in self._downloaded_packages:
            commit = self._downloaded_packages[repo_name]['commit']
            log.info("Checked out '{}' at '{}'".format(repo_name, commit))

        # Check out repos and add to lock
        lock_packages = []
        for repo_name in self._downloaded_packages:
            commit = self._downloaded_packages[repo_name]['commit']
            source = self._downloaded_packages[repo_name]['source']
            lock_repo = GitRepo(source, commit, name=repo_name, wsroot=self.path)
            lock_repo.checkout()
            lock_packages.append(lock_repo)

        # TODO compare to current and print info?
        new_lock = LockFile(lock_packages)
        new_lock.write(self.lockfile_path())
        self.lock = new_lock

    # this assumes that the provided parent_repo has already been safely cloned
    def handle_repo_parallel(self, parent_repo):
        threads = []

        deps = parent_repo.get_dependencies(self.path)
        log.debug("Dependencies for [{}]: [{}]".format(parent_repo.get_path(), deps))
        for repo in deps:
            repo.find_source(self.repo_paths)  # handle the --repo-path flag

            our_commit = repo.revision
            our_timestamp = parent_repo.get_timestamp()

            # check if this repo has already been requested
            with self._update_thread_lock:
                already_requested = repo.name in self._downloaded_packages

                if already_requested:
                    their_source = self._downloaded_packages[repo.name]['source']
                    if their_source != repo.source:
                        log.error("Repo [{}] has multiple conflicting paths:\n"
                                  "  {}\n"
                                  "  {}\n".format(repo.name, repo.source,
                                                  their_source))
                        sys.exit(1)

                    # wait till they are done cloning
                    # FIXME: we could do something cleaner
                    self._downloaded_packages[repo.name]['ready_lock'].acquire()

                    their_data = self._downloaded_packages[repo.name]
                    their_commit = their_data['commit']
                    their_timestamp = their_data['timestamp_of_requester']
                    we_are_newer = our_timestamp > their_timestamp

                    # NOTE: we could do something clever to reduce duplicate code but being clever
                    # could hurt readability
                    if we_are_newer:  # we are newer
                        if not repo.is_ancestor(their_commit, our_commit):
                            # if we are here, that means a older parent requested a child newer than
                            # this parent's child
                            raise NotAncestorError
                    else:  # we are older
                        if not repo.is_ancestor(our_commit, their_commit):
                            # if we are here, that means a newer parent requested a child older than
                            # this parent's child
                            raise NotAncestorError

                    if not we_are_newer:
                        self._downloaded_packages[repo.name]['ready_lock'].release()
                        continue  # see Step 5

                # note that we never release from that if branch. That's intentional!
                self._downloaded_packages[repo.name] = {
                    'commit': our_commit,
                    'source': repo.source,
                    'timestamp_of_requester': our_timestamp,
                    'ready_lock': threading.Lock(),
                }
            with self._downloaded_packages[repo.name]['ready_lock']:
                # scenario 1: we are the first to request this package, we should download it
                # scenario 2: we are requesting a newer version, so we need to make sure the newest
                #             version is downloaded
                if GitRepo.is_git_repo(repo.get_path()):
                    repo.fetch()
                else:
                    repo.clone()

                # make sure the requesting commit is newer than the requested commit
                if our_timestamp < repo.get_timestamp():
                    # dependent is newer than dependee. Panic.
                    msg = ("Repo [{}] has a dependent that is newer than the source. "
                           "This should not happen.\n".format(repo.name))
                    log.error(msg)
                    sys.exit(1)
            # now, we need to spawn new threads to further explore dependencies
            t = PropagatingThread(target=self.handle_repo_parallel, args=(repo,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

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
