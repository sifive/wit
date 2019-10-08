#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

make_repo 'bar'
bar_dir=$PWD/bar

cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$foo_dir" }
]
EOF
git -C bar add -A
git -C bar commit -m "add dep on foo"

# Now create workspace
wit init myws -a $bar_dir
cd myws

prereq off

wit update-pkg potato
check "Updating a package not in the workspace should fail" [ $? -ne 0 ]

check "foo should have been pulled in as a dependency" [ -d foo ]

wit update-pkg foo
check "Updating a package in the lock file but not in the workspace should fail" [ $? -ne 0 ]

report
finish
