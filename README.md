# Wit
Workspace Integration Tool

## What is this?
Wit is a tool for managing workspaces. It is intended as a supplement to (not a replacement for) Git-based workflows.
The goal of wit is to enable development in a multiple user and repository environment.

A wit workspace is composed of one or more packages. A package is a git repository.
Each package may optionally contain a wit-manifest.json file which defines other packages upon which it depends.
Wit resolves this hierarchy of dependencies and generates a flattened directory structure in which each package
may exist only once.

## Getting started

The best way to learn wit is to check out the [tutorial](share/doc/wit/tutorial.md).

### Installation

Wake is intended to be as lightweight as possible. It simply requires `git` and `Python` version 3.5 or greater.

You can simply clone the repo and add it to your `PATH`, for example:
```bash
git clone https://github.com/sifive/wit.git
PATH=$PATH:$PWD/wit
which wit
```

It also includes a `Makefile` for installing specific versions. The installation flow requires `make`, `rsync`, and `sed`.

```bash
make install PREFIX=/path/to/installation
```

The Makefile will create a directory with the version (it even works for commits between tags)
and copy the contents of contents of the local clone excluding the tests and metadata.


### Creating a workspace
Creating a workspace does not require a git repository to be specified. You may create an empty workspace with:

    wit init <workspace>
 
If you want to specify one or more packages when you generate the workspace you can use the `-a` option

    wit init <workspace> -a </path/to/git/repo/soc.git>[::revision]

The revision can be a tag, branch, or commit. Note that wit respects normal git behavior.

### Adding a package to a workspace

To add a package to a workspace that has already been created you use the `add-pkg` sub-command.

    wit add-pkg </path/to/git/repo/soc.git>[::revision]
 
### Resolve and fetch package dependencies

Once you have added one or more repositories to your workspace, you can use `update` to resolve and fetch
the transitive dependencies of each package.

    wit update
    
### Updating a package

You can update the revision of a package in the workspace using the `update-pkg` sub-command.

    wit update-pkg <package>[::revision]

If you update to `<package>::<branch>`, it will checkout the local version of that branch.
You can always checkout remote branches by specifying the remote as well

    wit update-pkg <package>::<remote>/<branch>
 
## Contributing

Please see [README-internals](README-internals.md) for information about development.
 
## License
 
See [LICENSE](./LICENSE).
