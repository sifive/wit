#!/usr/bin/env python3

import subprocess
from pathlib import Path
import logging
from pprint import pformat
import json
import sys
import lib.manifest

log = logging.getLogger('wit')


class GitError(Exception):
    pass


class GitRepo:
    """
    In memory data structure representing a Git repo package
    It may not be in sync with data structures on the file system
    Note there can be multiple GitRepo objects for the same package
    """
    WIT_DEPENDENCY_FILE = "wit-manifest.json"

    def __init__(self, source, revision, name=None, path=None):
        self.path = path
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
        assert self.path is None, "Trying to set path, but it has already been set!"
        self.path = wsroot / self.name

    # find the repo based on path variable
    def find_source(self, repo_paths):
        for path in repo_paths:
            tmp_path = str(Path(path) / self.name)
            if GitRepo.is_git_repo(tmp_path):
                self.source = tmp_path
                return

    def clone(self):
        assert self.path is not None, "Path must be set before cloning!"
        assert not GitRepo.is_git_repo(self.path), "Trying to clone and checkout into existing git repo!"
        log.info('Cloning {}...'.format(self.name))

        self.path.mkdir()

        proc = self._git_command("clone", "--no-checkout", str(self.source), str(self.path))
        try:
            self._git_check(proc)
        except Exception as e:
            log.error("Error cloning into workspace: {}".format(e))
            sys.exit(1)

    def clone_and_checkout(self):
        self.clone()
        self.checkout()
        # If our revision was a branch or tag, get the actual commit
        self.revision = self.get_latest_commit()

    def get_latest_commit(self):
        proc = self._git_command('rev-parse', 'HEAD')
        self._git_check(proc)
        return proc.stdout.rstrip()

    def clean(self):
        proc = self._git_command('status', '--porcelain')
        self._git_check(proc)
        return proc.stdout == ""

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
        proc = self._git_command("merge-base", "--is-ancestor", ancestor, current or self.get_latest_commit())
        return proc.returncode == 0

    # FIXME should we pass wsroot or should it be a member of the GitRepo?
    # Should this be a separate mutation or part of normal construction?
    def get_dependencies(self, wsroot):
        proc = self._git_command("show", "{}:{}".format(self.revision, GitRepo.WIT_DEPENDENCY_FILE))
        if proc.returncode:
            log.debug("No dependency file found in repo [{}:{}]".format(self.revision, self.path))
            return []
        json_content = json.loads(proc.stdout)
        return lib.manifest.Manifest.process_manifest(wsroot, json_content).packages

    def checkout(self):
        proc = self._git_command("checkout", self.revision)
        self._git_check(proc)

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.revision,
        }

    def _git_command(self, *args):
        log.debug("Executing [{}] in [{}]".format(' '.join(['git', *args]), self.path))
        proc = subprocess.run(['git', *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              cwd=str(self.path), universal_newlines=True)
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
