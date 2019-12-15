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


# Parse arguments. Create sub-commands for each of the modes of operation
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

subparsers = parser.add_subparsers(
               title='subcommands',
               dest='command',
               metavar='<command>',
               help='<description>')

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

fetch_scala_parser = subparsers.add_parser('fetch-scala',
                                           help='Fetch dependencies for Scala projects')
fetch_scala_parser.add_argument('--jar', action='store_true', default=False,
                                help='download coursier jar instead of binary')
