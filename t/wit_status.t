#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

# Now set up repo bar to depend on foo
mkdir bar
git -C bar init
echo "[{\"commit\":\"$foo_commit\",\"name\":\"foo\",\"source\":\"$PWD/foo\"}]" | jq '.' >> bar/wit-manifest.json
git -C bar add -A
git -C bar commit -m "commit1"
bar_commit=$(git -C bar rev-parse HEAD)

prereq off

# Now create a workspace from bar
wit init myws -a $PWD/bar
cd myws

wit status
check "wit status should not fail" [ $? -eq 0 ]

report
finish
