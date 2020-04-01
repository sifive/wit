import argparse
import os
from .dependency import parse_dependency_tag


def chdir(s) -> None:
    def err(msg):
        raise argparse.ArgumentTypeError(msg)
    try:
        os.chdir(s)
    except FileNotFoundError:
        err("'{}' path not found!".format(s))
    except NotADirectoryError:
        err("'{}' is not a directory!".format(s))


# ********** top-level parser **********
parser = argparse.ArgumentParser(
    prog='wit',
    formatter_class=argparse.RawTextHelpFormatter)
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

# ********** command subparser aggregator **********
subparsers = parser.add_subparsers(
               title='subcommands',
               dest='command',
               metavar='<command>',
               help='<description>')

# ********** init subparser **********
init_parser = subparsers.add_parser('init', help='create workspace')
init_parser.add_argument('--no-update', dest='update', action='store_false',
                         help='don\'t run update upon creating the workspace')
init_parser.add_argument('-a', '--add-pkg', metavar='repo[::revision]', action='append',
                         type=parse_dependency_tag, help='add an initial package')
init_parser.add_argument('workspace_name')

# ********** add-pkg subparser **********
add_pkg_parser = subparsers.add_parser('add-pkg', help='add a package to the workspace')
add_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=parse_dependency_tag)

# ********** update-pkg subparser **********
update_pkg_parser = subparsers.add_parser('update-pkg', help='update the revision of a '
                                          'previously added package')
update_pkg_parser.add_argument('repo', metavar='repo[::revision]', type=parse_dependency_tag)

# ********** add-dep subparser **********
add_dep_parser = subparsers.add_parser(
    name='add-dep',
    description='Adds <pkg> as a dependency to a target package determined by the current working '
                'directory (which can be set by -C)',
    help='add a dependency to a package')
add_dep_parser.add_argument(
    dest='pkg',
    metavar='pkg[::revision]',
    type=parse_dependency_tag,
    help='revision can be any git commit-ish, default is the currently checked out commit')
add_dep_parser.add_argument(
    '-m',
    '--message',
    dest="message",
    help="Comment message to be added to the dependency's entry in the manifest.")

# ********** update-dep subparser **********
update_dep_parser = subparsers.add_parser('update-dep', help='update revision of a dependency '
                                          'in a package')
update_dep_parser.add_argument('pkg', metavar='pkg[::revision]', type=parse_dependency_tag)
update_dep_parser.add_argument(
    '-m',
    '--message',
    dest="message",
    help='Comment message to be added to the dependency\'s entry in the manifest. This will'
         ' overwrite a previous message.')

# ********** status subparser **********
subparsers.add_parser('status', help='show status of workspace')

# ********** update subparser **********
subparsers.add_parser('update', help='update git repos')

# ********** inspect subparser **********
inspect_parser = subparsers.add_parser('inspect', help='inspect lockfile')
inspect_group = inspect_parser.add_mutually_exclusive_group()
inspect_group.add_argument('--tree', action="store_true")
inspect_group.add_argument('--dot', action="store_true")

# ********** foreach subparser **********
foreach_parser = subparsers.add_parser(
    'foreach',
    help='perform a command in each repository directory',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description="""
Perform a command in each repository directory.
The repository list is created by reading records contained in 'wit-lock.json'.

Any options, such as --continue-on-fail must be specified before the command.

Wit sets the following environment variables for each invocation of the command:
    WIT_REPO_NAME    repository name
    WIT_REPO_PATH    path to repository
    WIT_LOCK_SOURCE  initial source location of repository
    WIT_LOCK_COMMIT  commit recorded in lockfile, actual repository contents could be different
    WIT_WORKSPACE    path to root of wit workspace""")

foreach_parser.add_argument('--continue-on-fail', action='store_true',
                            help='run the command in each repository regardless of failures')

# 'cmd' and 'args' eventually become one list, but this forces at least one input string
foreach_parser.add_argument('cmd', help='command to run in each repository')
foreach_parser.add_argument('args', nargs=argparse.REMAINDER, help='arguments for the command')
