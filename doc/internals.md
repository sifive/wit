# Wit Internals

This document contains documentation for `wit` developers.`

## Testing

Requirements for linting and type checking can be installed with `pip3`:
```
$ pip3 install -r requirements.txt
```

You can run all tests with the included Makefile:
```
$ make test-all
```

### Regression Tests

The regression tests for wit are in the `t/` directory. Each test is a bash script ending with `.t` as the filename extension. You can run individual tests:
```
$ ./t/wit_init.t
```

You can also run all of the regression tests via the Makefile:
```
$ make test-regress
```

#### Customizing wit executable

By default, the regression tests use the `wit` executable in the base directory of this repository. This can be overwritten by setting the `WIT` environment variable to point to either the directory containing the `wit` executable, or setting it to the `wit` executable itself.

For example, if you wish to test whatever `wit` is on your `PATH`, you can type:
```bash
$ WIT=`which wit` make test-regress
```

Alternatively, you can point to a `wit` installation:
```bash
$ WIT=/path/to/wit/installation make test-regress
```

Note that this only affects `test-regress`, linting and type checking are run on the repository itself.

### Lint

This projects uses [Flake8](http://flake8.pycqa.org/en/latest/) for linting. The rules are in [`.flake8`](.flake8) and linting can be run with:
```
$ make test-lint
```

### Type Checking

We also use [mypy](http://mypy-lang.org/) for (limited) static type checking. The rules are specified in [`mypy.ini`](mypy.ini) and can be run with:
```
$ make test-typecheck
```

## Terms

Much of `wit` terminology is derived directly from `git`, upon which `wit` relies.

**package**: A git repository that is incorporated into a `wit` workspace, either explicitly by being added to the workspace by the workspace owner, or implicitly by being included from aanother package.

**workspace**: A workspace is a work area that contains zero or more packages, along with meta-data about those packages.


## Supporting files

These files are generated and maintained by `wit`. Wit uses json for its meta-data. Note that the purpose and thus the format of these files are all very similar; they explicitly identify packages.

`wit-workspace.json`: This file lists the packages explicitly added to the workspace, along with their specific git hash.
```
[
  {
    "commit": "d575fab969bee591e115f6e5f836b4bbc810883f",
    "name": "chisel3-wake",
    "source": "git@github.com:sifive/chisel3-wake.git"
  }
]
```

`wit-manifest.json`: Packages specify their dependencies in the `wit-manifest.json` file. These packages are implicitly added to the workspace during `wit`'s resolution phase.
```
[
  {
    "commit": "2272044c6ab46b5148c39c124e66e1a8e9073a24",
    "name": "firrtl",
    "source": "git@github.com:freechipsproject/firrtl.git"
  }
]
```

`wit-lock.json`: When wit traverses the packages in your workspace its resolution algorithm deterministically generates a list of explicit and implicit packages along with git hashes. `wit-lock.json` contains this list, which is a full specification of your workspace's state.

```
{
  "firrtl": {
    "commit": "2272044c6ab46b5148c39c124e66e1a8e9073a24",
    "name": "firrtl",
    "source": "git@github.com:freechipsproject/firrtl.git"
  },
  ...
}
```


## Package Resolution Algorithm

Wit's purpose is to assist development by deterministically generating a workspace of packages that ensures all dependencies are met. Its algorithm is straightforward:

1. Initialize an empty repo -> package map (`MAP`).
2. Create a queue of all packages present in the `wit-workspace.json` file ordered by commit time. Remember, a package is a specific commit of a git repo.
3. Pop the package (`P`) with the youngest (newest) commit time. Determine the source repo (`R`).
4. If `R` has already been seen and the package (`P'`) specified in `MAP[R]` _is not_ a descendent of `P` (i.e. `P`'s commit is not present in `P'`'s history) then fail.
5. If `R` has already been seen and `P'` _is_ a descendent of `P` then go to step 2
6. If `R` has not been seen then set `MAP[R]` to `P`.
7. Determine `P`'s `wit` dependencies from `P/wit-manifest.json`. Append these to the ordered list from step 2 based on commit time.
8. Go to step 3.

## Post-refactor Package Resolution etc
Wit has three main responsibilities:
1. Generate a reproducible dependency tree from a `wit-workspace.json`
2. Deduplicate packages in that dependency tree into a flat list of packages
3. Make the workspace filesystem match the aforementioned flat list of packages as close as possible without overwriting the users' uncommitted changes

As of [`5670099b`][5670099b], Wit is increasingly built with assumption that we might encounter problems while fulfilling Responsibilities 1 & 2.

[5670099b]: https://github.com/sifive/wit/commit/5670099b45988e16c765ed696045231684de3b5d

## Dependency tree exploring & deduplication
Responsibilities 1 & 2 are fulfilled by the same algorithm in Wit to reduce unnecessary cloning of Git repos.

In Wit, the process of exploring & deduplicating packages is called "package resolution."

The following objects are used to store data:
1. `Dependency`: what's _requested_ by the `wit-workspace.json` and `wit-manifest.json` files
2. `Package`: the outcome of deduplicating a list of `Dependency` objects with the same
3. `GitRepo`: the repo on disk used to analyze `Package` and `Dependency` objects

During package resolution, Wit does the following:
1. Explore `wit-workspace.json` and `wit-manifest.json` files, generating `Dependency` objects
2. Bind each `Dependency` object to `Package` object of the same name. All `Dependency` objects of the same name should point to the same Package object.
3. Bind that `Package` object to `GitRepo` on disk, used to find the commit times and git ancestry of each Dependency
4. Use the `GitRepo` to find the commit time of each Dependency
5. Add the `Dependency` objects to the queue in tuples of (Dependency, commit time).
6. Pop the `Dependency` with the newest commit time from the queue
7. The newest `Dependency` out of all of the `Dependency` objects of the same name is the one we want to cloned to disk. Therefore, the `Dependency` we just popped is the "winner" of the deduplication algorithm
8. So far, the `Package` object was used to group `Dependency` objects of the same name together. Now that we know which `Dependency` is the winner, we can populate the `source` and `revision` fields of the `Package`.
9. Does the popped `Package` object have a `wit-manifest.json`?
   1. Yes: Skip to Step 1, using its `wit-manifest.json`
   2. No: Are there more items in the queue?
      1. Yes: Skip to step 6
      2. No: Package resolution complete!

## Types of Commands

### Modify json
- `add-pkg`
- `add-dep`
- `update-pkg`
- `update-dep`

### Analyze json, Modify .wit
- `status`: compare `resolve(workspace.json)` to the filetree
- `resolve()`

### Analyze json, user filetree
- `inspect`: analyze the output of `resolve(lock.json)`

### Modify user filetree
- `update`: update filetree to match the model of `resolve(workspace.json)`
