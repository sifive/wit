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
from lib.formatter import WitFormatter
from pathlib import Path

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(WitFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
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

    add_parser = subparsers.add_parser('add-pkg', help='add a package to the workspace')
    add_parser.add_argument('repo', metavar='repo[::revision]', type=Package.from_arg)

    subparsers.add_parser('status', help='show status of workspace')
    subparsers.add_parser('update', help='update git repos')

    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.INFO)
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
            add(ws, args)

        elif args.command == 'status':
            status(ws, args)

        elif args.command == 'update':
            update(ws, args)


def create(args):
    if args.add_pkg is None:
        packages = []
    else:
        packages = args.add_pkg
    WorkSpace.create(args.workspace_name, packages)


def add(ws, args):
    log.info("Adding repo to workspace")
    ws.add_package(args.repo)


def status(ws, args):
    log.debug("Checking workspace status")
    if not ws.lock:
        log.info("{} is empty. Have you run `wit update`?".format(ws.LOCK))
        return

    clean = []
    dirty = []
    for package in ws.lock.packages:
        # FIXME: cheating by diving into the object.
        lock_commit = package.revision
        latest_commit = package.get_latest_commit()

        new_commits = lock_commit != latest_commit

        if new_commits or not package.clean():
            status = []
            if new_commits:
                status.append("new commits")
            if package.modified():
                status.append("modified content")
            if package.untracked():
                status.append("untracked content")
            dirty.append((package, status))
        else:
            clean.append(package)

    log.info("Clean packages:")
    for package in clean:
        log.info("    {}".format(package.name))
    log.info("Dirty repos:")
    for package, content in dirty:
        msg = ", ".join(content)
        log.info("    {} ({})".format(package.name, msg))


def update(ws, args):
    log.info("Updating workspace")
    ws.update()
