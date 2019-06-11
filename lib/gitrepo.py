#!/usr/bin/env python3

import subprocess
from pathlib import Path
import logging
from pprint import pformat
import json
import sys
import lib.manifest
from lib.common import WitUserError

log = logging.getLogger('wit')


class GitError(Exception):
    pass


class GitCommitNotFound(WitUserError):
    pass


class GitRepo:
    """
    In memory data structure representing a Git repo package
    It may not be in sync with data structures on the file system
    Note there can be multiple GitRepo objects for the same package
    """
    PKG_DEPENDENCY_FILE = "wit-manifest.json"

    def __init__(self, source, revision, name=None, wsroot=None):
        self.wsroot = wsroot
        self.source = source
        self.revision = revision
        if name is None:
            self.name = GitRepo.path_to_name(source)
        else:
            self.name = name

    # FIXME
    # Ideally we would always set the path on construction, but constructing
    # GitRepo (see Package.from_arg) during argument parsing, we don't yet know
    # the path
    def set_path(self, wsroot):
        self.path = wsroot / self.name

    def get_path(self):
        try:
            return self.path

        except AttributeError:
            return self.wsroot / self.name

    def set_wsroot(self, wsroot):
        self.wsroot = wsroot

    # find the repo based on path variable
    def find_source(self, repo_paths):
        for path in repo_paths:
            tmp_path = str(Path(path) / self.name)
            if GitRepo.is_git_repo(tmp_path):
                self.source = tmp_path
                return

    def clone(self):
        assert not GitRepo.is_git_repo(self.get_path()), \
            "Trying to clone and checkout into existing git repo!"
        log.info('Cloning {}...'.format(self.name))

        path = self.get_path()
        path.mkdir()
        proc = self._git_command("clone", "--no-checkout", str(self.source), str(path))
        try:
            self._git_check(proc)
        except Exception as e:
            log.error("Error cloning into workspace: {}".format(e))
            sys.exit(1)

    def clone_and_checkout(self):
        self.clone()
        self.checkout()

    def get_latest_commit(self) -> str:
        return self.get_commit('HEAD')

    def get_commit(self, commit) -> str:
        proc = self._git_command('rev-parse', commit)
        self._git_check(proc)
        return proc.stdout.rstrip()

    def has_commit(self, commit) -> bool:
        proc = self._git_command('rev-parse', commit)
        return proc.returncode == 0

    def get_remote(self) -> str:
        # TODO Do we need to worry about other remotes?
        proc = self._git_command('remote', 'get-url', 'origin')
        self._git_check(proc)
        return proc.stdout.rstrip()

    def clean(self):
        proc = self._git_command('status', '--porcelain')
        self._git_check(proc)
        return proc.stdout == ""

    def fetch(self):
        proc = self._git_command('fetch', '--all')
        self._git_check(proc)
        return proc.returncode == 0

    def modified(self):
        proc = self._git_command('status', '--porcelain')
        self._git_check(proc)
        for line in proc.stdout.split("\n"):
            if line.lstrip().startswith("M"):
                return True
        return False

    def untracked(self):
        proc = self._git_command('status', '--porcelain')
        self._git_check(proc)
        for line in proc.stdout.split("\n"):
            if line.lstrip().startswith("??"):
                return True
        return False

    # TODO Since we're storing the revision, should we be passing it as an argument?
    def commit_to_time(self, hash):
        proc = self._git_command('log', '-n1', '--format=%ct', hash)
        self._git_check(proc)
        return proc.stdout.rstrip()

    def is_ancestor(self, ancestor, current=None):
        proc = self._git_command("merge-base", "--is-ancestor", ancestor,
                                 current or self.get_latest_commit())
        return proc.returncode == 0

    # FIXME should we pass wsroot or should it be a member of the GitRepo?
    # Should this be a separate mutation or part of normal construction?
    def get_dependencies(self, wsroot):
        self.set_wsroot(wsroot)
        return self.read_manifest_from_commit(self.revision).packages

    def read_manifest(self) -> lib.manifest.Manifest:
        mpath = self.manifest_path()
        return lib.manifest.Manifest.read_manifest(self.wsroot, mpath, safe=True)

    def write_manifest(self, manifest) -> None:
        mpath = self.manifest_path()
        manifest.write(mpath)

    def read_manifest_from_commit(self, revision) -> lib.manifest.Manifest:
        proc = self._git_command("show", "{}:{}".format(revision, GitRepo.PKG_DEPENDENCY_FILE))
        if proc.returncode:
            log.debug("No dependency file found in repo [{}:{}]".format(revision,
                      self.get_path()))
        json_content = [] if proc.returncode else json.loads(proc.stdout)
        return lib.manifest.Manifest.process_manifest(self.wsroot, json_content)

    def add_dependency(self, package):
        log.info("Adding dependency to '{}' on '{}' at '{}'".format(
                  self.name, package.name, package.revision))
        manifest = self.read_manifest()
        manifest.add_package(package)
        self.write_manifest(manifest)

    # TODO should we check manifest against the committed version?
    def update_dependency(self, package):
        manifest = self.read_manifest()
        old = manifest.get_package(package.name)
        if old is None:
            msg = "Package '{}' does not depend on '{}'!".format(self.name, package.name)
            raise WitUserError(msg)
        if old.revision == package.revision:
            log.warn("Input update revision for '{}' in '{}' is unchanged!".format(
                     package.name, self.name))
        else:
            log.info("Updating '{}' dependency on '{}' from '{}' to '{}'".format(
                     self.name, package.name, old.revision, package.revision))
            manifest.update_package(package)
            manifest.write(self.manifest_path())

    def checkout(self):
        proc = self._git_command("checkout", self.revision)
        self._git_check(proc)
        # If our revision was a branch or tag, get the actual commit
        self.revision = self.get_latest_commit()

    def manifest_path(self):
        return self.get_path() / self.PKG_DEPENDENCY_FILE

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.revision,
        }

    def check_uncommitted_manifest(self):
        proc = self._git_command("diff", str(self.manifest_path()))
        if proc.stdout != "":
            print("\033[31m", end="") # start red text
            print("Warning:", self.name, "has uncommitted changes in its wit-manifest.json", end="")
            print("\033[m") # end red text

    def _git_command(self, *args):
        log.debug("Executing [{}] in [{}]".format(' '.join(['git', *args]), self.get_path()))
        proc = subprocess.run(['git', *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              cwd=str(self.get_path()), universal_newlines=True)
        return proc

    def _git_check(self, proc):
        if proc.returncode:
            log.error("Command [{}] exited with non-zero exit status [{}]"
                      .format(' '.join(proc.args), proc.returncode))
            log.error("stdout: [{}]".format(proc.stdout.rstrip()))
            log.error("stderr: [{}]".format(proc.stderr.rstrip()))
            raise GitError(proc.stderr.rstrip())

        return proc.returncode

    @staticmethod
    def path_to_name(path):
        """
        >>> GitRepo.path_to_name("a.git")
        'a'
        >>> GitRepo.path_to_name("/a/b/c/def.git")
        'def'
        >>> GitRepo.path_to_name("ghi")
        'ghi'
        """
        return Path(path).name.replace('.git', '')

    @staticmethod
    def is_git_repo(path):
        cmd = ['git', 'ls-remote', '--exit-code', str(path)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret = proc.returncode
        return ret == 0

    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
