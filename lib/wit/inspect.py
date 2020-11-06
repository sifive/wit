import sys
from .common import print_errors
from .witlogger import getLogger
from .workspace import WorkSpace

log = getLogger()


def inspect_tree(ws, args):
    packages, errors = ws.resolve()

    if args.tree:
        tree = {}
        for dep in ws.manifest.dependencies:
            tree[dep.get_id()] = dep.crawl_dep_tree(ws.root, ws.repo_paths, packages)
        for key in tree:
            top_dep = tree[key]
            x, _ = _deduplicate_tree(top_dep)
            _print_generic_tree(x)

    if args.dot:
        if args.simple:
            _print_simple_dot_tree(ws, packages)
        else:
            _print_dot_tree(ws, packages)

    print_errors(errors)


BOXED_DEPS = False
VERBOSE_GRAPH = False


def _deduplicate_tree(tree, seen=None):
    tree = tree.copy()
    seen = seen or []
    tag = tree.pop('')
    ident = tag[-8:]
    out = {'': tag}

    if ident in seen:
        return out, seen
    else:
        seen.append(ident)
        for key in tree:
            out[key], seen = _deduplicate_tree(tree[key], seen)
        return out, seen


def _print_dot_tree(ws, packages_dict):
    packages = list(packages_dict.values())

    log.output('digraph dependencies {')
    log.output('root [label="[root]"]')

    pkg_ids = []
    for pkg in packages:
        pkg_id = pkg.get_id()
        pkg_ids.append(pkg_id)
        log.output('{} [label="{}"]'.format(pkg_id, pkg.id()))

    drawn_connections = []

    def draw_connection(from_id, to_id, dotted=False):
        if from_id == to_id:
            return
        pair = (from_id, to_id)
        if pair not in drawn_connections:
            log.output("{} -> {}{}".format(from_id, to_id, " [style=dotted]" if dotted else ""))
            drawn_connections.append(pair)

    def print_dep(pkg, dep):
        pkg_id = pkg.get_id()
        dep_id = dep.get_id()
        dep.load(packages_dict, ws.repo_paths, ws.root, False)
        if dep.package.repo is None:
            log.error("Cannot generate graph with missing repo '{}'".format(dep.name))
            sys.exit(1)
        dep_pkg_id = dep.package.get_id()
        if dep.id() != dep.package.id() or VERBOSE_GRAPH:
            draw_connection(dep_id, dep_pkg_id, dotted=True)
            log.output('{} [label="{}"]{}'.format(dep_id, dep.id(),
                                                  " [shape=box]" if BOXED_DEPS else ""))
            draw_connection(pkg_id, dep_id)
        else:
            draw_connection(pkg_id, dep_pkg_id)

    for dep in ws.manifest.dependencies:
        print_dep(ws, dep)

    for pkg in packages:
        for dep in pkg.get_dependencies():
            print_dep(pkg, dep)

    log.output('}')


def _print_simple_dot_tree(ws, packages_dict):
    # This algorithm is based on the normal one except we identify nodes based
    # on just the package name and not the revision.
    packages = list(packages_dict.values())

    def sanitize(s):
        return s.replace(r"-", "_")

    nodes = set()
    for pkg in packages:
        nodes.add(sanitize(pkg.name))

    drawn_connections = set()

    def draw_connection(from_id, to_id):
        if from_id == to_id:
            return
        pair = (from_id, to_id)
        if pair not in drawn_connections:
            drawn_connections.add(pair)

    def print_dep(pkg, dep):
        if isinstance(pkg, WorkSpace):
            pkg_name = "root"
        else:
            pkg_name = sanitize(pkg.name)
        dep_name = sanitize(dep.name)
        dep.load(packages_dict, ws.repo_paths, ws.root, False)
        if dep.package.repo is None:
            log.error("Cannot generate graph with missing repo '{}'".format(dep.name))
            sys.exit(1)
        draw_connection(pkg_name, dep_name)

    for dep in ws.manifest.dependencies:
        print_dep(ws, dep)

    for pkg in packages:
        for dep in pkg.get_dependencies():
            print_dep(pkg, dep)

    log.output('digraph dependencies {')
    log.output('root [label="[root]"]')

    for node in sorted(nodes):
        log.output('{} [label="{}"]'.format(node, node))

    for from_id, to_id in sorted(drawn_connections):
        log.output("{} -> {}".format(from_id, to_id))

    log.output('}')


def _print_generic_tree(data):
    tag = data.pop('')
    print(tag)
    return _recur_print_generic_tree(0, data, [])


def _recur_print_generic_tree(depth, data, done_cols):

    def print_indent(depth):
        for i in range(0, depth):
            if i in done_cols:
                print("   ", end="")
            else:
                print("│  ", end="")

    done_cols_copy = done_cols[:]

    keys = list(data.keys())
    for i, key in enumerate(keys):
        subdata = data[key]
        subtag = subdata.pop('')
        print_indent(depth)
        if i == len(keys)-1:
            print("└─", end="")
            done_cols_copy.append(depth)
        else:
            print("├─", end="")
        print(subtag)
        _recur_print_generic_tree(depth+1, subdata, done_cols_copy)
