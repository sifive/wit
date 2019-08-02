#!/usr/bin/env bash

. $(dirname $0)/regress_util.sh

prereq "on"

make_repo 'xyz'

cd xyz
touch zero
git add -A
git commit -m "xyz:0"

git checkout -b branch_a
touch testa
git add -A
git commit -m "xyz:a"
xyz_commit_a=$(git rev-parse HEAD)

git checkout master

git checkout -b branch_b
touch testb
git add -A
git commit -m "xyz:b"
xyz_commit_b=$(git rev-parse HEAD)
cd ..

make_repo 'foo'
cat << EOF | jq . > foo/wit-manifest.json
[
    { "commit": "$xyz_commit_b", "name": "xyz", "source": "$PWD/xyz" }
]
EOF
git -C foo add -A
git -C foo commit -m "add xyz:2"
foo_commit=$(git -C foo rev-parse HEAD)

# Set up repo foo
make_repo 'bar'
cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$xyz_commit_a", "name": "xyz", "source": "$PWD/xyz" }
]
EOF
git -C bar add -A
git -C bar commit -m "add xyz:1"

prereq "off"

# Now create a workspace from main_repo
wit init myws -a $PWD/foo -a $PWD/bar

check "wit init should fail with AncestryError" [ $? -ne 0 ]

cd myws
wit update
check "wit update should fail with AncestryError" [ $? -ne 0 ]

ls foo || ls bar || ls xyz
check "repos should not be checked out" [ $? -ne 0 ]

wit update --force
check "wit update --force should return non-zero exit code" [ $? -ne 0 ]

ls foo && ls bar && ls xyz
check "repos should be checked out" [ $? -eq 0 ]

report
finish
