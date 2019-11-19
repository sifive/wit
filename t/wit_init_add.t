#!/bin/sh

. $(dirname $0)/test_util.sh

# Set up repo foo
make_repo 'foo'

foo_dir=$PWD/foo
foo_commit=$(git -C foo rev-parse HEAD)

echo "Verify that we can create a workspace with an initial package"
wit init myws -a ${foo_dir}::${foo_commit}

# Extract the wit hash recorded in the wit-workspace
cd myws
wit_workspace_hash=$(jq -r '.[] | select(.name=="foo") | .commit' wit-workspace.json)
check "Wit manifest contains requested hash" [ "$wit_workspace_hash" = "$foo_commit" ]

# Get the latest checked out version of the wit repo and make
# sure it matches what we expect
wit update
foo_pkg_commit=$(git -C foo rev-parse HEAD)
check "Updated wit repo is at requested hash" [ "$foo_pkg_commit" = "$foo_commit" ]

report
finish
