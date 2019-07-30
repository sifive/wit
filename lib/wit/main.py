#!/usr/bin/env python3

# TODO:
# * Error handling
# * Log all commands into workspace
# * De-couple WorkSpace from GitRepos
# * Write unit tests
# * Handle corrupt dependencies.json
# * Handle exceptional conditions
# * Use a real logger
# * Handle partial sha1s correctly

import subprocess
import sys
import argparse
import os
from .witlogger import getLogger
from .workspace import WorkSpace, PackageNotInWorkspaceError
from .dependency import parse_dependency_tag, Dependency
from .inspect import inspect_tree
from . import scalaplugin
from pathlib import Path
from typing import cast, List, Tuple  # noqa: F401
from .common import error, WitUserError, print_errors
from .gitrepo import GitRepo, GitCommitNotFound
from .manifest import Manifest
from .package import WitBug
import re

log = getLogger()


class NotAPackageError(WitUserError):
    pass


def main() -> None:
    # Parse arguments. Create sub-commands for each of the modes of operation
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='''Specify level of verbosity
-v:    verbose
-vv:   debug
-vvv:  trace
-vvvv: spam
''')
    parser.add_argument('--version', action='store_true', help='Print wit version')
    parser.add_argument('-C', dest='cwd', type=chdir, metavar='path', help='Run in given path')
    parser.add_argument('--repo-path', default=os.environ.get('WIT_REPO_PATH'),
                        help='Specify alternative paths to look for packages')
    parser.add_argument('--prepend-repo-path', default=None,
                        help='Prepend paths to the default repo search path.')

    subparsers = parser.add_subparsers(dest='command', help='sub-command help')

    init_parser = subparsers.add_parser('init', help='create workspace')
    init_parser.add_argument('--no-update', dest='update', action='store_false',
                             help=('don\'t run update upon creating the workspace'
                                   ' (implies --no-fetch-scala)'))
    init_parser.add_argument('--no-fetch-scala', dest='fetch_scala', action='store_false',
                             help='don\'t run fetch-scala upon creating the workspace')
    init_parser.add_argument('-a', '--add-pkg', metavar='repo[::revision]', action='append',
                             type=parse_dependency_tag, help='add an initial package')
    init_parser.add_argument('workspace_name')

    add_pkg_parser = subparsers.add_parser('add-pkg', help='add a package to the workspace')
    add_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=parse_dependency_tag)

    update_pkg_parser = subparsers.add_parser('update-pkg', help='update the revision of a '
                                              'previously added package')
    update_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=parse_dependency_tag)

    add_dep_parser = subparsers.add_parser('add-dep', help='add a dependency to a package')
    add_dep_parser.add_argument('pkg', metavar='pkg[::revision]', type=parse_dependency_tag)

    update_dep_parser = subparsers.add_parser('update-dep', help='update revision of a dependency '
                                              'in a package')
    update_dep_parser.add_argument('pkg', metavar='pkg[::revision]', type=parse_dependency_tag)

    subparsers.add_parser('status', help='show status of workspace')
    subparsers.add_parser('update', help='update git repos')

    inspect_parser = subparsers.add_parser('inspect', help='inspect lockfile')
    inspect_group = inspect_parser.add_mutually_exclusive_group()
    inspect_group.add_argument('--tree', action="store_true")
    inspect_group.add_argument('--dot', action="store_true")

    subparsers.add_parser('fetch-scala', help='Fetch dependencies for Scala projects')

    args = parser.parse_args()
    if args.verbose == 4:
        log.setLevel('SPAM')
    elif args.verbose == 3:
        log.setLevel('TRACE')
    elif args.verbose == 2:
        log.setLevel('DEBUG')
    elif args.verbose == 1:
        log.setLevel('VERBOSE')
    else:
        log.setLevel('INFO')

    log.debug("Log level: {}".format(log.getLevelName()))

    if args.prepend_repo_path and args.repo_path:
        args.repo_path = " ".join([args.prepend_repo_path, args.repo_path])
    elif args.prepend_repo_path:
        args.repo_path = args.prepend_repo_path

    if args.version:
        version()
        sys.exit(0)

    try:
        # FIXME: This big switch statement... no good.
        if args.command == 'init':
            create(args)

        else:
            # These commands assume the workspace already exists. Error out if the
            # workspace cannot be found.
            try:
                ws = WorkSpace.find(Path.cwd(), parse_repo_path(args))

            except FileNotFoundError as e:
                log.error("Unable to find workspace root [{}]. Cannot continue.".format(e))
                sys.exit(1)

            if args.command == 'add-pkg':
                add_pkg(ws, args)

            elif args.command == 'update-pkg':
                update_pkg(ws, args)

            elif args.command == 'add-dep':
                add_dep(ws, args)

            elif args.command == 'update-dep':
                update_dep(ws, args)

            elif args.command == 'status':
                status(ws, args)

            elif args.command == 'update':
                update(ws, args)

            elif args.command == 'fetch-scala':
                fetch_scala(ws, args, agg=False)

            elif args.command == 'inspect':
                if args.dot or args.tree:
                    inspect_tree(ws, args)
                else:
                    log.error('`wit inspect` must be run with a flag')
                    print(parser.parse_args('inspect -h'.split()))
                    sys.exit(1)
    except WitUserError as e:
        error(e)
    except AssertionError as e:
        raise WitBug(e)


