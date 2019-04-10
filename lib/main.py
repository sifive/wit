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
import os
from lib.workspace import WorkSpace
from lib.package import Package
import logging
from lib import scalaplugin
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
                             type=Package.from_arg, help='add an initial package')
    init_parser.add_argument('workspace_name')

    add_parser = subparsers.add_parser('add-pkg', help='add a package to the workspace')
    add_parser.add_argument('repo', metavar='repo[::revision]', type=Package.from_arg)

    subparsers.add_parser('status', help='show status of workspace')
    subparsers.add_parser('update', help='update git repos')

    subparsers.add_parser('fetch-scala', help='Fetch dependencies for Scala projects')

    args = parser.parse_args()

    if args.prepend_repo_path and args.repo_path:
        args.repo_path = " ".join([args.prepend_repo_path, args.repo_path])
    elif args.prepend_repo_path:
        args.repo_path = args.prepend_repo_path

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
            ws.set_repo_path(args.repo_path)

        except FileNotFoundError as e:
            log.error("Unable to find workspace root [{}]. Cannot continue.".format(e))
            sys.exit(1)

        if args.command == 'add-pkg':
            add(ws, args)

        elif args.command == 'status':
            status(ws, args)

        elif args.command == 'update':
            update(ws, args)

        elif args.command == 'fetch-scala':
            fetch_scala(ws, args, agg=False)


def create(args):
    if args.add_pkg is None:
        packages = []
    else:
        packages = args.add_pkg
    ws = WorkSpace.create(args.workspace_name, packages)
    ws.set_repo_path(args.repo_path)
    for package in packages:
        ws.add_package(package)

    if args.update:
        update(ws, args)

        if args.fetch_scala:
            fetch_scala(ws, args, agg=True)


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
    ws.update()


def fetch_scala(ws, args, agg=True):
    """Fetches bloop, coursier, and ivy dependencies

    It only fetches if ivydependencies.json files are found in packages
    ws -- the Workspace
    args -- arguments to the parser
    agg -- indicates if this invocation is part of a larger command (like init)
    """

    # Collect ivydependency files
    files = []
    for package in ws.lock.packages:
        ivyfile = scalaplugin.ivy_deps_file(package)
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

        install_dir = scalaplugin.scala_install_dir(ws)

        ivy_cache_dir = scalaplugin.ivy_cache_dir(ws)
        os.makedirs(ivy_cache_dir, exist_ok=True)

        # Check if we need to install Bloop
        if os.path.isdir(install_dir):
            log.info("Scala install directory {} exists, skipping installation..."
                     .format(install_dir))
        else:
            log.info("Installing Scala to {}...".format(install_dir))
            os.makedirs(install_dir, exist_ok=True)
            scalaplugin.install_bloop(install_dir, ivy_cache_dir)

        log.info("Fetching ivy dependencies...")
        scalaplugin.fetch_ivy_dependencies(files, install_dir, ivy_cache_dir)
