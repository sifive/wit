#!/usr/bin/env python3

import os
import sys
from pathlib import Path
import json
from pprint import pformat
import logging
import subprocess
from collections import OrderedDict

logging.basicConfig()
log = logging.getLogger('wit')


class NotAncestorError(Exception):
    pass


class RepoAgeConflict(Exception):
    pass


class GitError(Exception):
    pass

    
class WorkSpace:
    MANIFEST = "wit-manifest.json"
    LOCK = "wit-lock.json"

    def __init__(self, repomap):
        self.path = None
        self.manifest = []
        self.lock = OrderedDict()

        if repomap is not None:
            self.repomap = self.read_repomap(repomap)

        else:
            self.repomap = None
    

    # create a new workspace root given a name.
    def create(self, name):
        self.path = Path.cwd() / name

        if self.path.exists():
            log.info("Using existing directory [{}]".format(str(self.path)))

            manifest_file = self.path / self.MANIFEST
            if manifest_file.exists():
                log.error("Manifest file [{}] already exists.".format(manifest_file))
                sys.exit(1)

        else:
            log.info("Creating new workspace [{}]".format(str(self.path)))
            try:
                self.path.mkdir()

            except Exception as e:
                log.error("Unable to create workspace [{}]: {}".format(str(self.path), e))
                sys.exit(1)

        self.path = self.path.resolve()
        self.write_manifest()


    # find a workspace root by iteratively walking up the path
    # until a manifest file is found.
    def find(self):
        cwd = Path.cwd().resolve()
        for p in ([cwd] + list(cwd.parents)):
            log.info("Checking [{}]".format(p / self.MANIFEST))
            if Path(p / self.MANIFEST).is_file():
                log.debug("Found workspace at [{}]".format(p))
                self.path = p

                self.read_manifest()
                self.read_lockfile()
                return
        
        raise FileNotFoundError("Couldn't find manifest file")


    def update(self):
        # This algorithm courtesy of Wes
        # https://sifive.atlassian.net/browse/FRAM-1
        # 1. Initialize an empty version selector map
        version_selector_map = {}
        self.lock = OrderedDict()

        # 2. For every existing repo put a tuple (name, hash, commit time) into queue
        queue = []
        for ws in self.manifest:
            repo = GitRepo.create(ws['source'], dest=self.path)
            commit_time = repo.commit_to_time(ws['commit'])

            queue.append((commit_time, ws['commit'], ws['name'], repo))
        
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
            dependencies = repo.get_dependencies(hash=commit)            
            log.debug("Dependencies for [{}]: [{}]".format(repo.clone_path, dependencies))

            for dependent in dependencies:
                # Check to see if there is a path specified in the repomap.
                # If so, use that path instead.
                dependent['source'] = self.resolve_repomap(dependent['source'])

                # 8. Clone without checking out the dependency
                dep_repo = GitRepo.create(source=dependent['source'], dest=self.path)
                
                # 9. Find the committer date
                dep_commit_time = dep_repo.commit_to_time(dependent['commit'])

                # 10. Fail if the dependent commit date is newer than the parent date
                if dep_commit_time > commit_time:
                    # dependent is newer than dependee. Panic.
                    raise RepoAgeConflict

                # 11. Push a tuple onto the queue
                queue.append((dep_commit_time, dependent['commit'], dep_repo.name, dep_repo))
        
            # Keep the queue ordered
            queue.sort(key = lambda tup: tup[0])

            # 12. Go to step 3 (finish loop)

        # 13. Print out summary
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            print("Repo name [{}] commit [{}]".format(reponame, commit))

        # 14. Check out repos and add to lock
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            repo = version_selector_map[reponame]['repo']
            repo.checkout(commit)
            self.lock[reponame] = repo.manifest()
            self.write_lockfile()


    def manifest_path(self):
        return self.path / self.MANIFEST


    def lockfile_path(self):
        return self.path / self.LOCK
        
        
    def write_lockfile(self):
        lockfile_json = json.dumps(self.lock, sort_keys=True, indent=4) + '\n'
        self.lockfile_path().write_text(lockfile_json)

    def read_lockfile(self):
        lockfile_json = self.lockfile_path().read_text()
        self.lock = json.loads(lockfile_json, object_pairs_hook=OrderedDict)

    def write_manifest(self):
        manifest_json = json.dumps(self.manifest, sort_keys=True, indent=4) + '\n'
        self.manifest_path().write_text(manifest_json)
            

    def read_manifest(self):
        manifest_json = self.manifest_path().read_text()
        self.manifest = json.loads(manifest_json)


    # FIXME: Too much going on here, and this couples WorkSpace too closely
    # with git repos. Need to move manifest generation into GitRepo, and allow
    # for instantiating other repo types here
    def add_repo(self, source=None, revision=None):
        source = self.resolve_repomap(source)

        repo = GitRepo.create(source, dest=self.path)
        repo.checkout(revision or repo.get_latest_commit())
        if repo.name not in self.manifest:
            self.manifest.append(repo.manifest())
            print("Adding [{}] to manifest as [{}]".format(source, repo.name))

        self.write_manifest()


    def repo_status(self, source):
        raise NotImplementedError   


    @staticmethod
    def read_repomap(repomap):
        repomap_path = Path(repomap)
        try:
            repomap_json = repomap_path.read_text()
            data = json.loads(repomap_json)
        except Exception as e:
            log.error("Unable to read repomap [{}] for reading: {}".format(repomap_path, e))
            sys.exit(1)

        return data


    def resolve_repomap(self, path):
        if self.repomap and path in self.repomap:
            log.info("Mapped repo [{}] to [{}] using repomap.".format(path, self.repomap[path]))
            path = self.repomap[path]
        
        return path


    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


