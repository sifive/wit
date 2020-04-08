[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/sifive/wit.svg?label=release)](https://github.com/sifive/wit/releases/latest)
[![Build Status](https://travis-ci.com/sifive/wit.svg?branch=master)](https://travis-ci.com/sifive/wit)
[![Github](https://img.shields.io/github/license/sifive/wit.svg?color=blue&style=flat-square)](LICENSE)

# Wit
Workspace Integration Tool

## What is this?
Wit is a tool for managing workspaces. It is intended as a supplement to (not a replacement for) Git-based workflows.
The goal of wit is to enable development in a multiple user and repository environment.

A wit workspace is composed of one or more packages. A package is a git repository.
Each package may optionally contain a wit-manifest.json file which defines other packages upon which it depends.
Wit resolves this hierarchy of dependencies and generates a flattened directory structure in which each package
may exist only once.

## How does Wit deduplicate packages?
When multiple versions of the same package are requested, Wit chooses the latest requested version, making sure the selected version's commit is a descendant of every other requested versions' commits.

## Getting started

The best way to learn wit is to check out the [tutorial](doc/tutorial.md).

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

### How To Guides

See the [How To Guides](doc/how-to-guides.adoc) for list of guides for common wit operations.


## Autocompletion

Tab completion can be enabled via `source complete.bash`. If you want it to persist, see below.

### Bash

#### Linux
```bash
cp complete.bash /etc/bash_completion.d/wit
```

#### macOS
##### Homebrew
Install autocompletion for bash:
```bash
brew install bash-completion
```

After running the script, you should see instructions for how to finish installing it.

For example, on macOS 10.14.15, the output is:
```
==> Caveats
Add the following line to your ~/.bash_profile:
  [[ -r "/usr/local/etc/profile.d/bash_completion.sh" ]] && . "/usr/local/etc/profile.d/bash_completion.sh"

Bash completion has been installed to:
  /usr/local/etc/bash_completion.d
```

So, in the above case, we'd add the following to our `~/.bash_profile`:
```bash
[[ -r "/usr/local/etc/profile.d/bash_completion.sh" ]] && . "/usr/local/etc/profile.d/bash_completion.sh"
```

then run:
```bash
cp complete.bash /usr/local/etc/bash_completion.d/wit
```

### Zsh

```bash
mkdir -p ~/.zsh/completion
cp complete.bash ~/.zsh/completion/_wit
```

Make sure the following is in your `~/.zshrc`:
```bash
fpath=(~/.zsh/completion $fpath)
autoload -Uz compinit && compinit -i
```

Then reload your shell:
```bash
exec $SHELL -l
```

## GitHub Action
This repo also provides a [GitHub Action](https://github.com/features/actions)
that is available for use in GitHub CI/CD workflows. See
[actions/wit/README.md](actions/wit/README.md) for more information.

## Contributing

Please see [README-internals](README-internals.md) for information about development.

## License

See [LICENSE](./LICENSE).
