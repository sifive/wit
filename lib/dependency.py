import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List  # noqa: F401
from lib.common import passbyval
from lib.package import Package
from lib.witlogger import getLogger

log = getLogger()


class Dependency:
    '''The version of a repo that is depended upon

    '''

    def __init__(self, name, source, revision=None):
        self.source = source
        self.revision = revision or "HEAD"
        self.name = name or Dependency.infer_name(source)
        self.package = None  # type: Package
        self.dependents = []  # type: List[Package]

    @passbyval
    def resolve_deps(self, wsroot, repo_paths, force_root, source_map, packages, queue):
        subdeps = self.package.get_dependencies()
        log.debug("Dependencies for [{}]: [{}]".format(self.name, subdeps))
        for subdep in subdeps:
            subdep.load_package(wsroot, repo_paths, packages, force_root)

            if subdep.get_commit_time() > self.get_commit_time():
                log.error("Repo [{}] has a dependent that is newer than the source. "
                          "This should not happen.\n".format(subdep.name))
                sys.exit(1)

            if subdep.name in source_map:
                if subdep.package.source != source_map[subdep.name]:
                    log.error("Dependency [{}] has multiple conflicting paths:\n"
                              "  {}\n"
                              "  {}\n".format(subdep.name, subdep.package.source,
                                              source_map[subdep.name]))
                    sys.exit(1)
            source_map[subdep.name] = subdep.package.source

            commit_time = subdep.get_commit_time()
            queue.append((commit_time, subdep))

        queue.sort(key=lambda tup: tup[0])

        return source_map, packages, queue

    def __key(self):
        return (self.source, self.revision, self.name)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()

    @staticmethod
    def infer_name(source):
        return Path(source).name.replace('.git', '')

    def load_package(self, wsroot, repo_paths, packages, force_root):
        if self.name in packages:
            self.package = packages[self.name]
        else:
            self.package = Package(self.name, self.source, self.revision)
        self.package.add_dependent(self)
        self.package.load(wsroot, repo_paths, force_root, self.revision)
        self.revision = self.package.repo.get_commit(self.revision)

    def add_dependent(self, dependent):
        if dependent not in self.dependents:
            self.dependents.append(dependent)

    def get_commit_time(self):
        return datetime.utcfromtimestamp(int(self.package.repo.commit_to_time(self.revision)))

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.revision,
        }

    def __repr__(self):
        return "Dep({})".format(self.tag())

    def tag(self):
        return "{}::{}".format(self.name, self.revision[:8])

    def get_id(self):
        return "dep_"+re.sub(r"([^\w\d])", "_", self.tag())

    def crawl_dep_tree(self, wsroot, repo_paths, packages):
        fancy_tag = "{}::{}".format(self.name, self.revision[:8])
        self.load_package(wsroot, repo_paths, packages, False)
        if self.package.theory_revision != self.revision:
            fancy_tag += "->{}".format(self.package.theory_revision[:8])
            return {'': fancy_tag}

        tree = {'': fancy_tag}
        try:
            subdeps = self.package.get_dependencies()
        except Exception:
            log.error("aaa")
            subdeps = []
        for subdep in subdeps:
            tree[subdep.get_id()] = subdep.crawl_dep_tree(wsroot, repo_paths, packages)
        return tree


def parse_dependency_tag(s):
    # TODO Could speed up validation
    #   - use git ls-remote to validate remote exists
    #   - use git ls-remote to validate revision for tags and branches
    #   - if github repo, check if page exists (or if you get 404)
    parts = s.split('::')
    source = parts[0]
    rev = parts[1] if parts[1:] else None

    return source, rev


def manifest_item_to_dep(obj):
    # source can be done due to repo path
    return Dependency(obj['name'], obj.get('source', None), obj['commit'])
