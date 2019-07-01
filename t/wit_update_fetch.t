#!/bin/sh

. $(dirname $0)/regress_util.sh

# Set up repo foo
make_repo 'foo'
foo_commit1=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

# Now set up repo bar to depend on foo
make_repo 'bar'
cat << EOF | jq . > bar/wit-manifest.json
[
  { "commit": "$foo_commit1", "name": "foo", "source": "$foo_dir" }
]
EOF
git -C bar add -A
make_commit bar "commit2"
bar_commit1=$(git -C bar rev-parse HEAD)
bar_dir=$PWD/bar

# Create the workspace
wit init myws -a $bar_dir

# Now update foo and bar remotes
echo "yep" > foo/file2
git -C foo add -A
make_commit foo "commit2"
foo_commit2=$(git -C foo rev-parse HEAD)

cat << EOF | jq . > bar/wit-manifest.json
[
  { "commit": "$foo_commit2", "name": "foo", "source": "$foo_dir" }
]
EOF
git -C bar add -A
make_commit bar "commit3"
bar_commit2=$(git -C bar rev-parse HEAD)

set -x

cd myws

# So as to not use fetch from a different command, edit bar's commit in the workspace
jq "map((select(.name == \"bar\") | .commit) |= \"$bar_commit2\")" wit-workspace.json > tmp
mv tmp wit-workspace.json

wit update
check "wit update should fetch remote commits" [ $? -eq 0 ]

foo_ws_commit=$(git -C foo rev-parse HEAD)
check "the correct commit of foo should be checked out" [ "$foo_ws_commit" = "$foo_commit2" ]

bar_ws_commit=$(git -C bar rev-parse HEAD)
check "the correct commit of bar should be checked out" [ "$bar_ws_commit" = "$bar_commit2" ]

set +x

report
finish
