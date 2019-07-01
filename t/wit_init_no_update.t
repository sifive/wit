#!/bin/sh

. $(dirname $0)/regress_util.sh

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

# Now set up repo bar to depend on foo
mkdir bar
git -C bar init
echo "[{\"commit\":\"$foo_commit\",\"name\":\"foo\",\"source\":\"$PWD/foo\"}]" | jq '.' >> bar/wit-manifest.json
git -C bar add -A
make_commit bar "commit1"
bar_commit=$(git -C bar rev-parse HEAD)

# Create a workspace but do NOT update
wit init --no-update myws -a $PWD/bar
cd myws

check "foo should not be cloned if --no-update is given" [ ! -d foo ]
# the update brings in foo
wit update

check "foo should be pulled in upon calling update" [ -d foo ]
foo_ws_commit=$(git -C foo rev-parse HEAD)
check "foo commit should match the dependency in bar" [ "$foo_ws_commit" = "$foo_commit" ]

foo_lock_commit=$(jq -r '.foo.commit' wit-lock.json)
check "ws-lock.json should contain correct foo commit" [ "$foo_lock_commit" = "$foo_commit" ]

bar_lock_commit=$(jq -r '.bar.commit' wit-lock.json)
check "ws-lock.json should contain correct bar commit" [ "$bar_lock_commit" = "$bar_commit" ]

report
finish
