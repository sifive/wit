#!/usr/bin/env python3

import sys
from pathlib import Path
from pprint import pformat
import logging
from lib.gitrepo import GitRepo
from lib.manifest import Manifest
from lib.lock import LockFile

logging.basicConfig()
log = logging.getLogger('wit')


class NotAncestorError(Exception):
    pass


class RepoAgeConflict(Exception):
    pass


class WorkSpace:
    MANIFEST = "wit-workspace.json"
    LOCK = "wit-lock.json"

    def __init__(self, path, manifest, lock=None):
        self.path = path
        self.manifest = manifest
        self.lock = lock

    # create a new workspace root given a name.
    @staticmethod
    def create(name, packages):
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

        for package in packages:
            package.set_wsroot(path)
            package.clone_and_checkout()

        manifest = Manifest(packages)
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
            log.info("Checking [{}]".format(manifest_path))
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


    # FIXME Should we run this algorithm upon `wit status` to mention if
    # lockfile out of sync?
    def update(self):
        # This algorithm courtesy of Wes
        # https://sifive.atlassian.net/browse/FRAM-1
        # 1. Initialize an empty version selector map
        version_selector_map = {}

        # 2. For every existing repo put a tuple (name, hash, commit time) into queue
        queue = []
        for repo in self.manifest.packages:
            commit = repo.revision
            commit_time = repo.commit_to_time(commit)

            queue.append((commit_time, commit, repo.name, repo))

        # sort by the first element of the tuple (commit time in epoch seconds)
        queue.sort(key=lambda tup: tup[0])
        log.debug(queue)

        while queue:
            # 3. Pop the tuple with the newest committer date. This removes from
            # the end of the queue, which is the latest commit date.
            commit_time, commit, reponame, repo = queue.pop()
            if reponame in version_selector_map:
                selected_commit = version_selector_map[reponame]['commit']

                # 4. If the repo has a selected version, fail if that version
                # does not include this tuple's hash
                if not repo.is_ancestor(commit, selected_commit):
                    raise NotAncestorError

                # 5. If the repo has a selected version, go to step 3
                continue

            # 6. set the version selector for this repo to the tuple's hash
            # FIXME: Right now I'm also storing the repo in here. This is for
            # convenience but is poor data hygiene. Need to think of a better
            # solution here.
            version_selector_map[reponame] = {
                'commit': commit,
                'repo': repo
            }

            # 7. Examine the repository's children
            dependencies = repo.get_dependencies(self.path)
            log.debug("Dependencies for [{}]: [{}]".format(repo.path, dependencies))

            for dep_repo in dependencies:
                # Check to see if there is a path specified in the repomap.
                # If so, use that path instead.
                # dependent['source'] = self.resolve_repomap(dependent['source'])

                # 8. Clone without checking out the dependency
                if not GitRepo.is_git_repo(dep_repo.path):
                    dep_repo.clone()

                # 9. Find the committer date
                dep_commit_time = dep_repo.commit_to_time(dep_repo.revision)

                # 10. Fail if the dependent commit date is newer than the parent date
                if dep_commit_time > commit_time:
                    # dependent is newer than dependee. Panic.
                    raise RepoAgeConflict

                # 11. Push a tuple onto the queue
                queue.append((dep_commit_time, dep_repo.revision, dep_repo.name, dep_repo))

            # Keep the queue ordered
            queue.sort(key=lambda tup: tup[0])

            # 12. Go to step 3 (finish loop)

        # 13. Print out summary
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            print("Repo name [{}] commit [{}]".format(reponame, commit))

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

    def add_package(self, package):
        package.set_wsroot(self.path)

        if GitRepo.is_git_repo(package.path):
            raise NotImplementedError
        else:
            package.clone_and_checkout()

        if self.manifest.contains_package(package):
            # TODO Update the revision
            raise NotImplementedError
        else:
            log.info("Adding [{}] to manifest as [{}]".format(package.source, package.name))
            self.manifest.add_package(package)

        print('my manifest_path = {}'.format(self.manifest_path()))
        self.manifest.write(self.manifest_path())

    def update_package(self, package):
        raise NotImplementedError

    def repo_status(self, source):
        raise NotImplementedError

    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
