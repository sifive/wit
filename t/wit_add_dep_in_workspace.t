#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit1=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo
echo "wow" > foo/file2
git -C foo add -A
git -C foo commit -m "commit 2"
foo_commit2=$(git -C foo rev-parse HEAD)

make_repo 'bar'
bar_dir=$PWD/bar
cat << EOF | jq . > bar/wit-manifest.json
[ {"commit": "$foo_commit1", "name": "foo", "source": "$foo_dir" } ]
EOF
git -C bar add -A
git -C bar commit -m "Add dep on foo"
bar_commit=$(git -C bar rev-parse HEAD)

make_repo 'fizz'
fizz_dir=$PWD/fizz
cat << EOF | jq . > fizz/wit-manifest.json
[ {"commit": "$bar_commit", "name": "bar", "source": "$bar_dir" } ]
EOF
git -C fizz add -A
git -C fizz commit -m "Add dep on bar"

prereq off

wit init myws -a $fizz_dir
cd myws

# Check out newer foo commit
git -C foo checkout $foo_commit2

wit -C fizz add-dep foo
check "wit add-dep a package in the workspace should succeed" [ $? -eq 0 ]

foo_manifest_commit=$(jq -r '.[] | select(.name=="foo") | .commit' fizz/wit-manifest.json)
check "Added foo dependency should have correct commit" [ "$foo_manifest_commit" = "$foo_commit2" ]

foo_manifest_source=$(jq -r '.[] | select(.name=="foo") | .source' fizz/wit-manifest.json)
check "Added foo dependency should have correct source" [ "$foo_manifest_source" = "$foo_dir" ]

report
finish
