#!/bin/sh

. $(dirname $0)/regress_util.sh

# Now create a workspace from main_repo
wit init myws

cd myws

output=$(wit add-pkg https://github.com/github/invalid.git)

# Should fail because of conflicting paths for foo
check "wit add-pkg with invalid source fails" [ $? -ne 0 ]

echo $output | grep -i "bad remote"

check "error message is somewhat descriptive" [ $? -eq 0 ]

report
finish
