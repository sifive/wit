#!/usr/bin/env bash

. $(dirname $0)/regress_util.sh

prereq on

# Set up repo foo
make_repo 'foo'
cd foo
detached_commit=$(git rev-parse HEAD)

touch asdas
git add -A
git commit -m "branch commit"
git checkout -b branch
git checkout master
branch_commit=$(git rev-parse HEAD)

touch dsakjkjsa
git add -A
git commit -m "tagged commit"
git tag "v1.0.0"
tag_commit=$(git rev-parse HEAD)

touch jukhia
git add -A
git commit -m "ambiguous commit"
git checkout -b other-branch
ambiguous_commit=$(git rev-parse HEAD)

foo_dir=$PWD
cd ..

wit init myws
cd myws

prereq off

set -x

wit add-pkg $foo_dir
wit update

# checkout branches locally
git -C foo checkout master
git -C foo checkout branch
git -C foo checkout other-branch

wit update-pkg $foo_dir::$detached_commit
wit update
status=$(git -C foo status --porcelain -b | md5)
golden=$(echo "## HEAD (no branch)" | md5)
check "head should be detached" [ $status = $golden ]

wit update-pkg $foo_dir::$branch_commit
wit update
status=$(git -C foo status --porcelain -b | md5)
golden=$(echo "## branch...origin/branch" | md5)
check "head should be attached to branch" [ $status = $golden ]

wit update-pkg $foo_dir::$tag_commit
wit update
status=$(git -C foo status --porcelain -b | md5)
golden=$(echo "## HEAD (no branch)" | md5)
check "head should NOT be attached to a branch" [ $status = $golden ]

wit update-pkg $foo_dir::$ambiguous_commit
output=$(wit update)
status=$(git -C foo status --porcelain -b | md5)
golden=$(echo "## HEAD (no branch)" | md5)
check "head should be detached" [ $status = $golden ]

echo $output | grep "(master, other-branch)"
check "logging should hint at branches" [ $? -eq 0 ]

git -C foo checkout master
wit update
status=$(git -C foo status --porcelain -b | md5)
golden=$(echo "## master...origin/master" | md5)
check "head should stay attached to same branch when not moved" [ $status = $golden ]

set +x

report
finish
