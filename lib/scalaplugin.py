#!/usr/bin/env python3

import json
from collections import OrderedDict
import logging
import subprocess
import os

log = logging.getLogger('wit')


def scala_install_dir(ws):
    return str(ws.path / "scala")


def ivy_cache_dir(ws):
    return str(ws.path / "ivycache")


def coursier_bin(install_dir):
    return "{}/blp-coursier".format(install_dir)


def ivy_deps_file(package):
    return str(package.get_path() / "ivydependencies.json")


def download_bloop_install(install_dir):
    filename = "{}/install.py".format(install_dir)
    if os.path.isfile(filename):
        log.debug("Bloop install script already downloaded!")
    else:
        log.info("Fetching bloop install script...")
        url = "https://github.com/scalacenter/bloop/releases/download/v1.2.5/install.py"
        cmd = ["wget", url]
        proc = subprocess.run(cmd, cwd=install_dir)
        if proc.returncode != 0:
            raise Exception("Error! Unable to download bloop install script from {}".format(url))
    return filename


def install_bloop(install_dir, ivy_cache_dir):

    install_script = download_bloop_install(install_dir)

    environ = os.environ.copy()  # Is this necessary?
    environ["COURSIER_CACHE"] = str(ivy_cache_dir)

    cmd = ["python", install_script, "-d", install_dir]
    proc = subprocess.run(cmd, env=environ)
    if proc.returncode != 0:
        raise Exception("Error! Unable to install bloop!")


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


def resolve_dependencies(projects):
    """
    Determines which dependencies should be fetched
    crossScalaVersions are used to fetch extra versions if any project has a
    scalaVersion that matches the *major* version of the crossScalaVersion
    """
    scalaVersions = unique_list(filter(None, [proj.get('scalaVersion') for proj in projects]))
    deps = []
    for proj in projects:
        version = proj.get('scalaVersion')
        pdeps = proj.get('dependencies') or []
        if version is not None:
            pdeps.append("org.scala-lang:scala-compiler:{}".format(version))
        crossVersions = proj.get('crossScalaVersions') or []
        # Note version can be none, this is okay
        allVersions = [version] + filter_versions(scalaVersions, crossVersions)
        # There may be duplicate deps, dedup later
        allDeps = [expand_scala_dep(v, d) for v in allVersions for d in pdeps]
        deps.extend(allDeps)
    uniqueDeps = unique_list(deps)
    return uniqueDeps


def fetch_ivy_dep(coursier, cache, dep):
    log.debug("Fetching {}...".format(dep))
    cmd = [coursier, "fetch", "--cache", cache, dep]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise Exception("Unable to fetch dependency {}".format(dep))


def fetch_ivy_dependencies(dep_files, install_dir, ivy_cache_dir):
    coursier = coursier_bin(install_dir)

    projects = []
    for fn in dep_files:
        projects.extend(read_ivy_file(fn))

    deps = resolve_dependencies(projects)

    for dep in deps:
        fetch_ivy_dep(coursier, ivy_cache_dir, dep)
