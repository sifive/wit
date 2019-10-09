#!/usr/bin/env python3

import subprocess
from pathlib import Path
from pprint import pformat
import json
import re
from . import manifest
from .common import WitUserError
from .witlogger import getLogger

log = getLogger()


class GitError(Exception):
    pass


class GitCommitNotFound(Exception):
    pass


class BadSource(WitUserError):
    def __init__(self, name, source):
        self.name = name
        self.source = source

    def __str__(self):
        return "Bad remote for '{}':\n  {}".format(self.name, self.source)


verbose_prefix = re.compile(r"^refs/(?:heads/)?")


# TODO Could speed up validation
#   - use git ls-remote to validate remote exists
#   - use git ls-remote to validate revision for tags and branches
#   - if github repo, check if page exists (or if you get 404)

class GitRepo:
    """
    In memory data structure representing a Git repo package
    It may not be in sync with data structures on the file system
    Note there can be multiple GitRepo objects for the same package
    """
    PKG_DEPENDENCY_FILE = "wit-manifest.json"

    def __init__(self, name, wsroot: Path):
        self.name = name
        self.path = wsroot / name

    def is_bad_source(self, source):
        tmp = self.path
        self.path = self.path.parent
        proc = self._git_command('ls-remote', source)
        self.path = tmp
        return proc.returncode != 0

    # name is needed for generating error messages
    def download(self, source, name):
        if not GitRepo.is_git_repo(self.path):
            self.clone(source, name)
        self.fetch(source, name)

    # name is needed for generating error messages
    def clone(self, source, name):
        assert not GitRepo.is_git_repo(self.path), \
            "Trying to clone and checkout into existing git repo!"
        log.info('Cloning {}...'.format(self.name))

        self.path.mkdir()
        proc = self._git_command("clone", "--no-checkout", source, str(self.path))
        try:
            self._git_check(proc)
        except GitError:
            if self.is_bad_source(source):
                raise BadSource(name, source)
            else:
                raise

    # name is needed for generating error messages
    def fetch(self, source, name):
        # in case source is a remote and we want a commit
        proc = self._git_command('fetch', source)
        # in case source is a file path and we want, for example, origin/master
        self._git_command('fetch', '--all')
        try:
            self._git_check(proc)
        except GitError:
            if self.is_bad_source(source):
                raise BadSource(name, source)
            else:
                raise
        return proc.returncode == 0

    def get_head_commit(self) -> str:
        return self.get_commit('HEAD')

    def get_commit(self, commit) -> str:
        proc = self._git_command('rev-parse', commit)
        try:
            self._git_check(proc)
        except GitError:
            proc = self._git_command('rev-parse', 'origin/{}'.format(commit))
            try:
                self._git_check(proc)
            except GitError:
                if 'unknown revision or path not in the working tree' in proc.stderr:
                    raise GitCommitNotFound
                else:
                    raise
        return proc.stdout.rstrip()

    def get_shortened_rev(self, commit):
        proc = self._git_command('rev-parse', '--short', commit)
        self._git_check(proc)
        return proc.stdout.rstrip()

    def is_hash(self, ref):
        return self.get_commit(ref) == ref

    def is_tag(self, ref):
        proc = self._git_command('tag', '--list', ref)
        self._git_check(proc)
        return ref in proc.stdout.split('\n')

    def has_commit(self, commit) -> bool:
        # rev-parse does not always fail when a commit is missing
        proc = self._git_command('cat-file', '-t', commit)
        return proc.returncode == 0

    def have_common_ancestor(self, commits):
        proc = self._git_command('merge-base', '--octopus', *commits)
        return proc.returncode == 0

    def get_remote(self) -> str:
        # TODO Do we need to worry about other remotes?
        proc = self._git_command('remote', 'get-url', 'origin')
        self._git_check(proc)
        return proc.stdout.rstrip()

    def set_origin(self, source):
        proc = self._git_command('remote', 'set-url', 'origin', source)
        self._git_check(proc)

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

    def modified_manifest(self):
        proc = self._git_command('status', '--porcelain')
        self._git_check(proc)
        for line in proc.stdout.split("\n"):
            if ((line.lstrip().startswith("M") or line.lstrip().startswith("D"))
                    and line.endswith("wit-manifest.json")):
                return True
        return False

    # TODO Since we're storing the revision, should we be passing it as an argument?
    def commit_to_time(self, hash):
        proc = self._git_command('log', '-n1', '--format=%ct', hash)
        self._git_check(proc)
        return proc.stdout.rstrip()

    def is_ancestor(self, ancestor, current=None):
        proc = self._git_command("merge-base", "--is-ancestor", ancestor,
                                 current or self.get_head_commit())
        return proc.returncode == 0

    def read_manifest(self) -> manifest.Manifest:
        mpath = self.manifest_path()
        return manifest.Manifest.read_manifest(mpath, safe=True)

    def write_manifest(self, manifest) -> None:
        mpath = self.manifest_path()
        manifest.write(mpath)

    def read_manifest_from_commit(self, revision) -> manifest.Manifest:
        proc = self._git_command("show", "{}:{}".format(revision, GitRepo.PKG_DEPENDENCY_FILE))
        if proc.returncode:
            log.debug("No dependency file found in repo [{}:{}]".format(revision,
                      self.path))
        json_content = [] if proc.returncode else json.loads(proc.stdout)
        return manifest.Manifest.process_manifest(json_content)

    def checkout(self, revision):
        wanted_hash = self.get_commit(revision)
        if self.get_commit('HEAD') != wanted_hash:
            proc_ref = self._git_command("show-ref")
            self._git_check(proc_ref)
            rev_names = proc_ref.stdout.rstrip().split('\n')
            rev_names = [r.split(' ') for r in rev_names]
            rev_names = [r[1] for r in rev_names if r[0] == wanted_hash]
            rev_names = [r for r in rev_names if not r.startswith('refs/remotes')]
            rev_names = [verbose_prefix.sub('', r) for r in rev_names]

            suggestions = ''
            if len(rev_names) > 1:
                suggestions = ' ({})'.format(', '.join(rev_names))

            if len(rev_names) != 1:
                rev = revision
                log.info("Checking out '{}' at '{}'{}".format(self.name, rev, suggestions))
            else:
                rev = rev_names[0]
                log.info("Checking out '{}' at '{}' ({})".format(self.name, rev, revision))

            proc = self._git_command("checkout", rev)
            self._git_check(proc)
        else:
            proc = self._git_command("checkout")
            self._git_check(proc)

        # If our revision was a branch or tag, get the actual commit
        self.revision = self.get_head_commit()

    def manifest_path(self):
        return self.path / self.PKG_DEPENDENCY_FILE

    def manifest(self, source, revision):
        return {
            'name': self.name,
            'source': source,
            'commit': revision,
        }

    def _git_command(self, *args):
        log.debug("Executing [{}] in [{}]".format(' '.join(['git', *args]), self.path))
        proc = subprocess.run(['git', *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              cwd=str(self.path), universal_newlines=True)
        return proc

    def _git_check(self, proc):
        if proc.returncode:
            msg = "Command [{}] exited with non-zero exit status [{}]\n".format(
                  ' '.join(proc.args), proc.returncode)
            msg += "stdout: [{}]\n".format(proc.stdout.rstrip())
            msg += "stderr: [{}]\n".format(proc.stderr.rstrip())
            raise GitError(msg)

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
