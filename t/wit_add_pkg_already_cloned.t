#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

prereq off

# Now create an empty workspace
wit init myws

cd myws
git clone $foo_dir

wit add-pkg $foo_dir
check "wit add-pkg an already cloned repo should succeed" [ $? -eq 0 ]

foo_ws_commit=$(jq -r '.[] | select(.name=="foo") | .commit' wit-workspace.json)
check "Added repo should have correct commit" [ "$foo_ws_commit" = "$foo_commit" ]

foo_ws_source=$(jq -r '.[] | select(.name=="foo") | .source' wit-workspace.json)
check "Added repo should have source copied from remote" [ "$foo_ws_source" = "$foo_dir" ]

report
finish
