#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

prereq off

# Now create an empty workspace
wit init myws

cd myws
wit add-pkg $foo_dir
check "wit add-pkg should succeed" [ $? -eq 0 ]

wit add-pkg $foo_dir
check "wit add-pkg a second time should fail" [ $? -eq 1 ]

report
finish
