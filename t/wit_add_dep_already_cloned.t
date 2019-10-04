#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

make_repo 'bar'
bar_dir=$PWD/bar
bar_commit1=$(git -C bar rev-parse HEAD)
echo "hi" > bar/file2
git -C bar add -A
git -C bar commit -m "commit2"
bar_commit2=$(git -C bar rev-parse HEAD)

prereq off

# Now create an empty workspace
wit init myws -a $foo_dir

cd myws
git clone $bar_dir

wit -C foo add-dep bar::$bar_commit1
check "wit add-dep an already cloned repo should succeed" [ $? -eq 0 ]

bar_checkedout_commit=$(git -C bar rev-parse HEAD)
check "wit should *not* do a checkout when adding dep on existing repo" [ "$bar_checkedout_commit" = "$bar_commit2" ]

bar_manifest_commit=$(jq -r '.[] | select(.name=="bar") | .commit' foo/wit-manifest.json)
check "Added bar dependency should have correct commit" [ "$bar_manifest_commit" = "$bar_commit1" ]

bar_manifest_source=$(jq -r '.[] | select(.name=="bar") | .source' foo/wit-manifest.json)
check "Added bar dependency should have correct source" [ "$bar_manifest_source" = "$bar_dir" ]

report
finish
