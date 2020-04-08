# Wit Tutorial

This tutorial assumes you have wit and git installed in your path.

## Basics

Wit is a tool for managing workspaces. It is intended as a supplement (not a replacement)
for Git-based workflows.
The goal of wit is to enable development in a multiple user and repository environment.

## Creating a workspace

The wit workflow revolves around the notion of a "workspace".
They are created with the `init` command.

```bash
mkdir tutorial
cd tutorial
wit init myws
ls myws
```

You should see a file called `wit-workspace.json` and a file called `wit-lock.json`.
We will refer to these files as the "workspace file" and the "lock file" respectively.
These two files mark the root of the workspace and contain all of the information
about the workspace.
At the moment, these files are empty, but we will see their contents change in this tutorial.

## Adding a package

Workspaces are made up of "packages". A package corresponds to a git repository.
Let us create a git repository and add it to the workspace.

```bash
# From the tutorial directory
git init foo
echo "Hello World!" > foo/file.txt
git -C foo add file.txt
git -C foo commit -m "Initial commit"
FOO_PATH=$PWD/foo
```

Now that we have a git repo, we'll add it to the workspace.

```bash
cd myws
wit add-pkg $FOO_PATH
```

This will add `foo` to the `wit-workspace.json` and clone `foo` into the workspace.
Note that while we're using local paths to repositories as the remote in this tutorial,
it works just the same for git repositories hosted with your favorite hosting service.

Note that the above is equivalent to cloning a repository into the workspace and then adding it by directory:

```bash
# You can this *instead* of the above, but don't run both
wit clone $FOO_PATH
wit add-pkg foo
```

Now let us inspect the state of the workspace

```bash
wit status
```

You should see something like the following:

```
Clean packages:
Dirty packages:
foo (will be added to workspace and lockfile)
```

We have added `foo` to the workspace so why does `status` indicate it "will be added to workspace"?
To explain, let us inspect the contents of the workspace and lock files.

```bash
cat wit-workspace.json
cat wit-lock.json
```

You will notice that while the workspace file contains information about `foo`,
the lock file remains empty.
This is because we have not yet run `wit update`.
The workspace file reflects the high-level, desired objectives of the user.
In contrast, the lock file contains the resolved state of the workspace.
When packages depend on one another, only the user-specified ones are listed in
the `wit-workspace.json`.
`wit-lock.json` will contain packages pulled in as dependencies and transitive
dependencies of those specific in the workspace file.

Now, let us update the workspace

```bash
wit update
wit status
```

You should now see `foo` marked as a clean package:

```
Clean packages:
    foo
Dirty packages:
```

Another thing to note, similarly to git submodules, `wit update` will check out
repositories in a detached state.
This can make development a little tricky as you may have a branch checked out
that you're working on. This is something we will fix in a future version of wit.

## Updating a package

Let's assume there have been upstream changes to `foo` and we would like to see
those changes reflected in our workspace.

First, let us make some "upstream changes".

```bash
echo "content." > $FOO_PATH/file2.txt
git -C $FOO_PATH add file2.txt
git -C $FOO_PATH commit -m "A second commit"
git -C $FOO_PATH log
git -C foo log
```

You should see that the "remote" foo (located at `$FOO_PATH`) and the version in the
workspace are out of sync. We can update the local checkout with `update-pkg`:

```bash
wit update-pkg foo::origin/master
```

Note that the inclusion `origin/` makes it clear that we want to pull `master` from the
remote repo. If we were to just write `wit update-pkg foo::master`, `master` would refer
to the local branch.

An equivalent way to accomplish this same goal is to check out the commit we want in the
local checkout and let `update-pkg` figure it out:

```bash
# An alternative way to do the above
git -C foo checkout master
git -C foo pull
wit update-pkg foo
```

When you have run one of the above, `wit` will notify you that it update the commit hash,
and will remind you to run `wit update`.
As before, `update-pkg` will modify the manifest file, but you need to propagate those changes
to the lock file.

```bash
wit update
wit status
```

We have now updated `foo`!


## Adding a dependency

Let us create another package for `foo` to depend on.

```bash
cd ..  # Back to root of tutorial
git init bar
echo "Howdy" > bar/file.txt
git -C bar add file.txt
git -C bar commit -m "Initial commit"
BAR_PATH=$PWD/bar
cd myws
```

Now that we have `bar`, let's make `foo` have a dependency on it.

```bash
wit -C foo add-dep $BAR_PATH
```

First, note that `wit` has a `-C` option. It works in the same way as other tools like
`git` and `make`, by changing the current working directory to the directory argument
following `-C` and running the command in that directory.
Thus, in this command, we run `add-dep` within the `foo` package.
This makes `foo` the package to which we are adding the dependency.
This is equivalent to the following

```bash
# You can run this as an alternative for the above
cd foo
wit add-dep $BAR_PATH
cd ..
```

Since `bar` is the argument to `add-dep`, it is the package were are
saying that `foo` should depend on.
Now let's see what adding this dependency did:

```bash
wit status
git -C foo status
```

You should see something like

```
Clean packages:
Dirty packages:
    foo (untracked content)
```
```
HEAD detached at <hash>
Untracked files:
  (use "git add <file>..." to include in what will be committed)

        wit-manifest.json

nothing added to commit but untracked files present (use "git add" to track)
```

Similarly to before, the workspace is not updated.
Unlike last time, this created a new (currently uncommitted) file inside `foo` called
`wit-manifest.json`. We refer to these files as "manifest files".
They describe the relationship between packages. Let us inspect the contents:

```bash
cat foo/wit-manifest.json
```

You will notice it looks very similar to the workspace file.
This is not guaranteed to remain true as wit evolves and we add more features.

Now we need to reflect this new dependency in the workspace.
We need to commit the manifest file to `foo`.
This may seem unnecessary, but since wit must create workspaces reproducibly
and deterministically, it requires that manifest files be versioned.

Recall that wit checks out repositories in a "detached" state.
We first want to check out a branch so that we can keep our changes and push them
to the remote.

As a tip, you can use the `git branch` command to help you see what branches
contain a certain commit. For example:

```bash
git -C foo branch --contains    # show local branches
git -C foo branch -r --contains # show remote branches
git -C foo branch -a --contains # show local and remote
```

Now let us check out `master` and commit the manifest file.

```bash
git -C foo checkout master
git -C foo add wit-manifest.json
git -C foo commit -m "Add dependency on bar"
```

Now that we have committed the dependency on `bar`, we should update the workspace

```
wit update-pkg foo
wit update
wit status
```

There we have it! We have made package `foo` depend on package `bar`.

