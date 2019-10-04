#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq off

# Set up repo foo
make_repo 'foo'
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
