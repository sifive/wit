# wit internals
This document describes terms and concepts used by `wit`.


## Terms

**repository**: A standard git repository. Each git "commit" in the repository represents a package, as defined below.

**package**: A package is a specific hash of a git repository that is incorporated into a `wit` workspace, either explicitly by being added to the workspace by the workspace owner, or implicitly by being included from aanother package.

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
]```

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

