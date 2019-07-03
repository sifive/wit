import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List  # noqa: F401
from .common import passbyval
from .package import Package
from .witlogger import getLogger

log = getLogger()


class Dependency:
    """ A dependency that a Package specifies. From wit-manifest.json and wit-workspace.js """

    def __init__(self, name, source, specified_revision=None):
        self.source = source
        self.revision = None
        self.specified_revision = specified_revision or "HEAD"
        self.name = name or Dependency.infer_name(source)
        self.package = None  # type: Package
        self.dependents = []  # type: List[Package]

    @passbyval
    def resolve_deps(self, wsroot, repo_paths, download, source_map, packages, queue):
        subdeps = self.package.get_dependencies()
        log.debug("Dependencies for [{}]: [{}]".format(self.name, subdeps))
        for subdep in subdeps:
            subdep.load_package(packages, repo_paths)
            subdep.package.load_repo(wsroot, download)

            if subdep.name in source_map:
                if subdep.package.source != source_map[subdep.name]:
                    log.error("Dependency [{}] has multiple conflicting paths:\n"
                              "  {}\n"
                              "  {}\n".format(subdep.name, subdep.package.source,
                                              source_map[subdep.name]))
                    sys.exit(1)

            source_map[subdep.name] = subdep.package.source

            if subdep.package.repo is None:
                continue

            if subdep.get_commit_time() > self.get_commit_time():
                log.error("Repo [{}] has a dependent that is newer than the source. "
                          "This should not happen.\n".format(subdep.name))
                sys.exit(1)

            commit_time = subdep.get_commit_time()
            queue.append((commit_time, subdep))

        queue.sort(key=lambda tup: tup[0])

        return source_map, packages, queue

    def __key(self):
        return (self.source, self.specified_revision, self.name)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()

    @staticmethod
    def infer_name(source):
        return Path(source).name.replace('.git', '')

    # wsroot, repo_paths, packages, force_root
    def load_package(self, packages, repo_paths):
        """
        Bind itself to a package, using one in the `packages` argument if available.
        This will also add itself as a dependent of the package
        """
        if self.name in packages:
            self.package = packages[self.name]
        else:
            self.package = Package(self.name, self.source, self.specified_revision, repo_paths)
        self.package.add_dependent(self)

    def add_dependent(self, dependent):
        if dependent not in self.dependents:
            self.dependents.append(dependent)

    def get_commit_time(self):
        return datetime.utcfromtimestamp(int(self.package.repo.commit_to_time(
            self.specified_revision)))

    def manifest(self):
        return {
            'name': self.name,
            'source': self.source,
            'commit': self.specified_revision,
        }

    # used before saving to manifests/lockfiles
    def resolved(self):
        if self.package is None or self.package.repo is None:
            raise Exception("Cannot resolve dependency that us unbound to disk")
        return Dependency(self.name, self.source, self.resolved_rev())

    def resolved_rev(self):
        if self.package.repo is None or self.package.repo is None:
            raise Exception("Cannot resolve dependency that is unbound to disk")
        return self.package.repo.get_commit(self.specified_revision)

    def __repr__(self):
        return "Dep({})".format(self.tag())

    def short_revision(self):
        if self.package and self.package.repo:
            if self.package.repo.is_hash(self.specified_revision):
                return self.package.repo.get_shortened_rev(self.specified_revision)
            return self.specified_revision
        return self.specified_revision[:8]

    def tag(self):
        return "{}::{}".format(self.name, self.short_revision())

    def get_id(self):
        return "dep_"+re.sub(r"([^\w\d])", "_", self.tag())

    def crawl_dep_tree(self, wsroot, repo_paths, packages):
        fancy_tag = "{}::{}".format(self.name, self.short_revision())
        self.load_package(packages, repo_paths)
        self.package.load_repo(wsroot)
        if self.package.repo is None:
            return {'': "{} \033[91m(missing)\033[m".format(fancy_tag)}
        if self.package.revision != self.resolved_rev():
            fancy_tag += "->{}".format(self.package.short_revision())
            return {'': fancy_tag}

        tree = {'': fancy_tag}
        subdeps = self.package.get_dependencies()
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
