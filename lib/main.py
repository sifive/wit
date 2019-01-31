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

import sys
import argparse
from lib.workspace import WorkSpace
from lib.package import Package
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('wit')


def main() -> None:
    # Parse arguments. Create sub-commands for each of the modes of operation
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('--repomap', default=None)
    subparsers = parser.add_subparsers(dest='command', help='sub-command help')

    init_parser = subparsers.add_parser('init', help='create workspace')
    init_parser.add_argument('-a', '--add-pkg', metavar='repo[::revision]', action='append',
                             type=Package.from_arg, help='add an initial package')
    init_parser.add_argument('workspace_name')

    add_pkg_parser = subparsers.add_parser('add-pkg', help='add a package to the workspace')
    add_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=Package.from_arg)

    update_pkg_parser = subparsers.add_parser('update-pkg', help='update the revision of a previously added package')
    update_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=Package.from_arg)

    add_dep_parser = subparsers.add_parser('add-dep', help='add a dependency to a package')
    add_dep_parser.add_argument('pkg', metavar='pkg[::revision]', type=Package.from_arg)

    subparsers.add_parser('status', help='show status of workspace')
    subparsers.add_parser('update', help='update git repos')

    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.WARNING)

    elif args.debug:
        log.setLevel(logging.DEBUG)

    else:
        log.setLevel(logging.INFO)

    # FIXME: This big switch statement... no good.
    if args.command == 'init':
        create(args)

    else:
        # These commands assume the workspace already exists. Error out if the
        # workspace cannot be found.
        try:
            ws = WorkSpace.find(Path.cwd())

        except FileNotFoundError as e:
            log.error("Unable to find workspace root [{}]. Cannot continue.".format(e))
            sys.exit(1)

        if args.command == 'add-pkg':
            add_pkg(ws, args)

        if args.command == 'update-pkg':
            update_pkg(ws, args)

        if args.command == 'add-dep':
            add_dep(ws, args)

        elif args.command == 'status':
            status(ws, args)

        elif args.command == 'update':
            update(ws, args)


def create(args):
    log.info("Creating workspace [{}]".format(args.workspace_name))

    if args.add_pkg is None:
        packages = []
    else:
        packages = args.add_pkg
    WorkSpace.create(args.workspace_name, packages)


def add_pkg(ws, args):
    log.info("Adding package to workspace")
    ws.add_package(args.repo)


def update_pkg(ws, args):
    log.info("Updating package in workspace")
    ws.update_package(args.repo)


def add_dep(ws, args):
    log.info("Adding dependency to package")
    pkg = Package.from_cwd()
    if not pkg:
        raise FileNotFoundError("Could not find package root from cwd.")

    pkg.add_dependency(args.pkg)


def status(ws, args):
    log.info("Checking workspace status")
    if not ws.lock:
        log.info("{} is empty. Have you run `wit update`?".format(ws.LOCK))
        return

    clean = []
    dirty = []
    for package in ws.lock.packages:
        # FIXME: cheating by diving into the object.
        lock_commit = package.commit
        repo = ws.get_repo(package)
        latest_commit = repo.get_latest_commit()

        new_commits = lock_commit != latest_commit

        if new_commits or not repo.clean():
            status = []
            if new_commits:
                status.append("new commits")
            if repo.modified():
                status.append("modified content")
            if repo.untracked():
                status.append("untracked content")
            dirty.append((package, status))
        else:
            clean.append(package)

    print("Clean packages:")
    for package in clean:
        print("    {}".format(package.name))
    print("Dirty repos:")
    for package, content in dirty:
        msg = ", ".join(content)
        print("    {} ({})".format(package.name, msg))


def update(ws, args):
    log.info("Updating workspace")
    ws.update()
