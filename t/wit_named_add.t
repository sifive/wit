#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

make_repo 'bar'
bar_commit=$(git -C bar rev-parse HEAD)
bar_dir=$PWD/bar

prereq off

set -x
# Now create an empty workspace
wit init myws
cd myws

wit add-pkg $foo_dir
check "wit add-pkg without name should succeed" [ $? -eq 0 ]

wit add-pkg $foo_dir fizz
check "wit add-pkg with name should succeed" [ $? -eq 0 ]

wit update

ls foo && ls fizz
check "relevant packages should exist in workspace" [ $? -eq 0 ]

cd fizz
wit add-dep $bar_dir bazz
check "wit add-dep with name should succeed" [ $? -eq 0 ]
git add -A
git commit -m "bump"
cd ..

wit update-pkg fizz
wit update

ls bazz
check "relevant dependencies should exist in workspace" [ $? -eq 0 ]

old_manifest=$(cat fizz/wit-manifest.json | md5)
wit -C fizz add-dep $foo_dir bazz
check "duplicate name should fail" [ $? -ne 0 ]
new_manifest=$(cat fizz/wit-manifest.json | md5)
check "manifest should not be changed" [ "$old_manifest" = "$new_manifest" ]

set +x

report
finish
