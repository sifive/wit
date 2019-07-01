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
from .gitrepo import get_package_from_cwd
from .workspace import WorkSpace, PackageNotInWorkspaceError
from .dependency import parse_dependency_tag, Dependency
from .inspect import inspect_tree
from . import scalaplugin
from pathlib import Path
from typing import cast, List, Tuple  # noqa: F401
from .common import WitUserError, error
from .gitrepo import GitRepo
import re

log = getLogger()


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

        try:
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
        packages = []  # type: List[Tuple[str, str]]
    else:
        packages = args.add_pkg

    ws = WorkSpace.create(args.workspace_name, parse_repo_path(args))
    for package in packages:
        ws.add_package(package)

    if args.update:
        update(ws, args)

        if args.fetch_scala:
            fetch_scala(ws, args, agg=True)


def add_pkg(ws, args) -> None:
    log.info("Adding package to workspace")
    ws.add_package(args.repo)


def update_pkg(ws, args) -> None:
    ws.update_package(args.repo)


def dependency_from_tag(tag):
    source, revision = tag
    return Dependency(None, source, revision)


def add_dep(ws, args) -> None:
    cwd_pkg = get_package_from_cwd(ws)
    cwd_pkg.load(ws.root, ws.repo_paths, force_root=True)

    new_dep = dependency_from_tag(args.pkg)
    new_dep.load_package(ws.root, ws.repo_paths, {}, force_root=True)
    # Check package exists in workspace
    found = ws.get_dependency(new_dep.name)
    if found is None:
        new_dep.source = new_dep.package.repo.get_remote()
    else:
        new_dep.source = found.source

    cwd_pkg.repo.add_dependency(new_dep)


def update_dep(ws, args) -> None:
    dep = dependency_from_tag(args.pkg)
    found = (ws.root/dep.name).exists()
    if not found:
        msg = "'{}' not found in workspace. Have you run 'wit update'?".format(dep.name)
        raise PackageNotInWorkspaceError(msg)
    # Be sure to propagate the specified revision!
    dep.load_package(ws.root, ws.repo_paths, {}, True)
    log.info(dep)

    parent_pkg = get_package_from_cwd(ws)
    parent_pkg.load(ws.root, ws.repo_paths, force_root=True)
    parent_pkg.repo.update_dependency(dep)


def status(ws, args) -> None:
    log.debug("Checking workspace status")
    if not ws.lock:
        log.info("{} is empty. Have you run `wit update`?".format(ws.LOCK))
        return

    clean = []
    dirty = []
    untracked = []
    seen_paths = {}
    for package in ws.lock.packages:
        seen_paths[package.repo.get_path()] = True

        lock_commit = package.theory_revision
        latest_commit = package.repo.get_latest_commit()

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

    packages = ws.resolve()
    for name in packages:
        package = packages[name]
        s = package.status(ws.lock)
        if s:
            print(package.name, s)


def update(ws, args) -> None:
    packages = ws.resolve(force_root=True)
    ws.checkout(packages)


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
        ivyfile = scalaplugin.ivy_deps_file(package.repo.get_path())
        if os.path.isfile(ivyfile):
            files.append(ivyfile)
        else:
            log.debug("No ivydependencies.json file found in package {}".format(package.name))

    if len(files) == 0:
        msg = "No ivydependency.json files found, skipping fetching Scala..."
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
    path = Path(__file__).resolve().parent.parent
    log.trace("Script path is {}".format(path))
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