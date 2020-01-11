#!/usr/bin/env python3

import json
from collections import OrderedDict
import subprocess
import os
import urllib.request
from .witlogger import getLogger
from typing import List, Tuple
import sys

log = getLogger()


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SCRIPT_NAME = os.path.basename(__file__)


def _report_old_version(name):
    raise Exception("Removed function {} called, please upgrade api-scala-sifive".format(name))


# Removed functions that might be called by old versions of api-scala-sifive
def bloop_home(install_dir):
    _report_old_version("bloop_home")


def run_bloop(coursier, bloop_home, cache, args):
    _report_old_version("run_bloop")


def scala_install_dir(path):
    return str(path / "scala")


def ivy_cache_dir(path):
    return str(path / "ivycache")


def coursier_bin(install_dir):
    return "{}/coursier".format(install_dir)

def mill_bin(install_dir):
    return "{}/mill".format(install_dir)



def ivy_deps_file(directory):
    return "{}/ivydependencies.json".format(directory)


def scala_version_dep(version):
    return "org.scala-lang:scala-compiler:{}".format(version)


def get_bloop_artifacts():
    version = "2.12.8"
    # The version of bsp4s that bloop depeneds on isn't published so we override it
    deps = ["ch.epfl.scala::bloop-frontend:1.2.5", "ch.epfl.scala::bsp4s:2.0.0-M3"]
    expanded = [expand_scala_dep(version, dep) for dep in deps]
    allDeps = expanded + [scala_version_dep(version)]
    return allDeps


def bloop_classpath(coursier, cache, offline=True):
    deps = get_bloop_artifacts()
    offlineArgs = ["-m", "offline"] if offline else []
    cmd = [coursier, "fetch"] + offlineArgs + ["--classpath", "--cache", cache] + deps
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    return proc.stdout.rstrip()


def fetch_scala_compiler_bridge(coursier, bloop_home, cache, version):
    classpath = bloop_classpath(coursier, cache, offline=False)
    if classpath is None:
        return 1
    fetcher = "{}/scala-bridge-fetcher_2.12-0.1.0.jar".format(SCRIPT_DIR)
    classpath = classpath + ":" + fetcher
    # Make sure bloop_home exists
    os.makedirs(bloop_home, mode=0o755, exist_ok=True)
    set_home = "-Duser.home={}".format(bloop_home)
    cmd = ["java", set_home, "-cp", classpath, "sifive.ScalaCompilerBridgeFetcher", version]
    # This creates a target directory, put it in bloop_home
    proc = subprocess.Popen(cmd, cwd=bloop_home)
    proc.wait()
    return proc.returncode == 0


def calc_sha256(filename):
    import hashlib
    block_size = 65536
    hasher = hashlib.sha256()
    with open(filename, 'rb') as f:
        buf = f.read(block_size)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(block_size)
    return hasher.hexdigest()


def install_coursier(install_dir, jar=False):
    release_host = "https://github.com/coursier/coursier/releases/download"
    version = "v2.0.0-RC4-1"

    platform = sys.platform
    # https://docs.python.org/3.5/library/platform.html#platform.architecture
    is_64bit = sys.maxsize > 2**32

    name = ""
    sha256 = None
    if platform == 'darwin' and is_64bit and not jar:
        name = "cs-x86_64-apple-darwin"
        sha256 = "3ba4f90d912497cf57dfdcc340468cbbaa26a9bd3df3be369b4f118b16305f8b"
    elif platform == 'linux' and is_64bit and not jar:
        name = "cs-x86_64-pc-linux"
        sha256 = "81d72ee774f5261169c5919bbc7ff6cedd7a84b7271ecb4ee16b332d6f91a4a4"
    else:
        name = "coursier.jar"
        sha256 = "ba197aec96b104fb1f8775e23f01435b865d9af3d40a9ad097ea9dd5dfcf04d1"

    url = '{}/{}/{}'.format(release_host, version, name)

    filename = coursier_bin(install_dir)

    print("Downloading from {}".format(url))
    urllib.request.urlretrieve(url, filename)

    actual_sha256 = calc_sha256(filename)
    if actual_sha256 != sha256:
        msg = "Error! SHA256 mismatch for {}!".format(filename)
        suggestion = "Please delete the 'scala/' directory and re-run fetch-scala!"
        extra_info = "  Expected: {}\n  Got:      {}".format(sha256, actual_sha256)
        raise Exception("{} {}\n{}".format(msg, suggestion, extra_info))

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


def resolve_dependencies(projects: List[dict]) -> Tuple[List[tuple], List[str]]:
    """
    Determines which dependencies should be fetched
    crossScalaVersions are used to fetch extra versions if any project has a
    scalaVersion that matches the *major* version of the crossScalaVersion
    """
    scalaVersions = unique_list(filter(None, [proj.get('scalaVersion') for proj in projects]))
    dep_groups = []
    scala_versions = []
    for proj in projects:
        version = proj.get('scalaVersion')
        if version is not None:
            scala_versions.append(version)
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
    unique_versions = unique_list(scala_versions)
    return (unique_groups, unique_versions)


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

    (dep_groups, scala_versions) = resolve_dependencies(projects)

    bhome = bloop_home(install_dir)
    for ver in scala_versions:
        assert fetch_scala_compiler_bridge(coursier, bhome, ivy_cache_dir, ver)

    for group in dep_groups:
        fetch_ivy_deps(coursier, ivy_cache_dir, group)
