#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit1=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

wit init myws -a $foo_dir

# Now update the "remote" foo such that the workspace isn't aware
echo "halp" > foo/file2
git -C foo add -A
git -C foo commit -m "commit2"
foo_commit2=$(git -C foo rev-parse HEAD)

cd myws

prereq off

git -C foo cat-file -t $foo_commit2
check "The remote commit should not yet be known in local foo checkout" [ $? -ne 0 ]

wit update-pkg foo::$foo_commit2
check "Updating foo to a commit the requires fetching should work" [ $? -eq 0 ]

wit update

foo_repo_commit=$(git -C foo rev-parse HEAD)
check "The correct foo commit should be checked out" [ "$foo_repo_commit" = "$foo_commit2" ]

report
finish
