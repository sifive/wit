#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

into_test_dir

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo
echo "what's up?" > foo/other
git -C foo add -A
git -C foo commit -m "commit2"
foo_commit2=$(git -C foo rev-parse HEAD)
# Create a branch with a commit
echo "blah" > foo/file2
git -C foo checkout -b branch
git -C foo add -A
git -C foo commit -m "branch commit"
foo_commit_branch=$(git -C foo rev-parse HEAD)
# Now return to master
git -C foo checkout master

prereq off

wit init myws
cd myws

wit add-pkg $foo_dir::$foo_commit2

wit update-pkg foo::$foo_commit
check "We should be able to update-pkg without calling update" [ $? -eq 0 ]
foo_remote=$(jq -r '.[] | select(.name=="foo") | .source' wit-workspace.json)
check "update-pkg should leave the source unchanged" [ "$foo_remote" = "$foo_dir" ]

wit update
check "Wit update should succeed" [ $? -eq 0 ]

# Check that "branch" is not a valid branch locally
git -C foo rev-parse branch
check "Branch 'branch' in foo should not yet exist" [ $? -ne 0 ]

wit update-pkg foo::branch
check "Updating foo to a remote branch should work!" [ $? -eq 0 ]

foo_manifest_commit=$(jq -r '.[] | select(.name=="foo") | .commit' wit-workspace.json)
check "The manifest should contain the correct commit" [ "$foo_manifest_commit" = "$foo_commit_branch" ]

foo_lock_commit=$(jq -r '.[] | select(.name=="foo") | .commit' wit-lock.json)
check "Before running 'wit update', the lock should contain the old commit" [ "$foo_lock_commit" = "$foo_commit" ]

wit update
check "wit update should succeed" [ $? -eq 0 ]

commit=$(git -C foo rev-parse HEAD)
check "foo should have checked out the right commit" [ "$commit" = "$foo_commit_branch" ]

foo_lock_commit2=$(jq -r '.[] | select(.name=="foo") | .commit' wit-lock.json)
check "After 'wit update', the lock should contain the correct commit" [ "$foo_lock_commit2" = "$foo_commit_branch" ]

report
finish
