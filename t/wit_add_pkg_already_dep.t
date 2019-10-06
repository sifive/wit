#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit1=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

# Set up repo bar
make_repo 'bar'
bar_commit=$(git -C bar rev-parse HEAD)
bar_dir=$PWD/bar

prereq off

# Now create an empty workspace
wit init myws

cd myws
wit add-pkg $bar_dir
check "wit add-pkg an already cloned repo should succeed" [ $? -eq 0 ]

wit update

wit -C bar add-dep $foo_dir
git -C bar add -A
git -C bar commit -m "add foo as dep"
wit update-pkg bar
wit update

foo_ws_commit=$(jq -r '.[] | select(.name=="foo") | .commit' wit-lock.json)
check "Added sub-dep should have correct commit" [ "$foo_ws_commit" = "$foo_commit1" ]

wit add-pkg foo

wit update

foo_ws_source=$(jq -r '.[] | select(.name=="foo") | .source' wit-workspace.json)
check "Added repo should have source copied from remote" [ "$foo_ws_source" = "$foo_dir" ]

report
finish
