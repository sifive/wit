#!/bin/sh

. $(dirname $0)/regress_util.sh

wit init 
check "Wit init with no arguments should fail" [ $? -eq 2 ]

echo "Verify that we can create a workspace with no initial repo"
wit init myws
check "Wit init with no initial repo succeeds" [ $? -eq 0 ]
check "Wit creates a wit-manifest.json file" [ -e 'myws/wit-manifest.json' ]

report
finish
