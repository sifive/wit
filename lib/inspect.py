from lib.witlogger import getLogger

log = getLogger()


def inspect_tree(ws, args):
    packages = ws.resolve()

    if args.tree:
        tree = {}
        for dep in ws.manifest.packages:
            tree[dep.get_id()] = dep.crawl_dep_tree(packages)
        for key in tree:
            top_dep = tree[key]
            _print_generic_tree(top_dep)

    if args.dot:
        _print_dot_tree(ws, packages)


def _print_dot_tree(ws, packages_dict):
    packages = list(packages_dict.values())

    log.output('digraph dependencies {')
    log.output('root [label="[root]"]')

    pkg_ids = []
    for pkg in packages:
        pkg_id = pkg.get_id()
        pkg_ids.append(pkg_id)
        log.output('{} [label="{}"]'.format(pkg_id, pkg.tag()))

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
        if dep_id not in pkg_ids:
            dep.load_package(packages_dict, False)
            dep_pkg_id = dep.package.get_id()
            log.output('{} [label="{}"]'.format(dep_id, dep.tag()))
            draw_connection(dep_id, dep_pkg_id, dotted=True)
        draw_connection(pkg_id, dep_id)

    for dep in ws.manifest.packages:
        print_dep(ws, dep)

    for pkg in packages:
        for dep in pkg.get_dependencies():
            print_dep(pkg, dep)

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