def parse_repo_path(args):
    return args.repo_path.split(' ') if args.repo_path else []


def chdir(s) -> None:
    def err(msg):
        raise argparse.ArgumentTypeError(msg)
    try:
        os.chdir(s)
    except FileNotFoundError:
        err("'{}' path not found!".format(s))
    except NotADirectoryError:
        err("'{}' is not a directory!".format(s))


def create(args) -> None:
    if args.add_pkg is None:
        dependencies = []  # type: List[Tuple[str, str]]
    else:
        dependencies = args.add_pkg

    ws = WorkSpace.create(args.workspace_name, parse_repo_path(args))
    for dep in dependencies:
        ws.add_dependency(dep)

    if args.update:
        update(ws, args)

        if args.fetch_scala:
            fetch_scala(ws, args, agg=True)


def add_pkg(ws, args) -> None:
    log.info("Adding package to workspace")
    ws.add_dependency(args.repo)


def update_pkg(ws, args) -> None:
    ws.update_dependency(args.repo)


def dependency_from_tag(wsroot, tag):
    source, revision = tag

    if (wsroot/source).exists() and (wsroot/source).parent == wsroot:
        repo = GitRepo((wsroot/source).name, wsroot)
        source = repo.get_remote()
    elif (wsroot/source).exists():
        source = str((wsroot/source).resolve())
    elif Path(source).exists():
        source = str(Path(source).resolve())

    return Dependency(None, source, revision)


def add_dep(ws, args) -> None:
    """ Resolve a Dependency then add it to the cwd's wit-manifest.json """
    packages = {pkg.name: pkg for pkg in ws.lock.packages}
    req_dep = dependency_from_tag(ws.root, args.pkg)

    cwd = Path(os.getcwd()).resolve()
    cwd_dirname = cwd.relative_to(ws.root).parts[0]

    if not ws.lock.contains_package(cwd_dirname):
        raise NotAPackageError(
            "'{}' is not a package in workspace at '{}'".format(cwd_dirname, ws.path))

    # in order to resolve the revision, we need to bind
    # the req_dep to disk, cloning into .wit if neccesary
    req_dep.load(packages, ws.repo_paths, ws.root, True)
    try:
        req_dep.package.revision = req_dep.resolved_rev()
    except GitCommitNotFound:
        raise WitUserError("Could not find commit or reference '{}' in '{}'"
                           "".format(req_dep.specified_revision, req_dep.name))

    manifest_path = cwd/'wit-manifest.json'
    if manifest_path.exists():
        manifest = Manifest.read_manifest(manifest_path)
    else:
        manifest = Manifest([])

    # make sure the dependency is not already in the cwd's manifest
    if manifest.contains_dependency(req_dep.name):
        log.error("'{}' already depends on '{}'".format(cwd_dirname, req_dep.name))
        sys.exit(1)

    manifest.add_dependency(req_dep)
    manifest.write(manifest_path)

    log.info("'{}' now depends on '{}'".format(cwd_dirname, req_dep.package.tag()))


def update_dep(ws, args) -> None:
    packages = {pkg.name: pkg for pkg in ws.lock.packages}
    req_dep = dependency_from_tag(ws.root, args.pkg)

    cwd = Path(os.getcwd()).resolve()

    if cwd == ws.root:
        error("Cannot run update-dep from root of workspace.")

    cwd_dirname = cwd.relative_to(ws.root).parts[0]
    manifest = Manifest.read_manifest(cwd/'wit-manifest.json')

    # make sure the package is already in the cwd's manifest
    if not manifest.contains_dependency(req_dep.name):
        log.error("'{}' does not depend on '{}'".format(cwd_dirname, req_dep.name))
        sys.exit(1)

    req_dep.load(packages, ws.repo_paths, ws.root, True)
    req_pkg = req_dep.package
    try:
        req_pkg.revision = req_dep.resolved_rev()
    except GitCommitNotFound:
        raise WitUserError("Could not find commit or reference '{}' in '{}'"
                           "".format(req_dep.specified_revision, req_dep.name))

    # check if the requested repo is missing from disk
    if req_pkg.repo is None:
        msg = "'{}' not found in workspace. Have you run 'wit update'?".format(req_dep.name)
        raise PackageNotInWorkspaceError(msg)

    log.info("Updating to {}".format(req_dep.resolved_rev()))
    manifest.replace_dependency(req_dep)
    manifest.write(cwd/'wit-manifest.json')

    log.info("'{}' now depends on '{}'".format(cwd_dirname, req_pkg.tag()))


