#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

into_test_dir

# Set up repo foo
make_repo 'bar'
bar_commit=$(git -C bar rev-parse HEAD)
bar_dir=$PWD/bar

make_repo 'foo'
cat << EOF | jq . > foo/wit-manifest.json
[
    { "commit": "$bar_commit", "name": "bar", "source": "$bar_dir" }
]
EOF
git -C foo add -A
git -C foo commit -m "add manifest"
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

prereq off

set -x
# Now create an empty workspace
wit init myws

cd myws
wit add-pkg $foo_dir
output=$(wit update)
echo $output | grep "disregarding uncommitted changes"
check "initial wit update should not log uncommitted manifest warnings" [ $? -ne 0 ]
echo $output | grep "manifest instead of currently checked-out version"
check "initial wit update should not log different manifest warnings" [ $? -ne 0 ]

rm foo/wit-manifest.json
output=$(wit update)
echo $output | grep "disregarding uncommitted changes"
check "initial wit update should log uncommitted manifest warnings" [ $? -eq 0 ]
echo $output | grep "manifest instead of currently checked-out version"
check "initial wit update should not log different manifest warnings" [ $? -ne 0 ]

git -C foo add -A
git -C foo commit -m "remove manifest"
output=$(wit update)
echo $output | grep "disregarding uncommitted changes"
check "initial wit update should not log uncommitted manifest warnings" [ $? -ne 0 ]
echo $output | grep "manifest instead of currently checked-out version"
check "initial wit update should log different manifest warnings" [ $? -eq 0 ]

set +x

report
finish
