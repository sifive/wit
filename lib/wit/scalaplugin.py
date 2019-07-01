#!/usr/bin/env python3

import json
from collections import OrderedDict
import subprocess
import os
import urllib.request
from .witlogger import getLogger
from typing import List

log = getLogger()


def scala_install_dir(path):
    return str(path / "scala")


def ivy_cache_dir(path):
    return str(path / "ivycache")


def coursier_bin(install_dir):
    return "{}/coursier".format(install_dir)


def ivy_deps_file(package):
    return str(package / "ivydependencies.json")


def install_coursier(install_dir):
    version = "1.1.0-M14-6"
    path = "io/get-coursier/coursier-cli_2.12/{}/coursier-cli_2.12-{}-standalone.jar".format(
           version, version)
    filename = coursier_bin(install_dir)
    url = "http://central.maven.org/maven2/{}".format(path)
    print("Downloading from {}".format(url))
    urllib.request.urlretrieve(url, filename)
    os.chmod(filename, 0o755)


def split_scala_version(version):
    parts = version.split('.')
    if len(parts) != 3:
        raise Exception("Malformed Scala Version {}".format(version))
    if parts[0] != "2":
        raise Exception("Only Scala 2.X.Y are supported!")
    return parts


def get_major_version(version):
    return '.'.join(split_scala_version(version)[:2])


def unique_list(l):
    d = OrderedDict()
    for e in l:
        d[e] = None
    return list(d.keys())


# TODO More validation?
def expand_scala_dep(version, dep):
    parts = dep.split(':')

    def errMalformed():
        raise Exception("Malformed IvyDependency {}!".format(dep))

    def assertHasScala():
        if version is None:
            raise Exception("Must specify scalaVersion for IvyDependency {}!".format(dep))

    if len(parts) == 3:
        # Java dep
        return dep
    elif len(parts) == 4:
        # Scala Dep
        c = parts.pop(1)
        if c != '':
            errMalformed()
        assertHasScala()
        sv = split_scala_version(version)
        parts[1] = "{}_{}.{}".format(parts[1], sv[0], sv[1])
        return ':'.join(parts)
    elif len(parts) == 5:
        c = parts.pop(1)
        d = parts.pop(1)
        if c != '' or d != '':
            errMalformed()
        assertHasScala()
        parts[1] = "{}_{}".format(parts[1], version)
        return ':'.join(parts)
    else:
        errMalformed()


# TODO JSON validation/schema?
def read_ivy_file(filename):
    with open(filename, 'r') as json_file:
        data = json.load(json_file, object_pairs_hook=OrderedDict)
        # Ignore project names, could be duplicates?
        return list(data.values())
    return []


def filter_versions(allVers, myVers):
    """
    Determines what versions should be kept out of myVers based on major Scala version
    """
    majorVersions = set([get_major_version(ver) for ver in allVers])
    return [ver for ver in myVers if get_major_version(ver) in majorVersions]


def resolve_dependencies(projects: List[dict]) -> List[tuple]:
    """
    Determines which dependencies should be fetched
    crossScalaVersions are used to fetch extra versions if any project has a
    scalaVersion that matches the *major* version of the crossScalaVersion
    """
    scalaVersions = unique_list(filter(None, [proj.get('scalaVersion') for proj in projects]))
    dep_groups = []
    for proj in projects:
        version = proj.get('scalaVersion')
        pdeps = proj.get('dependencies') or []
        crossVersions = proj.get('crossScalaVersions') or []
        # Note version can be none, this is okay
        allVersions = [version] + filter_versions(scalaVersions, crossVersions)
        for ver in allVersions:
            deps = [expand_scala_dep(ver, dep) for dep in pdeps]
            if ver is not None:
                deps.append("org.scala-lang:scala-compiler:{}".format(ver))
            dep_groups.append(tuple(deps))
    unique_groups = unique_list(dep_groups)
    return unique_groups


def fetch_ivy_deps(coursier: str, cache: str, deps: tuple) -> None:
    log.debug("Fetching [{}]...".format(", ".join(deps)))
    cmd = [coursier, "fetch", "--cache", cache] + list(deps)
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise Exception("Unable to fetch dependencies [{}]".format(", ".join(deps)))


def fetch_ivy_dependencies(dep_files, install_dir, ivy_cache_dir):
    coursier = coursier_bin(install_dir)

    projects = []
    for fn in dep_files:
        projects.extend(read_ivy_file(fn))

    dep_groups = resolve_dependencies(projects)

    for group in dep_groups:
        fetch_ivy_deps(coursier, ivy_cache_dir, group)
