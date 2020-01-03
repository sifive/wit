#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on
make_repo 'foo'
make_repo 'foo-dep1'
make_repo 'foo-dep2'
prereq off

wit init myws -a $PWD/foo
check "foo-dep1 should not yet exist in the workspace" [ ! -d myws/foo-dep1/.git ]
check "foo-dep2 should not yet exist in the workspace" [ ! -d myws/foo-dep2/.git ]
cd myws/foo

# Create a dependency with a message
wit add-dep ../foo-dep1 -m "message1"
check "wit add-dep should succeed" [ $? -eq 0 ]
grep message1 wit-manifest.json
check "wit add-dep should have created comment message" [ $? -eq 0 ]

# Create a dependency without a message
wit add-dep ../foo-dep2
check "wit add-dep should succeed" [ $? -eq 0 ]
check "only one dependency should have a message" [ $(grep '//' wit-manifest.json | wc -l) -eq 1 ]
grep message1 wit-manifest.json
check "foo-dep1 should be the one with the message" [ $? -eq 0 ]

# Update foo-dep2 dependency, now with a message
wit update-dep ../foo-dep2 -m "message2"
check "wit update-dep should succeed" [ $? -eq 0 ]
grep message2 wit-manifest.json
check "new message should be created" [ $? -eq 0 ]
grep message1 wit-manifest.json
check "original message should still be there" [ $? -eq 0 ]

report
finish
