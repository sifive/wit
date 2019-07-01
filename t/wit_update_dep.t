#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo
# Add a second commit
echo "halp" > foo/file2
git -C foo add -A
make_commit foo "commit2"
foo_commit2=$(git -C foo rev-parse HEAD)

make_repo 'bar'
# Make bar depend on foo
cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$foo_dir" }
]
EOF
git -C bar add -A
make_commit bar "commit2"
bar_dir=$PWD/bar

wit init myws -a $bar_dir
cd myws

prereq off

set -x

wit -C bar update-dep foo
check "Updating foo in bar should work, but..." [ $? -eq 0 ]

foo_dep_commit=$(jq -r '.[] | select(.name=="foo") | .commit' bar/wit-manifest.json)
check "Foos commit in bar's manifest should be unchanged" [ "$foo_dep_commit" = "$foo_commit" ]

check "Checked out foo commit should be unchanged" [ "$(git -C foo rev-parse HEAD)" = "$foo_commit" ]

wit -C bar update-dep foo::master
check "Updating foo to master should work" [ $? -eq 0 ]

foo_dep_commit=$(jq -r '.[] | select(.name=="foo") | .commit' bar/wit-manifest.json)
check "Foos commit in bar's manifest should have bumped" [ "$foo_dep_commit" = "$foo_commit2" ]

check "Checked out foo commit should be unchanged" [ "$(git -C foo rev-parse HEAD)" = "$foo_commit" ]

# Bump foo in bar
git -C bar add -A
make_commit bar "bump foo"
# Now update the workspace with the bump
wit update-pkg bar
wit update

check "Checked out foo commit should have bumped" [ "$(git -C foo rev-parse HEAD)" = "$foo_commit2" ]

set +x

report
finish