# Make this a factory for different VCS types
class Package:
    pass


class GitRepo:
    WIT_DEPENDENCY_FILE = "wit-manifest.json"
    instance_map = {}

    def __init__(self, source):
        self.source = source
        self.name = GitRepo.path_to_name(source)
        GitRepo.instance_map[source] = self


    # Instantiate a git object and, if not already done, create a clone
    @classmethod
    def create(cls, source, dest=None, commit=None):
        if source in cls.instance_map:
            self = cls.instance_map[source]
        else:
            self = cls(source)

        # We're already in the root of the workspace, so this will put the
        # clone directly at the top level of the workspace
        self.clone_path = dest / self.name
        if not self.clone_path.is_dir():
            os.mkdir(str(self.clone_path))
            proc = self._git_command("clone", "--no-checkout", str(self.source), str(self.clone_path))
            
            try:
                self._git_check(proc)
            except Exception as e:
                log.error("Error cloning into workspace: {}".format(e))
                sys.exit(1)

        return self


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


    def commit_to_time(self, hash):
        proc = self._git_command('log', '-n1', '--format=%ct', hash)
        self._git_check(proc)

        return proc.stdout.rstrip()
    

    def is_ancestor(self, ancestor, current=None):
        proc = self._git_command("merge-base", "--is-ancestor", ancestor, current or self.get_latest_commit())
        if proc.returncode != 0:
            return False

        else:
            return True


    def get_dependencies(self, hash=None):
        proc = self._git_command("show", "{}:{}".format(hash, GitRepo.WIT_DEPENDENCY_FILE))
        if proc.returncode:
            log.info("No dependency file found in repo [{}:{}]".format(hash, self.clone_path))
            return []

        return json.loads(proc.stdout)
        
    
    def checkout(self, hash):
        proc = self._git_command("checkout", hash)
        self._git_check(proc)

    
    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': str(self.get_latest_commit()),
        }


    def _git_command(self, *args):
        log.debug("Executing [{}] in [{}]".format(' '.join(['git', *args]), self.clone_path))
        proc = subprocess.run(['git', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(self.clone_path), universal_newlines=True)
        return proc


    def _git_check(self, proc):
        if proc.returncode:
            log.error("Command [{}] exited with non-zero exit status [{}]".format(' '.join(proc.args), proc.returncode))
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


    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