def status(ws, args) -> None:
    log.debug("Checking workspace status")
    if not ws.lock:
        log.info("{} is empty. Have you run `wit update`?".format(ws.LOCK))
        return

    clean = []
    dirty = []
    untracked = []
    missing = []
    seen_paths = {}
    for package in ws.lock.packages:
        package.load(ws.root, False)
        if package.repo is None:
            missing.append(package)
            continue
        seen_paths[package.repo.path] = True

        lock_commit = package.revision
        latest_commit = package.repo.get_head_commit()

        new_commits = lock_commit != latest_commit

        if new_commits or not package.repo.clean():
            status = []
            if new_commits:
                status.append("new commits")
            if package.repo.modified():
                status.append("modified content")
            if package.repo.untracked():
                status.append("untracked content")
            dirty.append((package, status))
        else:
            clean.append(package)

    for path in ws.root.iterdir():
        if path not in seen_paths and path.is_dir() and GitRepo.is_git_repo(path):
            untracked.append(path)
        seen_paths[path] = True

    log.info("Clean packages:")
    for package in clean:
        log.info("    {}".format(package.name))
    log.info("Dirty packages:")
    for package, content in dirty:
        msg = ", ".join(content)
        log.info("    {} ({})".format(package.name, msg))
    if len(untracked) > 0:
        log.info("Untracked packages:")
        for path in untracked:
            relpath = path.relative_to(ws.root)
            log.info("    {}".format(relpath))
    if len(missing) > 0:
        log.info("Missing packages:")
        for package in missing:
            log.info("    {}".format(package.name))

    packages, errors = ws.resolve()
    for name in packages:
        package = packages[name]
        s = package.status(ws.lock)
        if s:
            print(package.name, s)

    print_errors(errors)


def update(ws, args) -> None:
    packages, errors = ws.resolve(download=True)
    if len(errors) == 0:
        ws.checkout(packages)
    else:
        print_errors(errors)
        sys.exit(1)


def fetch_scala(ws, args, agg=True) -> None:
    """Fetches bloop, coursier, and ivy dependencies

    It only fetches if ivydependencies.json files are found in packages
    ws -- the Workspace
    args -- arguments to the parser
    agg -- indicates if this invocation is part of a larger command (like init)
    """

    # Collect ivydependency files
    files = []
    for package in ws.lock.packages:
        package.load(ws.root, False)
        ivyfile = scalaplugin.ivy_deps_file(package.repo.path)
        if os.path.isfile(ivyfile):
            files.append(ivyfile)
        else:
            log.debug("No ivydependencies.json file found in package {}".format(package.name))

    if len(files) == 0:
        msg = "No ivydependencies.json files found, skipping fetching Scala..."
        if agg:
            log.debug(msg)
        else:
            # We want to print something if you run `wit fetch-scala` directly and nothing happens
            log.info(msg)
    else:
        log.info("Fetching Scala install and dependencies...")

        install_dir = scalaplugin.scala_install_dir(ws.root)

        ivy_cache_dir = scalaplugin.ivy_cache_dir(ws.root)
        os.makedirs(ivy_cache_dir, exist_ok=True)

        # Check if we need to install Bloop
        if os.path.isdir(install_dir):
            log.info("Scala install directory {} exists, skipping installation..."
                     .format(install_dir))
        else:
            log.info("Installing Scala to {}...".format(install_dir))
            os.makedirs(install_dir, exist_ok=True)
            scalaplugin.install_coursier(install_dir)

        log.info("Fetching ivy dependencies...")
        scalaplugin.fetch_ivy_dependencies(files, install_dir, ivy_cache_dir)


def version() -> None:
    path = Path(__file__).resolve().parent.parent.parent
    log.trace("Wit root is {}".format(path))
    version_file = path.joinpath('__version__')

    try:
        with version_file.open() as fh:
            version = fh.readline().rstrip()
            log.spam("Version as read from [{}]: [{}]".format(version_file, version))

    except FileNotFoundError:
        # not an official release, use git to get an explicit version
        log.spam("Running [git -C {} describe --tags --dirty]".format(str(path)))
        proc = subprocess.run(['git', '-C', str(path), 'describe', '--tags', '--dirty'],
                              stdout=subprocess.PIPE)
        version = proc.stdout.decode('utf-8').rstrip()
        log.spam("Output: [{}]".format(version))
        version = re.sub(r"^v", "", version)

    print("wit {}".format(version))
