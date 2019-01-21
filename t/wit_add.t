#!/bin/sh

. $(dirname $0)/regress_util.sh

# Set up repo foo
mkdir foo
git -C foo init
touch foo/file
git -C foo add -A
git -C foo commit -m "commit1"
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

# Now create an empty workspace
wit init myws

cd myws
wit add-pkg $foo_dir
check "wit add-pkg should succeed" [ $? -eq 0 ]

foo_ws_commit=$(jq -r '.[] | select(.name=="foo") | .commit' wit-workspace.json)
check "Added repo should have correct commit" [ "$foo_ws_commit" = "$foo_commit" ]

report
finish
