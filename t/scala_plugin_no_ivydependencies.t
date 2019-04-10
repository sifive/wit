#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'

prereq "off"

# Now create a workspace
wit init myws -a $PWD/foo

cd myws
wit fetch-scala

check "wit fetch-scala should succeed" [ $? -eq 0 ]

check "fetch-scala should not fetch anything if there is no ivydependencies.json" [ ! -d "scala" ]

found=$(find . -name "*bloop*" | wc -l)
check "there should NOT be a bloop executable" [ "$found" -eq 0 ]

report
finish
