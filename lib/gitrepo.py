#!/usr/bin/env python3

import subprocess
from pathlib import Path
import logging
from pprint import pformat
import json
import sys
#import lib.manifest

logging.basicConfig()
log = logging.getLogger('wit')


class GitError(Exception):
    pass


class GitRepo:
    """
    In memory data structure representing a Git repository
    """

    # TODO
    #   - we accept path as a String, should we?
    #   - should we verify the creation was correct?
    def __init__(self, name, remote, path):
        self.name = name
        self.remote = remote
        if not path is Path:
            self.path = Path(path)
        else:
            self.path = path

    @staticmethod
    def fromPackage(package, path):
        """
        Creates a GitRepo from a package description into a path
        """
        repo = GitRepo(package.name, package.remote, path)
        repo.clone()
        return repo

    @staticmethod
    def from_path(path):
        """
        Create a GitRepo from an existing repo on disk
        """
        assert GitRepo.is_git_repo(path), "Cannot create git repo from {}".format(path)
        proc = GitRepo._raw_git_command(str(path), "remote", "get-url", "origin")
        GitRepo._git_check(proc)
        remote = proc.stdout.rstrip("\r\n")
        name = GitRepo.remote_to_name(remote)
        return GitRepo(name, remote, path)


    # TODO Should this be folding in to fromPackage?
    def clone(self):
        assert not GitRepo.is_git_repo(self.path), "Trying to clone into existing git repo!"

        cwd = self.path.parent
        proc = GitRepo._raw_git_command(str(cwd), "clone", "--no-checkout", str(self.remote), str(self.path))
        try:
            GitRepo._git_check(proc)
        except Exception as e:
            log.error("Error cloning into workspace: {}".format(e))
            sys.exit(1)

    def get_latest_commit(self):
        proc = self._git_command('rev-parse', 'HEAD')
        GitRepo._git_check(proc)
        return proc.stdout.rstrip()

    def clean(self):
        proc = self._git_command('status', '--porcelain')
        GitRepo._git_check(proc)
        return proc.stdout == ""

    def modified(self):
        proc = self._git_command('status', '--porcelain')
        GitRepo._git_check(proc)
        for line in proc.stdout.split("\n"):
            if line.lstrip().startswith("M"):
                return True
        return False

    def untracked(self):
        proc = self._git_command('status', '--porcelain')
        GitRepo._git_check(proc)
        for line in proc.stdout.split("\n"):
            if line.lstrip().startswith("??"):
                return True
        return False

    # TODO Since we're storing the revision, should we be passing it as an argument?
    def commit_to_time(self, commit):
        proc = self._git_command('log', '-n1', '--format=%ct', commit)
        GitRepo._git_check(proc)
        return proc.stdout.rstrip()

    def is_ancestor(self, ancestor, current=None):
        proc = self._git_command("merge-base", "--is-ancestor", ancestor, current or self.get_latest_commit())
        return proc.returncode == 0

    ## FIXME should we pass wsroot or should it be a member of the GitRepo?
    ## Should this be a separate mutation or part of normal construction?
    #def get_dependencies(self, wsroot):
    #    proc = self._git_command("show", "{}:{}".format(self.revision, GitRepo.PKG_DEPENDENCY_FILE))
    #    if proc.returncode:
    #        log.info("No dependency file found in repo [{}:{}]".format(self.revision, self.path()))
    #        return []
    #    json_content = json.loads(proc.stdout)
    #    return lib.manifest.Manifest.process_manifest(wsroot, json_content).packages

    # Reads a file from a certain commit
    # Returns the contents of the file or a string if the file does not exist in that commit
    def show_file(self, commit, file_path):
        proc = self._git_command("show", "{}:{}".format(commit, file_path))
        if proc.returncode:
            return None
        return proc.stdout

    def checkout(self, commit):
        proc = self._git_command("checkout", commit)
        GitRepo._git_check(proc)

    def _git_command(self, *args):
        return GitRepo._raw_git_command(self.path, *args)

    @staticmethod
    def _raw_git_command(path, *args):
        log.debug("Executing [{}] in [{}]".format(' '.join(['git', *args]), str(path)))
        proc = subprocess.run(['git', *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              cwd=str(path), universal_newlines=True)
        return proc

    @staticmethod
    def _git_check(proc):
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
    def remote_to_name(remote):
        """
        >>> GitRepo.remote_to_name("git@github.com:sifive/wit.git")
        'wit'
        >>> GitRepo.remote_to_name("https://github.com/sifive/wit.git")
        'wit'
        """
        import re
        return re.sub('\.git', '', remote.split("/")[-1])

    @staticmethod
    def is_git_repo(path):
        if not path.is_dir():
            return False
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


