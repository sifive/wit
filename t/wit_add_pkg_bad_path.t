#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit1=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

prereq off

# Now create an empty workspace
wit init myws
cd myws

# fail to add a package that has the correct name, but an incorrect path
wit add-pkg $foo_dir/foo

# add package with correct path
wit add-pkg $foo_dir
check "wit add-pkg should succeed regardless of past failed attempts with same name" [ $? -eq 0 ]

report
finish
