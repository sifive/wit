#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

mkdir newdir
cp -r foo newdir/

# Now set up repo main_repo to depend on foo, foo2, foo3
mkdir main_repo
git -C main_repo init

cat << EOF | jq . > main_repo/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$PWD/foo" },
    { "commit": "$foo_commit", "name": "foo", "source": "$PWD/newdir/foo" }
]
EOF

git -C main_repo add -A
git -C main_repo commit -m "commit1"
main_repo_commit=$(git -C main_repo rev-parse HEAD)

prereq "off"

# Now create a workspace from main_repo
wit init myws -a $PWD/main_repo

# Should fail because of conflicting paths for foo
check "wit init with conflicting paths passes" [ $? -eq 0 ]


wit --repo-path="$PWD $PWD/newdir $PWD/newdir2" init myws2 -a $PWD/main_repo
check "wit with path set succeeds" [ $? -eq 0 ]

report
finish
