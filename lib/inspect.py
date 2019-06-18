import os
import sys
import re
from lib.manifest import Manifest
from lib.witlogger import getLogger

log = getLogger()


# FIXME use custom logger to write to files
def inspect_tree(ws, args):
    out = sys.stdout
    if args.out_file:
        out = args.out_file
        log.info("[printing to {}]".format(args.out_file.name))

    if not ws.lock:
        log.error('Cannot inspect non-existent wit-lock.json')
        sys.exit(1)
    tree = {}
    root_packages = ws.manifest.packages
    for package in root_packages:
        ident = _get_package_ident(package)
        tree[ident] = _get_package_tree(package)

    processed_lockfile_packages = {pkg.name: pkg.revision for pkg in ws.lock.packages}
    new_tree = _clean_tree(tree, processed_lockfile_packages)

    if args.dot:
        _print_dot_tree(out, new_tree)
    else:
        _print_pkg_tree(out, new_tree)


def _get_package_tree(root_pkg):
    manifest_path = root_pkg.get_path()/'wit-manifest.json'
    if not os.path.isfile(str(manifest_path)):
        return {}
    data = {}
    manifest = Manifest.read_manifest(root_pkg.wsroot, manifest_path)
    for package in manifest.packages:
        ident = _get_package_ident(package)
        data[ident] = _get_package_tree(package)
    return data


def _get_package_ident(package):
    return "{}@{}".format(package.name, package.revision)


def _clean_tree(tree, lockfile_package_dict):
    if not tree:
        return {}
    cleaned_tree = {}
    for key in tree:
        pkg_name = key.split("@")[0]
        if pkg_name in lockfile_package_dict:
            old_revision = key.split("@")[1]
            new_revision = lockfile_package_dict[pkg_name]
            if new_revision != old_revision:
                new_key = "{}->{}".format(key, new_revision)
                cleaned_tree[new_key] = {}
                continue
        cleaned_tree[key] = _clean_tree(tree[key], lockfile_package_dict)
    return cleaned_tree


def _print_pkg_tree(out, data):
    return _recur_print_pkg_tree(out, 0, data, list(data.keys()), 0, [], [])


def _recur_print_pkg_tree(out, depth, data, keys, idx, done_cols, already_explored):
    key = keys[idx]
    already_explored_copy = already_explored[:]
    this_already_explored = key in already_explored
    if not this_already_explored:
        already_explored_copy.append(keys[idx])

    done_cols_copy = done_cols[:]
    end = idx == len(keys)-1
    if depth > 0:
        for i in range(1, depth):
            if i in done_cols:
                print("   ", end="", file=out)
            else:
                print("│  ", end="", file=out)
        if end:
            print("└─ ", end="", file=out)
            done_cols_copy.append(depth)
        else:
            print("├─ ", end="", file=out)

    print(_format_pkg_key(key), end="", file=out)
    if this_already_explored:
        print(" (see above)", file=out)
    elif "->" in key:
        superceded_key = key.split("@")[0]+"::"+key.split("->")[1]
        if superceded_key in already_explored:
            print(" (see above)", file=out)
        else:
            print(" (see below)", file=out)
    else:
        print()

    if data[key] and not this_already_explored:
        already_explored_copy = _recur_print_pkg_tree(out, depth+1, data[key],
                                                      list(data[key].keys()),
                                                      0, done_cols_copy, already_explored_copy)
    if not end:
        already_explored_copy = _recur_print_pkg_tree(out, depth, data, keys, idx+1,
                                                      done_cols_copy, already_explored_copy)

    return already_explored_copy


def _format_pkg_key(s):
    name = s.split("@")[0]
    rev = s.split("@")[1]
    out = "{}::".format(name)
    if "->" in s:
        parts = rev.split("->")
        rev_old = parts[0][:8]
        rev_new = parts[1][:8]
        out += "{}->{}".format(rev_old, rev_new)
    else:
        out += "{}".format(rev[:8])
    return out


def _print_dot_tree(out, tree):
    print('digraph dependencies {', file=out)
    print('root [label="[root]"]', file=out)
    _print_dot_tree_body(out, tree, "root", [], [])
    print('}', file=out)


def _print_dot_tree_body(out, tree, parent_key, keys_defined, keys_seen):
    if parent_key in keys_seen:
        return keys_defined, keys_seen
    keys_seen_copy = keys_seen[:]
    keys_seen_copy.append(parent_key)

    parent_dot_key = _transform_to_dot_key(parent_key)

    if "->" in parent_key:
        superceded = parent_key.split("@")[0]+"@"+parent_key.split("->")[1]
        superceded_dot_key = _transform_to_dot_key(superceded)
        print("{} -> {} [style=dotted]".format(parent_dot_key, superceded_dot_key), file=out)
        return keys_defined, keys_seen_copy

    if not tree:
        return keys_defined, keys_seen_copy

    keys_defined_copy = keys_defined[:]
    for key in tree:
        child_dot_key = _transform_to_dot_key(key)
        if key not in keys_defined_copy:
            fancy_key = _format_pkg_key(key)
            fancy_key = fancy_key.split("->")[0]
            print('{} [label="{}"]'.format(child_dot_key, fancy_key), file=out)
            keys_defined_copy.append(key)
        print("{} -> {}".format(parent_dot_key, child_dot_key), file=out)
        keys_defined_copy, keys_seen_copy = _print_dot_tree_body(out, tree[key], key,
                                                                 keys_defined_copy, keys_seen_copy)
    return keys_defined_copy, keys_seen_copy


def _transform_to_dot_key(ident):
    if ident == "root":
        return "root"
    return re.sub(r"([^\w\d])", "_", ident)
