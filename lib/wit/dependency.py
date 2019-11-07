import re
from datetime import datetime
from pathlib import Path
from typing import List  # noqa: F401
from collections import OrderedDict
from .common import WitUserError
from .package import Package
from .witlogger import getLogger
from .gitrepo import BadSource

log = getLogger()


class DependeeNewerThanDepender(WitUserError):
    def __init__(self, depender, dependee):
        self.depender = depender
        self.dependee = dependee

    def __str__(self):
        return ("Depender {} is older than its dependee {}\n"
                "This should not happen, but it may be caused by a ficticious "
                "clock time being stored in a commit.\n This should be fixable "
                "by creating a new commit in the dependee then depending on "
                "that commit."
                "".format(self.depender.id(), self.dependee.id()))


class Dependency:
    """ A dependency that a Package specifies. From wit-manifest.json and wit-workspace.js """

    def __init__(self, name, source, specified_revision=None):
        self.source = source
        self.specified_revision = specified_revision or "HEAD"
        self.name = name or Dependency.infer_name(source)
        self.package = None  # type: Package
        self.dependents = []  # type: List[Package]

    def resolve_deps(self, wsroot, repo_paths, download, source_map, packages, queue, errors):
        source_map = source_map.copy()
        packages = packages.copy()
        queue = queue.copy()
        errors = errors.copy()
        subdeps = self.package.get_dependencies()
        log.debug("Dependencies for [{}]: [{}]".format(self.name, subdeps))
        for subdep in subdeps:
            try:
                subdep.load(packages, repo_paths, wsroot, download)
            except BadSource as e:
                errors.append(e)
                continue

            sources_conflict_check(subdep, source_map)

            source_map[subdep.name] = subdep.package.resolve_source(subdep.source)

            if subdep.package.repo is None:
                continue

            if subdep.get_commit_time() > self.get_commit_time():
                errors.append(DependeeNewerThanDepender(self, subdep))
                continue

            commit_time = subdep.get_commit_time()
            queue.append((commit_time, subdep))

        queue.sort(key=lambda tup: tup[0])

        return source_map, packages, queue, errors

    def __key(self):
        return (self.source, self.specified_revision, self.name)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()

    @staticmethod
    def infer_name(source):
        return Path(source).name.replace('.git', '')

    # NB: mutates packages[self.name]
    def load(self, packages, repo_paths, wsroot, download):
        if self.name in packages:
            self.package = packages[self.name]
        else:
            self.package = Package(self.name, repo_paths)
            packages[self.name] = self.package
        self.package.add_dependent(self)

        self.package.load(wsroot, download, source=self.source, revision=self.specified_revision)

    def add_dependent(self, dependent):
        if dependent not in self.dependents:
            self.dependents.append(dependent)

    def get_commit_time(self):
        return datetime.utcfromtimestamp(int(self.package.repo.commit_to_time(
            self.specified_revision)))

    def manifest(self):
        res = OrderedDict()
        res['name'] = self.name
        res['source'] = self.source
        res['commit'] = self.specified_revision
        return res

    # used before saving to manifests/lockfiles
    def resolved(self):
        return Dependency(self.name, self.source, self.resolved_rev())

    # Check if the Dependency has a Package and repo on disk
    def _is_bound(self) -> bool:
        return self.package is not None and self.package.repo is not None

    def resolved_rev(self):
        if not self._is_bound():
            raise Exception("Cannot resolve dependency that is unbound to disk")
        return self.package.repo.get_commit(self.specified_revision)

    def __repr__(self):
        return "Dep({})".format(self.id())

    def short_revision(self):
        if self.package and self.package.repo:
            if self.package.repo.is_hash(self.specified_revision):
                return self.package.repo.get_shortened_rev(self.specified_revision)
            return self.specified_revision
        return self.specified_revision[:8]

    def id(self):
        return "{}::{}".format(self.name, self.short_revision())

    def get_id(self):
        return "dep_"+re.sub(r"([^\w\d])", "_", self.id())

    def crawl_dep_tree(self, wsroot, repo_paths, packages):
        fancy_tag = self.id()
        self.load(packages, repo_paths, wsroot, False)
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


def sources_conflict_check(dep, source_map):
    if dep.name in source_map:
        dep_resolved_source = dep.package.resolve_source(dep.source)
        if dep_resolved_source != source_map[dep.name]:
            if not dep.package.dependents_have_common_ancestor():
                raise WitUserError(("Two dependencies have the same name "
                                    "but an unrelated git history:\n"
                                    "  {}\n"
                                    "  {}\n"
                                    "".format(dep_resolved_source,
                                              source_map[dep.name])))


def parse_dependency_tag(s):
    parts = s.split('::')
    source = parts[0]
    rev = parts[1] if parts[1:] else None

    return source, rev


def manifest_item_to_dep(obj):
    # source can be done due to repo path
    return Dependency(obj['name'], obj.get('source', None), obj['commit'])
