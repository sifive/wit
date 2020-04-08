## Using a local repository cache for a faster 'wit init'

If you will have multiple similar wit workspaces, there is likely cloned
repositories that have substantially similar contents.

Using the environment variable `WIT_WORKSPACE_REFERENCE` you can point at a workspace
or directory containing pre-cloned repositories.
These pre-cloned repositories do not need to have the most recent commits, what is there
will be used and the remainder will be fetched from the regularly specified remote repository.
Similarly, any missing repositories in the cache will be ignored and a regular clone will occur.

```
$ tree
.
└── workspace1
    ├── baa
    └── foo

$ export WIT_WORKSPACE_REFERENCE=$PWD/workspace1
$ wit init workspace2 -a git@github.com:acme/foo
$ tree
.
├── workspace1
│   ├── baa
│   └── foo
└── workspace2
    ├── baa
    └── foo
```

Internally this uses git clone's [`--reference`](https://git-scm.com/docs/git-clone#Documentation/git-clone.txt---reference-if-ableltrepositorygt) argument.
