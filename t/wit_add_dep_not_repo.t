#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

# Set up repo foo
mkdir foo
git -C foo init
touch foo/file
git -C foo add -A
git -C foo commit -m "commit1"
foo_dir=$PWD/foo

# Now create an empty workspace
wit init myws
cd myws

# Make some random directory
mkdir bar

# Make a repo that's not part of the workspace
make_repo 'fizz'

prereq off

# Now try to make bar depend on foo
msg=$(wit -C bar add-dep $foo_dir)
check "Adding dependency to non-package should fail" [ $? -ne 0 ]

msg=$(wit -C fizz add-dep $foo_dir)
check "Adding dependency to non-workspace repo should fail" [ $? -ne 0 ]

report
finish
