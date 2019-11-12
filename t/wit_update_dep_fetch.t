#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

into_test_dir

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

make_repo 'bar'
# Make bar depend on foo
cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$foo_dir" }
]
EOF
git -C bar add -A
git -C bar commit -m "commit2"
bar_dir=$PWD/bar

wit init myws -a $bar_dir

# Now update the "remote" foo such that the workspace isn't aware
echo "halp" > foo/file2
git -C foo add -A
git -C foo commit -m "commit2"
foo_commit2=$(git -C foo rev-parse HEAD)

cd myws

prereq off

wit -C bar update-dep foo::origin/master
check "Updating foo to origin/master in bar should work" [ $? -eq 0 ]

foo_dep_commit=$(jq -r '.[] | select(.name=="foo") | .commit' bar/wit-manifest.json)
check "Foos commit in bar's manifest should have bumped" [ "$foo_dep_commit" = "$foo_commit2" ]

report
finish
