#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
git -C foo branch 💣

# Create new commit such that HEAD isn't the commit we want, since that's
# necessary for forcing wit into executing git show-ref, which is what triggers
# the error.
echo $RANDOM > foo/file
git -C foo add -A
git -C foo commit -m "commit2"

# Set locale to ASCII (non-UTF-8) encoding.
export LANG=C
export LC_ALL=C

prereq off

wit init myws -a $PWD/foo::💣
cd myws

foo_ws_commit=$(git -C foo rev-parse HEAD)
check "foo commit should match the dependency" [ "$foo_ws_commit" = "$foo_commit" ]

report
finish
