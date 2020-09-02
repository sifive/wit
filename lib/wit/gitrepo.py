#!/usr/bin/env python3

import subprocess
from pathlib import Path
from pprint import pformat
import re
import os
import sys
from .common import WitUserError
from collections import OrderedDict
from .witlogger import getLogger
from typing import List, Set  # noqa: F401
from functools import lru_cache
from .env import git_reference_workspace
from .repo_entries import RepoEntry, RepoEntries

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
    SUBMODULE_FILE = ".gitmodules"

    def __init__(self, name, wsroot: Path):
        self.name = name
        self.path = wsroot / name
        self.wsroot = wsroot
        # Cache known hashes for quick lookup
        self._known_hashes = set()  # type: Set[str]

    def _known_hash(self, commit) -> bool:
        """Checks if a hash exists in the current repo"""
        return commit in self._known_hashes

    def _add_known_hash(self, commit):
        self._known_hashes.add(commit)

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

        cmd = ["clone", *self._git_reference_options(), "--no-checkout", source, str(self.path)]
        proc = self._git_command(*cmd, working_dir=str(self.path.parent))
        try:
            self._git_check(proc)
        except GitError:
            if self.is_bad_source(source):
                raise BadSource(name, source)
            else:
                raise
        log.info('Cloned {}'.format(self.name))

    def _git_reference_options(self):
        """
        Use git clone's '--reference' to point at a local repository cache to copy objects/commits
        to save network traffic. Any missing objects/commits are downloaded from the true remote.
        Only newer git versions can use '--reference-if-able', so we emulate the 'if-able' bit.
        """
        if not git_reference_workspace:
            return []
        paths = [Path(git_reference_workspace) / self.name,
                 Path(git_reference_workspace) / (self.name+'.git')]
        for path in paths:
            if path.is_dir():
                return ["--reference", str(path), "--dissociate"]
        return []

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

    @lru_cache(maxsize=None)
    def _get_commit_cached(self, commit):
        return self._get_commit_impl(commit)

    def _get_commit_impl(self, commit):
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

    def get_commit(self, commit) -> str:
        if self._known_hash(commit):
            result = self._get_commit_cached(commit)
        else:
            result = self._get_commit_impl(commit)
        self._add_known_hash(result)
        return result

    @lru_cache(maxsize=None)
    def _get_shortened_rev_cached(self, commit):
        return self._get_shortened_rev_impl(commit)

    def _get_shortened_rev_impl(self, commit):
        proc = self._git_command('rev-parse', '--short', commit)
        self._git_check(proc)
        return proc.stdout.rstrip()

    def get_shortened_rev(self, commit):
        if self._known_hash(commit):
            return self._get_shortened_rev_cached(commit)
        else:
            return self._get_shortened_rev_impl(commit)

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

    @lru_cache(maxsize=None)
    def _commit_to_time_cached(self, hash):
        return self._commit_to_time_impl(hash)

    def _commit_to_time_impl(self, hash):
        proc = self._git_command('log', '-n1', '--format=%ct', hash)
        self._git_check(proc)
        return proc.stdout.rstrip()

    def commit_to_time(self, hash):
        if self._known_hash(hash):
            return self._commit_to_time_cached(hash)
        else:
            return self._commit_to_time_impl(hash)

    def is_ancestor(self, ancestor, current=None):
        proc = self._git_command("merge-base", "--is-ancestor", ancestor,
                                 current or self.get_head_commit())
        return proc.returncode == 0

    def repo_entries_from_commit(self, revision) -> List[RepoEntry]:
        manifest_entries = self._read_manifest_from_commit(revision)
        if len(manifest_entries) == 0:
            manifest_entries = self._read_submodules_from_commit(revision)
        return manifest_entries

    def _read_manifest_from_commit(self, revision) -> List[RepoEntry]:
        proc = self._git_command("show", "{}:{}".format(revision, GitRepo.PKG_DEPENDENCY_FILE))
        if proc.returncode:
            log.debug("No wit dependency file found in repo [{}:{}]".format(revision,
                      self.path))
            return []
        return RepoEntries.parse(proc.stdout, Path(GitRepo.PKG_DEPENDENCY_FILE), revision)

    def _read_submodules_from_commit(self, revision) -> List[RepoEntry]:
        proc = self._git_command("show", "{}:{}".format(revision, GitRepo.SUBMODULE_FILE))
        if proc.returncode:
            log.debug("No .gitmodules file found in repo [{}:{}]".format(revision, self.path))
            return []

        log.debug("{}:{} does not have wit-manifest.json, "
                  "reading dependencies from .gitmodules instead"
                  .format(self.name, revision))

        # Use the 'git config' parser to read the submodule contents.
        # Output is of the form:
        #     submodule.$NAME.path $PATH
        #     submodule.$NAME.url  $REMOTE
        proc = self._git_command("config", "-f-", "--get-regex", r"submodule\..*",
                                 input=proc.stdout)
        self._git_check(proc)

        paths_by_name = OrderedDict()  # type: OrderedDict
        urls_by_name = {}

        path_r = re.compile(r'^submodule\.(.*)\.path (.*)$')
        for line in proc.stdout.splitlines():
            m = path_r.match(line)
            if m:
                paths_by_name[m.group(1)] = m.group(2)

        url_r = re.compile(r'^submodule\.(.*)\.url (.*)$')
        for line in proc.stdout.splitlines():
            m = url_r.match(line)
            if m:
                urls_by_name[m.group(1)] = m.group(2)

        if len(paths_by_name) != len(urls_by_name):
            log.error("Error matching paths with urls in {}/{}"
                      .format(self.name, GitRepo.SUBMODULE_FILE))
            sys.exit(1)

        submodules = []
        for name_key, path in paths_by_name.items():
            # We use the relative path within the repository to ask the git index
            # for the pointer that's currently commited
            submodule_ref = self._get_submodule_pointer(revision, path)

            url = urls_by_name[name_key]
            name = name_key
            if "/" in name:
                # Wit only supports a 'flat' checkout pattern.
                # By default, git submodules uses the relative checkout path to name the submodule.
                # The user can add an explict name, but often do not.
                # So if the submodule happens to have a name that looks like a nested path,
                # use the the final path component in the remote url instead as the path-based names
                # as sometimes they're easy-to-clash names like docs/html.
                name = re.sub(r"\.git$", "", os.path.basename(url))

            submodules.append(RepoEntry(name, submodule_ref, url))

        return submodules

    def _get_submodule_pointer(self, revision, path):
        """
        Get the submodule pointer commit in the index.
        Note: This is NOT always the currently checked-out commit for a submodule.
        The 'git ls-tree' output is defined as:
           ^<mode> space <type> space <git object hash> tab <file>$
        """
        proc = self._git_command("ls-tree", revision, path)
        self._git_check(proc)
        first_line = proc.stdout.splitlines()[0]
        no_tab = first_line.split("\t")[0]
        return no_tab.split(" ")[2]

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

    def manifest(self, source, revision):
        return {
            'name': self.name,
            'source': source,
            'commit': revision,
        }

    def _git_command(self, *args, working_dir=None, input=None):
        cwd = str(self.path) if working_dir is None else str(working_dir)
        log.debug("Executing [{}] in [{}]".format(' '.join(['git', *args]), cwd))
        proc = subprocess.run(['git', *args],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              universal_newlines=True,
                              input=input,
                              cwd=cwd)
        log.spam("   stderr: [{}]".format(proc.stderr.rstrip()))
        log.spam("   stdout: [{}]".format(proc.stdout.rstrip()))
        return proc

    def _git_check(self, proc):
        if proc.returncode:
            msg = "Command [{}] in [{}] exited with non-zero exit status [{}]\n".format(
                  ' '.join(proc.args), str(self.path), proc.returncode)
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
