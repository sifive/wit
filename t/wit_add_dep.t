#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
mkdir foo
git -C foo init
touch foo/file
git -C foo add -A
git -C foo commit -m "commit1"
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

# Set up repo bar, upon which foo will depend
mkdir bar
git -C bar init
touch bar/file
git -C bar add -A
git -C bar commit -m "commit1"
bar_commit=$(git -C bar rev-parse HEAD)
# Make a new branch that points to bar_commit
git -C bar checkout -b coolbranch
# Now back to master for more commits
git -C bar checkout master
touch bar/file2
git -C bar add -A
git -C bar commit -m "commit2"
bar_dir=$PWD/bar

prereq off

# Now create an empty workspace
wit init myws

cd myws
wit add-pkg $foo_dir
check "wit add-pkg should succeed" [ $? -eq 0 ]

# Need to update the lock file
wit update
check "wit update should succeed" [ $? -eq 0 ]

check "bar should not yet exist in the workspace" [ ! -d bar/.git ]

wit -C foo add-dep $bar_dir::coolbranch
check "wit add-dep should succeed" [ $? -eq 0 ]

foo_bar_commit=$(jq -r '.[] | select(.name=="bar") | .commit' foo/wit-manifest.json)
check "foo should depend on the correct commit of bar" [ "$foo_bar_commit" = "$bar_commit" ]

bar_manifest_source=$(jq -r '.[] | select(.name=="bar") | .source' foo/wit-manifest.json)
check "Added bar dependency should have correct source" [ "$bar_manifest_source" = "$bar_dir" ]

report
finish
