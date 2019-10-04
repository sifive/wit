#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo

wit init myws -a $foo_dir

cd myws
rm -rf foo

prereq off

wit update
check "wit should redownload a deleted package" [ $? -eq 0 ]

foo_ws_commit=$(git -C foo rev-parse HEAD)
check "The checked out commit should be correct" [ "$foo_ws_commit" = "$foo_commit" ]

report
finish
