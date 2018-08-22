#!/usr/bin/env python3

import os
import sys
from pathlib import Path
import git
from queue import PriorityQueue
import json
from pprint import pformat
import logging

logging.basicConfig()
log = logging.getLogger(os.path.basename(__file__))
log.setLevel(logging.DEBUG)

class NotAncestorError(Exception):
    pass


class RepoAgeConflict(Exception):
    pass

    
class WorkSpace:
    MANIFEST = "wit_manifest.json"

    def __init__(self):
        self.path = None
        self.manifest = {}


    # create a new workspace root given a name.
    def create(self, name):
        self.path = Path.cwd() / name
        os.mkdir(self.path)
        os.chdir(self.path)

        self.write_manifest()


    # find a workspace root by iteratively walking up the path
    # until a manifest file is found.
    def find(self):
        cwd = Path.cwd().resolve()
        for p in ([cwd] + list(cwd.parents)):
            print("Checking [{}]".format(p / self.MANIFEST))
            if Path(p / self.MANIFEST).is_file():
                log.debug("Found workspace at [{}].format(p)")
                self.path = p

                os.chdir(p)
                self.read_manifest()
                return
        
        raise FileNotFoundError("Couldn't find manifest file")


    def update(self):
        # This algorithm courtesy of Wes
        # https://sifive.atlassian.net/browse/FRAM-1
        # 1. Initialize an empty version selector map
        version_selector_map = {}

        # 2. For every existing repo put a tuple (name, hash, commit time) into queue
        queue = []
        for reponame in self.manifest:
            source = self.manifest[reponame]['source']
            commit = self.manifest[reponame]['commit']
            repo = GitRepo.create(source)
            commit_time = repo.commit_to_time(commit)

            queue.append((commit_time, commit, reponame, repo))
        
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
            # convenience but is poor data hygiene. Need to think of a beter
            # solution here.
            version_selector_map[reponame] = {
                'commit': commit,
                'repo': repo
            }

            # 7. Examine the repository's children
            dependencies = repo.get_dependencies(hash=commit)
            log.debug("Dependencies for [{}]: [{}]".format(repo.clone_path, dependencies))

            for dependent in dependencies:
                # 8. Clone without checking out the dependency
                dep_repo = GitRepo.create(source=dependent['path'], explicit=False)
                
                # 9. Find the committer date
                dep_commit_time = dep_repo.commit_to_time(dependent['hash'])

                # 10. Fail if the dependent commit date is newer than the parent date
                if dep_commit_time > commit_time:
                    # dependent is newer than dependee. Panic
                    raise RepoAgeConflict

                # 11. Push a tuple onto the queue
                queue.append((dep_commit_time, dependent['hash'], dep_repo.name, dep_repo))
        
            # Keep the queue ordered
            queue.sort(key = lambda tup: tup[0])

            # 12. Go to step 3 (finish loop)

        # 13. Print out summary
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            print("Repo name [{}] commit [{}]".format(reponame, commit))

        # 14. Check out repos and add to manifest
        for reponame in version_selector_map:
            commit = version_selector_map[reponame]['commit']
            repo = version_selector_map[reponame]['repo']
            repo.checkout(commit)
            self.manifest[reponame] = repo.manifest()
            self.write_manifest()


    def write_manifest(self):
        with open(self.MANIFEST, "w") as manifest:
            json.dump(self.manifest, manifest, sort_keys=True, indent=4)
            

    def read_manifest(self):
        with open(self.MANIFEST, "r") as manifest:
            self.manifest = json.load(manifest)


    # FIXME: Too much going on here, and this couples WorkSpace too closely
    # wit git repos. Need to move manifest generation into GitRepo, and allow
    # for instantiating other repo types here
    def add_repo(self, source=None, revision=None, explicit=False):
        repo = GitRepo.create(source, explicit=explicit)
        repo.checkout(revision)
        if repo.name not in self.manifest:
            self.manifest[repo.name] = repo.manifest()
            print("Adding [{}] to manifest as [{}]".format(source, repo.name))

        self.write_manifest()


    def repo_status(self, source):
        raise NotImplementedError
        

    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)


# Make this a factory for different VCS types
class Package:
    pass


class GitRepo:
    WIT_DEPENDENCIES = "wit_dependencies.json"
    instance_map = {}

    def __init__(self, source, explicit=False):
        self.source = source
        self.explicit = explicit
        self.name = GitRepo.path_to_name(source)
        GitRepo.instance_map[source] = self


    # Instantiate a git object and, if not already done, create a clone
    @classmethod
    def create(cls, source, explicit=False, commit=None):
        if source in cls.instance_map:
            self = cls.instance_map[source]
        else:
            self = cls(source, explicit=explicit)

        # We're already in the root of the workspace, so this will put the
        # clone directly at the top level of the workspace
        self.clone_path = Path(self.name).resolve()
        if self.clone_path.is_dir():
            self.repo = git.Repo(str(self.clone_path))
        
        else:
            self.repo = git.Repo.clone_from(
                self.source, self.clone_path, no_checkout=True)
        
        return self


    def get_latest_commit(self):
        return self.repo.commit()


    def commit_to_time(self, hash):
        return self.repo.commit(hash).committed_date
    

    def is_ancestor(self, ancestor, current=None):
        return self.repo.is_ancestor(ancestor, current or self.repo.commit())
            

    def get_dependencies(self, hash=None):
        try:
            wit_dependencies = self.repo.git.show("{}:{}".format(hash, GitRepo.WIT_DEPENDENCIES))
        except:
            print("No dependencies found in repo [{}:{}].".format(self.clone_path, hash))
            return []

        return json.loads(wit_dependencies)
        
    
    def checkout(self, hash):
        print("Checking out commit [{}] in repo [{}]".format(hash, self.repo.git_dir))
        self.repo.git.checkout(hash)

    
    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': str(self.repo.commit()),
            'explicit': self.explicit
        }

    
    @staticmethod
    def path_to_name(path):
        return Path(path).name.replace('.git', '')


    # Enable prettyish-printing of the class
    def __repr__(self):
        return pformat(vars(self), indent=4, width=1)
