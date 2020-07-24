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

output=$(wit foreach 'echo $WIT_REPO_NAME' 2>&1 | tr "\n" ' ')
expected='Entering baa baa Entering foo foo '
check "wit foreach should know the repository names" $([[ "$output" = "$expected" ]])

output2=$(wit foreach git status)
RES=$?
check "git status should return 0 for each repository" [ $RES ]

echo "my file" > foo/myfile
echo "my file" > baa/myfile
output3=$(wit foreach grep "my file" *)
RES=$?
check "multiword args should be passed through to grep" [ $RES ]

report
finish
