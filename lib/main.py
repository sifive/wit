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
from lib.formatter import WitFormatter
from pathlib import Path
from typing import List  # noqa: F401

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(WitFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger('wit')

def build_base_parser(parser):
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-C', dest='cwd', type=chdir, metavar='path', help='Run in given path')
    parser.add_argument('--repo-path', default=os.environ.get('WIT_REPO_PATH'),
                        help='Specify alternative paths to look for packages')
    parser.add_argument('--prepend-repo-path', default=None,
                        help='Prepend paths to the default repo search path.')


def add_sub_parsers(parser):
    subparsers = parser.add_subparsers(dest='command', help='sub-command help')

    init_parser = subparsers.add_parser('init', help='create workspace')
    init_parser.add_argument('--no-update', dest='update', action='store_false',
                             help='don\'t run update upon creating the workspace')
    init_parser.add_argument('-a', '--add-pkg', metavar='repo[::revision]', action='append',
                             type=Package.from_arg, help='add an initial package')
    init_parser.add_argument('workspace_name')

    add_pkg_parser = subparsers.add_parser('add-pkg', help='add a package to the workspace')
    add_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=Package.from_arg)

    update_pkg_parser = subparsers.add_parser('update-pkg', help='update the revision of a '
                                              'previously added package')
    update_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=Package.from_arg)

    add_dep_parser = subparsers.add_parser('add-dep', help='add a dependency to a package')
    add_dep_parser.add_argument('pkg', metavar='pkg[::revision]', type=Package.from_arg)

    subparsers.add_parser('status', help='show status of workspace')
    subparsers.add_parser('update', help='update git repos')

    return subparsers


def main() -> None:

    parser = argparse.ArgumentParser(add_help=False)
    # parse_known_args does not support sub-commands so we split parsing into
    # mutliple phases
    build_base_parser(parser)

    args, unknown = parser.parse_known_args()

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

    # Now let's add the subparsers
    parser = argparse.ArgumentParser()
    build_base_parser(parser)
    subparsers = add_sub_parsers(parser)

    # If the sub-command is init, then it's not a plugin command
    if 'init' in unknown:
        args = parser.parse_args()

        assert args.command == 'init'
        create(args)
    # FIXME: This big switch statement... no good.
    else:
        # These commands assume the workspace already exists. Error out if the
        # workspace cannot be found.
        try:
            ws = WorkSpace.find(Path.cwd())
            ws.set_repo_path(args.repo_path)

        except FileNotFoundError as e:
            log.error("Unable to find workspace root [{}]. Cannot continue.".format(e))
            sys.exit(1)

        ws.load_plugins()

        # Load plugins into parser
        plugin_cmds = {}
        for plugin in ws.plugins:
            cmd = plugin.add_subparser(subparsers)
            if cmd is not None:
                plugin_cmds[cmd] = plugin

        args = parser.parse_args()

        # Built-in commands
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

        # Plugin commands
        elif args.command in plugin_cmds:
            plugin = plugin_cmds[args.command]
            plugin.post_parse(ws, args)


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
        packages = []  # type: List[Package]
    else:
        packages = args.add_pkg

    ws = WorkSpace.create(args.workspace_name, packages)
    ws.set_repo_path(args.repo_path)

    for package in packages:
        ws.add_package(package)

    if args.update:
        update(ws, args)

def add_pkg(ws, args) -> None:
    log.info("Adding package to workspace")
    ws.add_package(args.repo)


def update_pkg(ws, args) -> None:
    log.info("Updating package in workspace")
    ws.update_package(args.repo)


def add_dep(ws, args) -> None:
    log.info("Adding dependency to package")
    pkg = Package.from_cwd()
    if not pkg:
        raise FileNotFoundError("Could not find package root from cwd.")

    pkg.add_dependency(args.pkg)


def status(ws, args) -> None:
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


def update(ws, args) -> None:
    ws.update()

    # Reload plugins after an update
    ws.load_plugins()

    for plugin in ws.plugins:
        plugin.post_update(ws, args)


