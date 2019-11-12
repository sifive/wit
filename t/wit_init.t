#!/bin/sh

. $(dirname $0)/test_util.sh

wit init
check "Wit init with no arguments should fail" [ $? -eq 2 ]

echo "Verify that we can create a workspace with no initial repo"
wit init myws
check "Wit init with no initial repo succeeds" [ $? -eq 0 ]
check "Wit creates a wit-workspace.json file" [ -e 'myws/wit-workspace.json' ]

report
finish
