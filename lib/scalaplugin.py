#!/usr/bin/env python3

import json
from collections import OrderedDict
import logging
import subprocess
import os
import urllib.request
from typing import List, Optional
import tempfile
import shutil
from pathlib import Path
import filecmp

log = logging.getLogger('wit')


def scala_install_dir(path):
    return str(path / "scala")


def ivy_cache_dir(path):
    return str(path / "ivycache")


def coursier_bin(install_dir):
    return "{}/coursier".format(install_dir)


def ivy_deps_file(package):
    return str(package / "ivydependencies.json")


def pretty_cmd(cmd):
    def wrap(s):
        return '"{}"'.format(s) if ' ' in s else s
    return ' '.join([wrap(s) for s in cmd])


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


def recursive_list_files(directory) -> List[str]:
    """
    Recursively list [only] files in a directory
    """
    return [os.path.join(d, f) for d, _, fs in os.walk(directory) for f in fs]


def atomic_sync_copy(src, dst, tmproot) -> None:
    """
    Copies src directory to dst
    Does a "sync" copy where it only copies if dst files don't exist or differ
    from the src files
    Will create parent directories if they do not exist
    """
    log.debug('Syncing {} to {}'.format(src, dst))
    src_files = recursive_list_files(src)
    dst_files = recursive_list_files(dst)
    dst_lookup = {os.path.relpath(f, dst): f for f in dst_files}

    for src_file in src_files:
        relpath = os.path.relpath(src_file, src)
        dst_file = "{}/{}".format(dst, relpath)
        copy = False
        if relpath in dst_lookup:
            # File exists at destination, check if it has changed
            if filecmp.cmp(src_file, dst_file, shallow=False):
                log.debug('{} exists and contents match!'.format(dst_file))
                copy = False
            else:
                log.debug("{} and {} differ".format(src_file, dst_file))
                copy = True
        else:
            log.debug("{} does not exist!".format(dst_file))
            copy = True

        if copy:
            log.debug("Copying {} to {}".format(src_file, dst_file))
            parent = os.path.dirname(dst_file)
            if not os.path.exists(parent):
                log.debug("Destination directory {} does not exist! Creating it.".format(parent))
                # exist_ok avoids race condition error
                os.makedirs(parent, mode=0o755, exist_ok=False)
            f = tempfile.NamedTemporaryFile(mode='w+b', dir=parent, delete=False)
            shutil.copy(src_file, f.name)
            os.rename(f.name, dst_file)


def copy_ivy_deps(deps: List[dict], cache: str) -> None:
    """
    Copies dependencies from system ivy cache to local cache
    Uses 'v1' as the marker for beginning of cache path
    """
    for dep in deps:
        coord = dep["coord"]
        cache_path = dep["file"]
        if coord is not None and cache_path is not None:
            name = coord.split(":")[1]
            split_path = cache_path.split(name, 1)
            # '/home/user/.cache/coursier/v1/https/repo1.maven.org/maven2/org/scala-lang/' ->
            #   '/https/repo1.maven.org/maven2/org/scala-lang/'
            cache_prefix = split_path[0].split("v1")[1]
            # '/2.12.8/scala-reflect-2.12.8.jar' -> '2.12.8'
            version = split_path[1].split('/')[1]
            src = '{}{}'.format(cache_path.split(version, 1)[0], version)
            dst = '{}{}/{}/{}'.format(cache, cache_prefix, name , version)
            atomic_sync_copy(src, dst, ".")
        else:
            log.debug("Skipping {}, coord or file was None".format(dep))


def fetch_ivy_deps(coursier: str, cache: str, deps: tuple) -> None:
    """
    Uses coursier to fetch ivy dependencies
    Will attempt to put things in COURSIER_CACHE by default and then copy them to cache
    If that fails, will just download directly to the local cache
    """
    def do_fetch(local: bool) -> Optional[dict]:
        with tempfile.NamedTemporaryFile('r') as info_file:
            base_cmd = [coursier, "fetch", "-q", "-p", "-j", info_file.name]
            cmd = base_cmd + ["--cache", cache] if local else base_cmd
            full_cmd = cmd + list(deps)
            log.debug("Coursier [{}]...".format(pretty_cmd(full_cmd)))
            proc = subprocess.run(full_cmd, stdout=subprocess.PIPE, universal_newlines=True)
            info = json.load(info_file)
            if proc.returncode == 0:
                return info
            else:
                return None

    # Try cached
    info = do_fetch(False)
    if info is None:
        log.debug("Cached fetch failed, trying local...")
        res = do_fetch(True)
        if res is None:
            raise Exception("Unable to fetch dependencies [{}]".format(", ".join(deps)))
    else:
        copy_ivy_deps(info["dependencies"], cache)


def fetch_ivy_dependencies(dep_files, install_dir, ivy_cache_dir):
    coursier = coursier_bin(install_dir)

    projects = []
    for fn in dep_files:
        projects.extend(read_ivy_file(fn))

    dep_groups = resolve_dependencies(projects)

    for group in dep_groups:
        fetch_ivy_deps(coursier, ivy_cache_dir, group)
