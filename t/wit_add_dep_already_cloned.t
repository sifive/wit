#!/bin/sh

. $(dirname $0)/regress_util.sh

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

make_repo 'bar'
bar_commit=$(git -C bar rev-parse HEAD)
bar_dir=$PWD/bar

set -x
# Now create an empty workspace
wit init myws -a $foo_dir

cd myws
git clone $bar_dir

wit -C foo add-dep bar
check "wit add-dep an already cloned repo should succeed" [ $? -eq 0 ]

bar_manifest_commit=$(jq -r '.[] | select(.name=="bar") | .commit' foo/wit-manifest.json)
check "Added bar dependency should have correct commit" [ "$bar_manifest_commit" = "$bar_commit" ]

set +x

report
finish
