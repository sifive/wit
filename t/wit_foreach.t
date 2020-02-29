#!/bin/bash

. $(dirname $0)/test_util.sh

prereq on

# make 2 repositories
make_repo 'foo'
foo_dir=$PWD/foo
make_repo 'baa'
baa_dir=$PWD/baa

# create wit workspace
wit init myws -a $foo_dir -a $baa_dir
cd myws

prereq off

output=$(wit foreach --quiet 'echo $WIT_REPO_NAME' | tr '\n' ' ')
expected='baa foo '
check "wit foreach should know the repository names" $([ "$output" = "$expected" ])


report
finish
