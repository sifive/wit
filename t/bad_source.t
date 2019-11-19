#!/bin/sh

. $(dirname $0)/test_util.sh

# Now create a workspace from main_repo
wit init myws

cd myws

output=$(wit add-pkg /hopefully/this/path/doesnt/exist.git)

# Should fail because of source doesn't exist
check "wit add-pkg with invalid source fails" [ $? -ne 0 ]

echo $output | grep -i "bad remote"

check "error message is somewhat descriptive" [ $? -eq 0 ]

report
finish
